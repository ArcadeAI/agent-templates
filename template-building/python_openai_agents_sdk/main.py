from agents import Agent, Runner, TResponseInputItem
from functools import partial
from arcadepy import AsyncArcade
from tools import get_arcade_tools, auth_tool
from hooks import CustomAgentHooks
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage)

import globals


async def main():

    context = {
        "user_id": globals.ARCADE_USER_ID,
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client,
        tools=globals.TOOLS,
        mcp_servers=globals.MCP_SERVERS
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in globals.ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name=globals.AGENT_NAME,
        instructions=globals.SYSTEM_PROMPT,
        model=globals.MODEL,
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name=globals.AGENT_NAME)
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
