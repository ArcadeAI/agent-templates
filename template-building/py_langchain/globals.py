from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

ARCADE_API_KEY = os.getenv("ARCADE_API_KEY")
ARCADE_USER_ID = os.getenv("ARCADE_USER_ID")
MCP_SERVERS = ["Slack", "Math"]
TOOLS = ["Gmail_ListEmails", "Gmail_SendEmail", "Gmail_WhoAmI"]
TOOL_LIMIT = 30
MODEL = "gpt-5-mini"
SYSTEM_PROMPT = "You are a helpful assistant that can assist with Gmail and Slack."
AGENT_NAME = "Awesome Agent"
ENFORCE_HUMAN_CONFIRMATION = ["Gmail_SendEmail",]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TYPE_MAPPING = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "json": dict,
}
