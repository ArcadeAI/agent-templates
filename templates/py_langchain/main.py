import asyncio
from typing import Dict, Any, List

from arcadepy import AsyncArcade
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from tools import get_arcade_tools
import globals


async def handle_authorization_interrupt(
    interrupt_value: Dict[str, Any],
    arcade_client: AsyncArcade
) -> Dict[str, bool]:
    # Extract authorization context
    auth_response = interrupt_value.get("auth_response", {})
    auth_id = auth_response.get("id")
    auth_url = auth_response.get("url")
    tool_name = interrupt_value.get("tool_name")

    if not auth_id or not auth_url:
        print("❌ Authorization interrupt missing required context")
        return {"authorized": False}

    # Display authorization URL to user
    print(f"\n{'='*70}")
    print(f"🔐 Authorization Required for {tool_name}")
    print("\nPlease visit the following URL to authorize:")
    print(f"\n  {auth_url}\n")
    print("Waiting for authorization to complete...")
    print(f"{'='*70}\n")

    try:
        status_response = await arcade_client.auth.wait_for_completion(auth_id)

        if status_response.status == "completed":
            print("✅ Authorization completed successfully!\n")
            return {"authorized": True}
        else:
            print(f"❌ Authorization failed with status: {status_response.status}\n")
            return {"authorized": False}

    except Exception as e:
        print(f"❌ Error during authorization: {str(e)}\n")
        return {"authorized": False}


async def stream_agent_response(agent, input_data, config) -> List[Any]:
    interrupts = []

    async for chunk in agent.astream(input_data, config, stream_mode="updates"):
        # Check and collect interrupts
        if "__interrupt__" in chunk:
            interrupts.extend(chunk["__interrupt__"])

        # Display agent actions
        for node_name, node_output in chunk.items():
            if node_name == "__interrupt__":
                continue

            if "messages" in node_output:
                for msg in node_output["messages"]:
                    # Tool calls from the AI
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            print(f"🔧 Calling tool: {tool_call['name']}")

                    # Tool response - just acknowledge it, don't dump the content
                    elif isinstance(msg, ToolMessage):
                        print(f"   ✓ {msg.name} completed, processing output...")

                    # Final AI response text
                    elif isinstance(msg, AIMessage) and msg.content:
                        print(f"\n🤖 Assistant:\n{msg.content}")

    return interrupts


async def main():
    # Initialize Arcade client
    arcade = AsyncArcade()

    # Get tools
    all_tools = await get_arcade_tools(
        arcade_client=arcade,
        mcp_servers=globals.MCP_SERVERS,
        tools=globals.TOOLS
    )

    # Initialize LLM
    model = ChatOpenAI(
        model=globals.MODEL,
        api_key=globals.OPENAI_API_KEY,
    )

    # Create agent with memory checkpointer
    memory = MemorySaver()
    agent = create_agent(
        system_prompt=globals.SYSTEM_PROMPT,
        model=model,
        tools=all_tools,
        checkpointer=memory
    )

    print(f"\n🤖 Agent created with {len(all_tools)} tools")
    print("Type 'quit' or 'exit' to end the conversation.\n")
    print("="*70)

    # Configuration for agent execution
    config = {
        "configurable": {
            "thread_id": "conversation_thread",
            "user_id": globals.ARCADE_USER_ID
        }
    }

    # Interactive conversation loop
    while True:
        # Get user input
        try:
            user_message = input("\n💬 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye!")
            break

        # Check for exit commands
        if not user_message:
            continue
        if user_message.lower() in ("quit", "exit", "q"):
            print("\n👋 Goodbye!")
            break

        print("="*70)

        # Start with user message
        current_input = {"messages": [{"role": "user", "content": user_message}]}

        # Agent execution loop with interrupt handling
        while True:
            print("\n🔄 Running agent...\n")

            interrupts = await stream_agent_response(agent, current_input, config)

            # Handle interrupts if any occurred
            if interrupts:
                print(f"\n⚠️  Detected {len(interrupts)} interrupt(s)\n")

                # Process each interrupt
                for interrupt_obj in interrupts:
                    interrupt_type = interrupt_obj.value.get("type")

                    if interrupt_type == "authorization_required":
                        # Handle authorization interrupt
                        decision = await handle_authorization_interrupt(
                            interrupt_obj.value,
                            arcade
                        )

                        # Resume agent with authorization decision
                        current_input = Command(resume=decision)
                        break  # Continue to next iteration
                    else:
                        print(f"❌ Unknown interrupt type: {interrupt_type}")
                        break
                else:
                    # All interrupts processed without break
                    break
            else:
                # No interrupts - agent completed successfully
                print("\n✅ Response complete!")
                break

        print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
