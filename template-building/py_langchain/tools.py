import asyncio
from arcadepy import AsyncArcade
from typing import Any, List
from pydantic import BaseModel, Field, create_model
from arcadepy.types import ToolDefinition
from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
import globals


def get_python_type(val_type: str) -> Any:
    _type = globals.TYPE_MAPPING.get(val_type)
    if _type is None:
        raise ValueError(f"Invalid value type: {val_type}")
    return _type


def arcade_schema_to_pydantic(tool_def: ToolDefinition) -> type[BaseModel]:
    try:
        fields: dict[str, Any] = {}
        for param in tool_def.input.parameters or []:
            param_type = get_python_type(param.value_schema.val_type)
            if param_type is list and param.value_schema.inner_val_type:
                inner_type: type[Any] = get_python_type(param.value_schema.inner_val_type)
                param_type = list[inner_type]
            param_description = param.description or "No description provided."
            default = ... if param.required else None
            fields[param.name] = (
                param_type,
                Field(default=default, description=param_description),
            )
        return create_model(f"{tool_def.name}Args", **fields)
    except ValueError as e:
        raise ValueError(
            f"Error converting {tool_def.name} parameters into pydantic model for langchain: {e}"
        )


async def arcade_to_langchain(
    arcade_client: AsyncArcade,
    arcade_tool: ToolDefinition,
) -> StructuredTool:
    # Convert Arcade schema to Pydantic model
    args_schema = arcade_schema_to_pydantic(arcade_tool)

    # Create the executor function with interrupt handling
    async def tool_function(config: RunnableConfig, **kwargs: Any) -> Any:
        user_id = config.get("configurable", {}).get("user_id") if config else None
        if not user_id:
            raise ValueError("User ID is required to execute Arcade tools")

        auth_response = await arcade_client.tools.authorize(
            tool_name=arcade_tool.qualified_name,
            user_id=user_id
        )

        if auth_response.status != "completed":
            # Interrupt the agent to handle authorization
            interrupt_result = interrupt({
                "type": "authorization_required",
                "tool_name": arcade_tool.qualified_name,
                "auth_response": {
                    "id": auth_response.id,
                    "url": auth_response.url,
                }
            })

            # Resume the flow with the authorization decision
            authorized = interrupt_result.get("authorized")
            if not authorized:
                raise RuntimeError(
                    f"Authorization was not completed for tool {arcade_tool.name}"
                )

        # Filter out None values to avoid passing unset optional parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        response = await arcade_client.tools.execute(
            tool_name=arcade_tool.qualified_name,
            input=filtered_kwargs,
            user_id=user_id,
        )

        if response.output and response.output.value:
            return response.output.value

        error_details = {
            "error": "Unknown error occurred",
            "tool": arcade_tool.qualified_name,
        }

        if response.output is not None and response.output.error is not None:
            error = response.output.error
            error_message = str(error.message) if hasattr(error, "message") else "Unknown error"
            error_details["error"] = error_message

            # Add all non-None optional error fields to the details
            for field in ["additional_prompt_content", "can_retry", "developer_message", "retry_after_ms"]:
                if (value := getattr(error, field, None)) is not None:
                    error_details[field] = str(value)

        return error_details

    # Create and return the LangChain StructuredTool
    return StructuredTool.from_function(
        coroutine=tool_function,
        name=arcade_tool.qualified_name.replace(".", "_"),
        description=arcade_tool.description,
        args_schema=args_schema
    )


async def get_arcade_tools(
    arcade_client: AsyncArcade | None = None,
    mcp_servers: List[str] | None = None,
    tools: List[str] | None = None,
    tool_limit: int = globals.TOOL_LIMIT,
) -> List[StructuredTool]:

    if not arcade_client:
        arcade_client = AsyncArcade(api_key=globals.ARCADE_API_KEY)

    # if no tools or MCP servers are provided, raise an error
    if not tools and not mcp_servers:
        raise ValueError(
            "No tools or MCP servers provided to retrieve tool definitions")

    # Collect tool definitions, using qualified name as key to avoid duplicates
    tool_definitions: dict[str, ToolDefinition] = {}

    # Retrieve individual tools if specified
    if tools:
        tasks = [arcade_client.tools.get(name=tool_name) for tool_name in tools]
        responses = await asyncio.gather(*tasks)
        for response in responses:
            tool_definitions[response.fully_qualified_name] = response

    # Retrieve tools from specified toolkits
    if mcp_servers:
        tasks = [arcade_client.tools.list(toolkit=mcp_server, limit=tool_limit) for mcp_server in mcp_servers]
        responses = await asyncio.gather(*tasks)

        # Combine the tool definitions from each response.
        for response in responses:
            for tool in response.items:
                tool_definitions[tool.fully_qualified_name] = tool

    tasks = [arcade_to_langchain(arcade_client, tool_definition) for tool_definition in tool_definitions.values()]
    langchain_tools = await asyncio.gather(*tasks)
    return langchain_tools
