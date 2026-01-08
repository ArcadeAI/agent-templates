# Arcade agent templates

CLI to scaffold agents from Jinja2 templates and JSON configs.

All generated agents use [Arcade](https://arcade.dev) as the tool runtime. Arcade handles auth and execution for external service integrations (Gmail, Slack, GitHub, etc.), so agents get tool access without managing OAuth flows or API keys directly.

## Structure

```
templates/             # Jinja2 templates (ts_langchain, python_openai_agents_sdk, etc.)
agent-configurations/  # JSON configs organized by template type
real_agents/           # Generated output
```

## Usage

```bash
python create_agent.py <config_path> [--template <name>] [--output-dir <path>]
```

Template is inferred from config's parent directory if not specified.

The `--output-dir` flag allows you to specify a custom output directory. If not provided, the agent will be created at `real_agents/<template>/<config_stem>/` where `<config_stem>` is the config filename without extension.

## Example

```bash
# Generate a ts_langchain agent from a config
python create_agent.py agent-configurations/ts_langchain/gmail-slack.json
```

This reads `gmail-slack.json`, applies values to the `ts_langchain` template, and outputs to `real_agents/ts_langchain/gmail-slack/`.

## Config Format

```json
{
  "arcade_tool_list": ["Gmail_ListEmails", "Gmail_SendEmail"],
  "arcade_toolkit_list": ["Slack", "gmail"],
  "agent_instruction": "Your system prompt here",
  "agent_description": "Short description"
}
```

Config keys become Jinja2 variables in templates.
