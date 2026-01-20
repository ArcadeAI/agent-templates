# {{ agent_description }}

## Purpose

{{ agent_instruction | safe }}

{%- if arcade_tool_list %}
## Tools

This agent has access to the following Arcade tools:
{% for tool in arcade_tool_list %}
- `{{ tool }}`
{%- endfor %}
{%- endif %}
{%- if arcade_tool_list %}
## MCP Servers

The agent uses tools from these Arcade MCP Servers:
{% for toolkit in arcade_toolkit_list %}
- {{ toolkit }}
{%- endfor %}
{%- endif %}
{%- if tools_with_human_confirmation %}

## Human-in-the-Loop Confirmation

The following tools require human confirmation before execution:
{% for tool in tools_with_human_confirmation %}
- `{{ tool }}`
{%- endfor %}
{% endif %}

## Getting Started

1. Create an and activate a virtual environment
    ```bash
    uv venv
    source .venv/bin/activate
    ```

2. Set your environment variables:

    Copy the `.env.example` file to create a new `.env` file, and fill in the environment variables.
    ```bash
    cp .env.example .env
    ```

3. Run the agent:
    ```bash
    uv run main.py
    ```
