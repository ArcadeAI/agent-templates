from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

ARCADE_USER_ID = os.getenv("ARCADE_USER_ID")
MCP_SERVERS = ["Slack", "Math"]
TOOLS = ["Gmail_ListEmails", "Gmail_SendEmail", "Gmail_WhoAmI"]
TOOL_LIMIT = 30
MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = "You are a helpful assistant that can assist with Gmail and Slack."
AGENT_NAME = "Awesome Agent"
ENFORCE_HUMAN_CONFIRMATION = ["Gmail_SendEmail",]
