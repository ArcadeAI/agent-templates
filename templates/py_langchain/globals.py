from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

ARCADE_API_KEY = os.getenv("ARCADE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ARCADE_USER_ID = os.getenv("ARCADE_USER_ID")
{%- if arcade_tool_list %}
TOOLS = {{ arcade_tool_list | safe }}
{%- else %}
TOOLS = None
{%- endif %}
{%- if arcade_toolkit_list %}
MCP_SERVERS = {{ arcade_toolkit_list | safe }}
{%- else %}
MCP_SERVERS = None
{%- endif %}
TOOL_LIMIT = 30
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
AGENT_NAME = "{{ agent_name | safe }}"
SYSTEM_PROMPT = """
{{ agent_instruction | safe }}
"""
ENFORCE_HUMAN_CONFIRMATION = {{ tools_with_human_confirmation | safe }}

TYPE_MAPPING = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "json": dict,
}
