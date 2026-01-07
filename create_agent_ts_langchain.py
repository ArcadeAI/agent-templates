import argparse
import json
from pathlib import Path
from render_utils import create_agent
from rich import print

template_dir = Path(__file__).parent / "ts_langchain"
output_dir = Path(__file__).parent / "real_agents" / "ts_langchain"

parser = argparse.ArgumentParser(
    description="Create a TypeScript LangChain agent from a JSON configuration."
)
parser.add_argument(
    "config",
    type=Path,
    help="Path to a JSON config file (e.g. agent-configurations/langchain/gmail-slack.json)",
)
args = parser.parse_args()

config_path = args.config.expanduser()
try:
    configuration = json.loads(config_path.read_text())
except FileNotFoundError as e:
    raise SystemExit(f"Config file not found: {config_path}") from e
except json.JSONDecodeError as e:
    raise SystemExit(f"Invalid JSON in config file: {config_path}\n{e}") from e

if not isinstance(configuration, dict):
    raise SystemExit(f"Config JSON must be an object/dict at top-level: {config_path}")

output_dir = output_dir / config_path.stem
print("Creating agent with configuration:")
print(configuration)

create_agent(output_dir, template_dir, configuration)
