from agents import Agent, Runner, TResponseInputItem
from agents.run_context import RunContextWrapper
from agents.tool import FunctionTool
from agents.exceptions import AgentsException
from arcadepy import AsyncArcade
from arcadepy.types.execute_tool_response import ExecuteToolResponse
from functools import partial
from typing import Any
import asyncio
import json
import globals


# Arcade to OpenAI agent exception classes
class ToolError(AgentsException):
    def __init__(self, result: ExecuteToolResponse):
        self.result = result

    @property
    def message(self):
        return self.result.output.error.message

    def __str__(self):
        return f"Tool {self.result.tool_name} failed with error: {self.message}"


def convert_output_to_json(output: Any) -> str:
    if isinstance(output, dict) or isinstance(output, list):
        return json.dumps(output)
    else:
        return str(output)


async def authorize_tool(client: AsyncArcade, context: RunContextWrapper, tool_name: str):
    if not context.context.get("user_id"):
        raise ToolError("No user ID and authorization required for tool")

    result = await client.tools.authorize(
        tool_name=tool_name,
        user_id=context.context.get("user_id"),
    )

    if result.status != "completed":
        print(f"{tool_name} requires authorization to run, please open the following URL to authorize: {result.url}")

        await client.auth.wait_for_completion(result)


async def invoke_arcade_tool(
    context: RunContextWrapper,
    tool_args: str,
    tool_name: str,
    client: AsyncArcade,
):
    args = json.loads(tool_args)
    await authorize_tool(client, context, tool_name)

    print(f"Invoking tool {tool_name} with args: {args}")
    result = await client.tools.execute(
        tool_name=tool_name,
        input=args,
        user_id=context.context.get("user_id"),
    )
    if not result.success:
        raise ToolError(result)

    print(f"Tool {tool_name} called successfully, {globals.MODEL} will now process the result...")

    return convert_output_to_json(result.output.value)


async def get_arcade_tools(
    client: AsyncArcade | None = None,
    tools: list[str] | None = None,
    mcp_servers: list[str] | None = None,
) -> list[FunctionTool]:

    if not client:
        client = AsyncArcade()

    # if no tools or MCP servers are provided, raise an error
    if not tools and not mcp_servers:
        raise ValueError(
            "No tools or MCP servers provided to retrieve tool definitions")

    # Use the Arcade Client to get OpenAI-formatted tool definitions
    tool_formats = []

    # Retrieve individual tools if specified
    if tools:
        # OpenAI-formatted tool definition
        tasks = [client.tools.formatted.get(name=tool_id, format="openai")
                 for tool_id in tools]
        responses = await asyncio.gather(*tasks)
        for response in responses:
            tool_formats.append(response)

    # Retrieve tools from specified toolkits
    if mcp_servers:
        # Create a task for each toolkit to fetche the formatted tool definition concurrently.
        tasks = [client.tools.formatted.list(toolkit=tk, format="openai")
                 for tk in mcp_servers]
        responses = await asyncio.gather(*tasks)

        # Combine the tool definitions from each response.
        for response in responses:
            # Here we assume the returned response has an "items" attribute
            # containing a list of ToolDefinition objects.
            tool_formats.extend(response.items)

    # Create a list of FunctionTool objects, mapping each tool to a partial function that invokes the tool via the Arcade client.
    tool_functions = []
    for tool in tool_formats:
        tool_name = tool["function"]["name"]
        tool_description = tool["function"]["description"]
        tool_params = tool["function"]["parameters"]
        tool_function = FunctionTool(
            name=tool_name,
            description=tool_description,
            params_json_schema=tool_params,
            on_invoke_tool=partial(
                invoke_arcade_tool,
                tool_name=tool_name,
                client=client,
            ),
            strict_json_schema=False,
        )
        tool_functions.append(tool_function)

    return tool_functions
