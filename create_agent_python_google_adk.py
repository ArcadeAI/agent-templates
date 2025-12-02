from pathlib import Path
from render_utils import create_agent

template_dir = Path(__file__).parent / "python_google_adk"
output_dir = Path(__file__).parent / "real_agents"

configuration = {
    "arcade_tool_list": [
        "Gmail_ListEmails",
        "Gmail_SendEmail"
    ],
    "arcade_toolkit_list": [
        "Slack",
    ],
    "tools_with_human_confirmation": [
        "Gmail_SendEmail",
        "Gmail_ListEmails"
    ],
    "agent_instruction": "You're a very useful assistant with access to Gmail and Slack tools, please use them to effectively do tasks requested by the user",
    "agent_description": "An agent with Gmail and Slack tools"
}

create_agent(output_dir, template_dir, configuration)
