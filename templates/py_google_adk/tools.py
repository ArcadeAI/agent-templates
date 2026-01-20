from typing import Any, Dict
from typing_extensions import override
from arcadepy import AsyncArcade
from arcadepy.types import ToolDefinition
from _utils import (
    _get_arcade_tool_formats,
    tool_definition_to_pydantic_model,
    get_arcade_client,
)
from _errors import AuthorizationError, ToolError
from google.adk.tools import ToolContext, FunctionTool
# TODO: This relies on "private" functions for schema adherence, update when
# stable for Google
from google.adk.tools._automatic_function_calling_util import (
    _map_pydantic_type_to_property_schema
)
from google.genai import types
from rich import print


async def _authorize_tool(client: AsyncArcade,
                          tool_context: ToolContext,
                          tool_name: str):
    if not tool_context.state.get("user_id"):
        raise ValueError("No user ID and authorization required for tool")

    result = await client.tools.authorize(
        tool_name=tool_name,
        user_id=tool_context.state.get("user_id"),
    )
    if result.status != "completed":
        raise AuthorizationError(result)


async def _async_invoke_arcade_tool(
    tool_context: ToolContext,
    tool_args: Dict,
    tool_name: str,
    requires_auth: bool,
    client: AsyncArcade,
) -> Dict:
    if requires_auth:
        await _authorize_tool(client, tool_context, tool_name)

    print(f"Executing tool: {tool_name} with args: {tool_args}")

    result = await client.tools.execute(
        tool_name=tool_name,
        input=tool_args,
        user_id=tool_context.state.get("user_id"),
    )

    if not result.success:
        raise ToolError(result)


    return result.output.value


class ArcadeTool(FunctionTool):
    def __init__(self,
                 name: str,
                 description: str,
                 schema: ToolDefinition,
                 client: AsyncArcade,
                 requires_auth: bool,
                 original_name: str | None = None):
        # original_name is used for Arcade API calls (may contain dots)
        # name is the sanitized version for OpenAI (no dots allowed)
        arcade_tool_name = original_name or name

        # define callable
        async def func(tool_context: ToolContext,
                       **kwargs: Any) -> Dict:
            return await _async_invoke_arcade_tool(
                tool_context=tool_context,
                tool_args=kwargs,
                tool_name=arcade_tool_name,  # Use original name for Arcade API
                requires_auth=requires_auth,
                client=client
            )
        func.__name__ = name.lower()
        func.__doc__ = description

        super().__init__(func)
        schema = schema.model_json_schema()
        _map_pydantic_type_to_property_schema(schema)
        self.schema = schema
        self.name = name  # Sanitized name for OpenAI
        self.original_name = arcade_tool_name  # Original name for Arcade
        self.description = description
        self.client = client
        self.requires_auth = requires_auth
        self._arcade_tool_name = arcade_tool_name

    @override
    async def run_async(self, *, args: Dict[str, Any], tool_context: ToolContext) -> Any:
        """Override run_async to directly pass args to Arcade tool execution.
        
        The base FunctionTool filters args based on function signature, which
        doesn't work well with **kwargs. We bypass that by calling the Arcade
        tool directly with the full args dict.
        """
        return await _async_invoke_arcade_tool(
            tool_context=tool_context,
            tool_args=args,
            tool_name=self._arcade_tool_name,
            requires_auth=self.requires_auth,
            client=self.client,
        )

    @override
    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(
            parameters=types.Schema(
                type='OBJECT',
                properties=self.schema["properties"],
            ),
            description=self.description,
            name=self.name,
        )


async def get_arcade_tools(
    client: AsyncArcade | None = None,
    tools: list[str] | None = None,
    toolkits: list[str] | None = None,
    raise_on_empty: bool = True,
    **kwargs: dict[str, Any],
) -> list[ArcadeTool]:
    """
    Asynchronously fetches tool definitions for each toolkit using client.tools.list,
    and returns a list of FuntionTool definitions that can be passed to OpenAI
    Agents

    Args:
        client: AsyncArcade client
        tools: Optional list of specific tool names to include.
        toolkits: Optional list of toolkit names to include all tools from.
        raise_on_empty: Whether to raise an error if no tools or toolkits are provided.
        kwargs: if a client is not provided, these parameters will initialize it

    Returns:
        Tool definitions to add to OpenAI's Agent SDK Agents
    """
    if not client:
        client = get_arcade_client(**kwargs)

    if not tools and not toolkits:
        if raise_on_empty:
            raise ValueError(
                "No tools or toolkits provided to retrieve tool definitions")
        return {}

    tool_formats = await _get_arcade_tool_formats(
        client,
        tools=tools,
        toolkits=toolkits,
        raise_on_empty=raise_on_empty)

    tool_functions = []
    for tool in tool_formats:
        requires_auth = bool(tool.requirements and tool.requirements.authorization)
        # Replace dots with underscores - OpenAI only allows ^[a-zA-Z0-9_-]+$ in tool names
        sanitized_name = tool.qualified_name.replace(".", "_")
        tool_function = ArcadeTool(
            name=sanitized_name,
            description=tool.description,
            schema=tool_definition_to_pydantic_model(tool),
            requires_auth=requires_auth,
            client=client,
            original_name=tool.qualified_name,  # Keep original for Arcade API calls
        )
        tool_functions.append(tool_function)

    return tool_functions
