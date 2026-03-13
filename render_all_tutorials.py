"""Batch render all tutorials from agent configurations and generate a manifest."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from tutorial_renderer import render_tutorial

console = Console()

REPO_ROOT = Path(__file__).parent
TEMPLATES_DIR = REPO_ROOT / "templates"
CONFIGS_DIR = REPO_ROOT / "agent-configurations"
OUTPUT_DIR = REPO_ROOT / "rendered-tutorials"


def get_source_commit() -> str:
    """Get the current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def render_all_tutorials() -> list[dict]:
    """Render tutorials for every config and return manifest entries."""
    entries = []
    errors = []

    for template_dir in sorted(TEMPLATES_DIR.iterdir()):
        if not template_dir.is_dir():
            continue

        template_name = template_dir.name
        tutorial_path = template_dir / "tutorial.md"
        if not tutorial_path.exists():
            console.print(
                f"[dim]Skipping {template_name} (no tutorial.md)[/dim]"
            )
            continue

        config_dir = CONFIGS_DIR / template_name
        if not config_dir.exists():
            console.print(
                f"[dim]Skipping {template_name} (no configs)[/dim]"
            )
            continue

        for config_file in sorted(config_dir.glob("*.json")):
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON: {config_file}: {e}")
                continue

            console.print(
                f"Rendering: {template_name}/{config_file.stem}...",
                end=" ",
            )

            try:
                rendered = render_tutorial(
                    template_dir=template_dir,
                    code_dir=REPO_ROOT / "real_agents" / template_name / config_file.stem,
                    context=config,
                )
            except Exception as e:
                errors.append(f"Render failed: {template_name}/{config_file.stem}: {e}")
                console.print("[red]FAILED[/red]")
                continue

            if rendered is None:
                console.print("[yellow]skipped[/yellow]")
                continue

            # Write rendered tutorial
            out_dir = OUTPUT_DIR / template_name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{config_file.stem}.md"
            out_file.write_text(rendered, encoding="utf-8")
            console.print("[green]OK[/green]")

            # Build manifest entry from frontmatter
            toolkits = config.get("arcade_toolkit_list", [])
            toolkit_slug = toolkits[0].lower().replace(" ", "-") if toolkits else "custom"

            # Derive slug from template name pattern
            slug_prefix = template_name.replace("_", "-")
            slug = f"{slug_prefix}-{toolkit_slug}"

            agent_name = config.get("agent_name") or (f"{toolkits[0]} Agent" if toolkits else "Agent")
            entries.append({
                "title": f"Build a {agent_name} with {_framework_label(template_name)} and Arcade",
                "slug": slug,
                "framework": _framework_id(template_name),
                "language": _language(template_name),
                "toolkits": toolkits,
                "file": f"tutorials/{template_name}/{config_file.stem}.md",
            })

    if errors:
        console.print(f"\n[red]{len(errors)} error(s):[/red]")
        for err in errors:
            console.print(f"  [red]- {err}[/red]")

    return entries


def _framework_id(template_name: str) -> str:
    mapping = {
        "py_crewai": "crewai",
        "py_langchain": "langchain",
        "py_google_adk": "google-adk",
        "py_openai_agents_sdk": "openai-agents-sdk",
        "ts_langchain": "langchain-ts",
    }
    return mapping.get(template_name, template_name)


def _framework_label(template_name: str) -> str:
    mapping = {
        "py_crewai": "CrewAI",
        "py_langchain": "LangChain",
        "py_google_adk": "Google ADK",
        "py_openai_agents_sdk": "OpenAI Agents SDK",
        "ts_langchain": "LangChain (TypeScript)",
    }
    return mapping.get(template_name, template_name)


def _language(template_name: str) -> str:
    return "typescript" if template_name.startswith("ts_") else "python"


def main():
    console.print("[bold]Rendering all tutorials...[/bold]\n")

    entries = render_all_tutorials()

    # Generate manifest
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": get_source_commit(),
        "tutorials": entries,
    }

    manifest_path = OUTPUT_DIR / "tutorials-manifest.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    console.print(f"\n[bold green]Done![/bold green] {len(entries)} tutorials rendered.")
    console.print(f"Manifest: {manifest_path}")

    return 0 if entries else 1


if __name__ == "__main__":
    sys.exit(main())
