import re
from pathlib import Path
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console

console = Console()


def render_template(env: Environment, template_string: str, context: dict) -> str:
    """Render a template string with the given variables."""
    template = env.from_string(template_string)
    return template.render(context)


def write_template(path: Path, content: str) -> None:
    """Write content to a file."""
    path.write_text(content, encoding="utf-8")


def create_ignore_pattern(
    include_evals: bool, is_community_or_official_toolkit: bool
) -> re.Pattern[str]:
    """Create an ignore pattern based on user preferences."""
    patterns = [
        "__pycache__",
        r"\.DS_Store",
        r"Thumbs\.db",
        r"\.git",
        r"\.svn",
        r"\.hg",
        r"\.vscode",
        r"\.idea",
        "build",
        "dist",
        r".*\.egg-info",
        r".*\.pyc",
        r".*\.pyo",
    ]

    if not include_evals:
        patterns.append("evals")

    if not is_community_or_official_toolkit:
        patterns.extend([".ruff.toml", ".pre-commit-config.yaml", "LICENSE"])
    else:
        patterns.extend(["README.md"])

    return re.compile(f"({'|'.join(patterns)})$")


def create_package(
    env: Environment,
    template_path: Path,
    output_path: Path,
    context: dict,
    ignore_pattern: re.Pattern[str],
) -> None:
    """Recursively create a new toolkit directory structure from jinja2 templates."""
    if ignore_pattern.match(template_path.name):
        return

    try:
        if template_path.is_dir():
            folder_name = render_template(env, template_path.name, context)
            new_dir_path = output_path / folder_name
            new_dir_path.mkdir(parents=True, exist_ok=True)

            for item in template_path.iterdir():
                create_package(env, item, new_dir_path, context, ignore_pattern)

        else:
            # Render the file name
            file_name = render_template(env, template_path.name, context)
            print(file_name)
            with open(template_path, encoding="utf-8") as f:
                content = f.read()
            # Render the file content
            content = render_template(env, content, context)

            write_template(output_path / file_name, content)
    except Exception as e:
        console.print(f"[red]Failed to create package: {e}[/red]")
        raise


def create_agent(output_directory: str, template_dir: Path, context: dict) -> None:
    """Create a new toolkit from a template with user input."""
    toolkit_directory = Path(output_directory)
    toolkit_directory.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    ignore_pattern = create_ignore_pattern(False, False)

    try:
        # Iterate over template_dir contents directly to avoid creating
        # a nested subdirectory with the template folder's name
        for item in template_dir.iterdir():
            create_package(env, item, toolkit_directory, context, ignore_pattern)
        console.print(
            f"[green]Agent created successfully at '{toolkit_directory}'.[/green]"
        )
    except Exception:
        shutil.rmtree(toolkit_directory)
        raise
