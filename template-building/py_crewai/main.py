from arcadepy import Arcade
from crewai import Agent
from crewai.events.event_listener import EventListener
from dotenv import load_dotenv

from tools import get_arcade_tools
import globals

load_dotenv()

# Suppress CrewAI's rich panel output
EventListener().formatter.verbose = False


def main():
    client = Arcade()

    arcade_tools = get_arcade_tools(
        client,
        tools=globals.TOOLS,
        mcp_servers=globals.MCP_SERVERS,
        user_id=globals.ARCADE_USER_ID,
    )

    agent = Agent(
        role=globals.AGENT_NAME,
        goal=globals.AGENT_GOAL,
        backstory=globals.AGENT_BACKSTORY,
        tools=arcade_tools,
    )

    history = []
    print("Agent ready. Type 'exit' to quit.\n")

    while True:
        user_input = input("> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break

        history.append({"role": "user", "content": user_input})
        result = agent.kickoff(history)
        history.append({"role": "assistant", "content": result.raw})
        print(f"\n{result.raw}\n")


if __name__ == "__main__":
    main()
