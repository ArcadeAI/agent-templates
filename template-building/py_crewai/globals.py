from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

ARCADE_USER_ID = os.getenv("ARCADE_USER_ID")
MCP_SERVERS = ["Slack"]
TOOLS = ["Gmail_ListEmails", "Gmail_SendEmail", "Gmail_WhoAmI"]
TOOL_LIMIT = 30
MODEL = "openai/gpt-4o-mini"
AGENT_GOAL = "Help the user with all their requests"
AGENT_BACKSTORY = "You are a helpful assistant that can assist with Gmail and Slack."
AGENT_NAME = "AwesomeAgent"
ENFORCE_HUMAN_CONFIRMATION = ["Gmail_SendEmail",]
