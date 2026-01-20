from arcadepy import AsyncArcade
from google.adk.tools import ToolContext
from pprint import pp
from typing import Any
from globals import ENFORCE_HUMAN_CONFIRMATION
from tools import ArcadeTool


async def confirm_tool_usage(tool: ArcadeTool,
                             args: Any,
                             tool_context: ToolContext) -> None | str:
    """
    Ask the user to confirm the use of a specific tool

    Args:
        context: OpenAI Agents SDK run context
        tool_args: parameters for the function, JSON as a string.
        tool_name: the name of the tool that we want to call
        callable: the function that we should call if approved

    Returns:
        None | str:
            None if the user approved the tool call, allowing the agent to
            continue

            A string with a denial message that will be passed to the LLM
            in case the user does not approve the tool call
    """
    # only applicable to tools we want to enforce confirmation for
    if tool.name not in ENFORCE_HUMAN_CONFIRMATION:
        return
    print("\nThe agent requires permission:\n"
          f"I'm about to call {tool.name} with these arguments:")
    # pp(json.loads(args))
    pp(args)
    clarification = input("Your response [y/n]: ")
    while clarification.lower() not in ["y", "n"]:
        clarification = input("Your response (must be either y or n): ")
    if clarification.lower() == "y":
        return
    return (f"The user denied permission to call {tool.name}"
            " with these arguments")


async def auth_tool(client: AsyncArcade, tool_name: str, user_id: str):
    result = await client.tools.authorize(tool_name=tool_name, user_id=user_id)
    if result.status != "completed":
        print(f"Click this link to authorize {tool_name}:\n{result.url}")
    await client.auth.wait_for_completion(result)
