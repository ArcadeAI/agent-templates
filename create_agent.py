import argparse
import json
from pathlib import Path
from render_utils import create_agent
from rich import print

# Mapping from configuration subdirectories to template names - NO LONGER NEEDED
# The configuration parent directory name now matches the template name.

def main():
    parser = argparse.ArgumentParser(
        description="Create an agent from a JSON configuration."
    )
    parser.add_argument(
        "config",
        type=Path,
        help="Path to a JSON config file (e.g. agent-configurations/ts_langchain/gmail-slack.json)",
    )
    parser.add_argument(
        "--template",
        type=str,
        help="The template to use. If not provided, it will be inferred from the config path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="The directory where the agent will be created. Defaults to real_agents/<template>/<config_stem>.",
    )

    args = parser.parse_args()

    config_path = args.config.expanduser()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    try:
        configuration = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in config file: {config_path}\n{e}")

    if not isinstance(configuration, dict):
        raise SystemExit(f"Config JSON must be an object/dict at top-level: {config_path}")

    # Determine the template
    template_name = args.template
    if not template_name:
        # Infer template from the parent directory name of the config file
        template_name = config_path.parent.name
        # Verify if it's a valid template (must exist in templates/)
        if not (Path(__file__).parent / "templates" / template_name).exists():
            # Check if the parent of the parent is agent-configurations
            if config_path.parent.parent.name != "agent-configurations":
                raise SystemExit(
                    f"Could not infer template from config path: {config_path}. "
                    "Please specify it with --template or place the config in agent-configurations/<template_name>/."
                )

    template_dir = Path(__file__).parent / "templates" / template_name
    if not template_dir.exists():
        raise SystemExit(f"Template directory not found: {template_dir}")

    # Determine the output directory
    output_dir = args.output_dir
    if not output_dir:
        output_dir = Path(__file__).parent / "real_agents" / template_name / config_path.stem

    print(f"Creating agent using template: [bold blue]{template_name}[/bold blue]")
    print(f"Config path: [yellow]{config_path}[/yellow]")
    print(f"Output directory: [green]{output_dir}[/green]")
    print("\nConfiguration:")
    print(configuration)
    print("")

    create_agent(output_dir, template_dir, configuration)

if __name__ == "__main__":
    main()

