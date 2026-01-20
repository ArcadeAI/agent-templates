from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

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
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
AGENT_NAME = "{{ agent_name | safe }}"
SYSTEM_PROMPT = """
{{ agent_instruction | safe }}
"""
ENFORCE_HUMAN_CONFIRMATION = {{ tools_with_human_confirmation | safe }}
