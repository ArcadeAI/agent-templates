from agents import AgentsException, RunContextWrapper
from pprint import pp
import json


class UserDeniedToolCall(AgentsException):
    """Exception raised when an user denies a tool call"""

    message: str

    def __init__(self, message: str):
        self.message = message


async def confirm_tool_usage(context: RunContextWrapper,
                             tool_args: str,
                             tool_name: str,
                             callback) -> str:
    """
    Ask the user to confirm the use of a specific tool

    Args:
        context: OpenAI Agents SDK run context
        tool_args: parameters for the function, JSON as a string.
        tool_name: the name of the tool that we want to call
        callable: the function that we should call if approved

    Returns:
        str: The output of the tool call
    """
    print("\nThe agent requires permission:\n"
          f"I'm about to call {tool_name} with these arguments:")
    pp(json.loads(tool_args))
    clarification = input("Your response [y/n]: ")
    while clarification.lower() not in ["y", "n"]:
        clarification = input("Your response (must be either y or n): ")
    if clarification.lower() == "y":
        return await callback(context, tool_args)
    raise UserDeniedToolCall(tool_name)


