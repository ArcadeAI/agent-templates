"""Tutorial rendering with snippet extraction from generated code."""

import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console

from render_utils import create_agent
from tutorial_utils import get_snippet, SNIPPET_OPEN_RE

console = Console()

# Regex matching {% snippet "file.py" %} or {% snippet "file.py" name="x" %} or {% snippet "file.py" lines="1-5" %}
SNIPPET_TAG_RE = re.compile(
    r'\{%[-\s]*snippet\s+"(?P<file>[^"]+)"'
    r'(?:\s+name="(?P<name>[^"]+)")?'
    r'(?:\s+lines="(?P<lines>[^"]+)")?'
    r'\s*[-\s]*%\}'
)

# Map file extensions to markdown language identifiers
LANG_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".js": "javascript",
    ".toml": "toml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".env": "bash",
}


def _detect_language(filename: str) -> str:
    """Detect the markdown code fence language from a filename."""
    suffix = Path(filename).suffix
    return LANG_MAP.get(suffix, "")


def _resolve_snippets(template_content: str, code_dir: Path) -> str:
    """Pre-process tutorial template to resolve {% snippet %} tags.

    Replaces each {% snippet "file" name="x" %} with a fenced code block
    containing the extracted snippet.
    """

    def replacer(match: re.Match) -> str:
        filename = match.group("file")
        name = match.group("name")
        lines = match.group("lines")

        filepath = code_dir / filename
        if not filepath.exists():
            console.print(
                f"[yellow]Warning: snippet file not found: {filepath}[/yellow]"
            )
            return f"````\n<!-- File not found: {filename} -->\n````"

        content = filepath.read_text(encoding="utf-8")
        snippet = get_snippet(content, name=name, lines=lines)
        lang = _detect_language(filename)
        return f"````{lang}\n{snippet}````"

    return SNIPPET_TAG_RE.sub(replacer, template_content)


def _code_dir_has_markers(code_dir: Path) -> bool:
    """Check if a code directory has snippet markers in any source file."""
    for ext in ("*.py", "*.ts", "*.js"):
        for filepath in code_dir.glob(ext):
            content = filepath.read_text(encoding="utf-8")
            if SNIPPET_OPEN_RE.search(content):
                return True
    return False


def _render_code_to_temp(template_dir: Path, context: dict) -> Path:
    """Render code templates to a temporary directory (with markers intact)."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="tutorial_code_"))
    create_agent(str(tmp_dir), template_dir, context)
    return tmp_dir


def render_tutorial(
    template_dir: Path,
    code_dir: Path,
    context: dict,
    *,
    tutorial_filename: str = "tutorial.md",
) -> Optional[str]:
    """Render a tutorial template using generated code for snippet extraction.

    Args:
        template_dir: Path to the template directory (e.g. templates/py_crewai/).
        code_dir: Path to the rendered agent code (e.g. real_agents/py_crewai/github/).
            If the code_dir doesn't exist or lacks snippet markers, a fresh render
            is done to a temp directory.
        context: Template variables (from the JSON config).
        tutorial_filename: Name of the tutorial template file.

    Returns:
        The rendered tutorial markdown string, or None if no tutorial template exists.
    """
    tutorial_path = template_dir / tutorial_filename
    if not tutorial_path.exists():
        return None

    # Determine where to read code snippets from.
    # If code_dir doesn't exist or lacks markers, render a fresh copy.
    tmp_dir = None
    snippet_dir = code_dir
    if not code_dir.exists() or not _code_dir_has_markers(code_dir):
        tmp_dir = _render_code_to_temp(template_dir, context)
        snippet_dir = tmp_dir

    try:
        # Read the raw tutorial template
        raw_template = tutorial_path.read_text(encoding="utf-8")

        # Pass 1: Resolve snippet tags using rendered code
        resolved = _resolve_snippets(raw_template, snippet_dir)

        # Pass 2: Render Jinja2 variables in the tutorial
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Add computed context variables for tutorials
        tutorial_context = {
            **context,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        tutorial_context["agent_slug"] = code_dir.name

        # Derive agent_name if not in config (e.g. TS templates don't have it)
        toolkits = context.get("arcade_toolkit_list", [])
        if not tutorial_context.get("agent_name"):
            if toolkits:
                tutorial_context["agent_name"] = f"{toolkits[0]} Agent"
            else:
                tutorial_context["agent_name"] = "Agent"

        # Add agent_repo_url placeholder (will be set by sync system)
        if "agent_repo_url" not in tutorial_context:
            tutorial_context["agent_repo_url"] = ""

        def natural_join(items):
            if len(items) == 1:
                return items[0]
            return f"{', '.join(items[:-1])} and {items[-1]}"

        env.filters["natural_join"] = natural_join

        template = env.from_string(resolved)
        rendered = template.render(tutorial_context)

        return rendered
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir)
