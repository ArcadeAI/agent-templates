from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage
import globals

load_dotenv()


async def main():
    app_name = globals.AGENT_NAME
    user_id = globals.ARCADE_USER_ID

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client,
        tools=globals.TOOLS,
        mcp_servers=globals.MCP_SERVERS
    )

    for tool in arcade_tools:
        await auth_tool(client, tool_name=tool.original_name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=globals.MODEL),
        name=globals.AGENT_NAME,
        instruction=globals.SYSTEM_PROMPT,
        description=globals.AGENT_NAME,
        tools=arcade_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
