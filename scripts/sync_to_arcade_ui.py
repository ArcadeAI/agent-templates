"""Sync rendered tutorials to the arcade-ui marketing site content directory.

Usage:
    # Sync everything
    python scripts/sync_to_arcade_ui.py --target-dir /path/to/arcade-ui

    # Sync only specific templates (framework level)
    python scripts/sync_to_arcade_ui.py --target-dir /path/to/arcade-ui --templates ts_langchain py_langchain

    # Sync only specific tutorials (by config name)
    python scripts/sync_to_arcade_ui.py --target-dir /path/to/arcade-ui --only ts-langchain-Github py-langchain-Slack

    # Combine both: all of ts_langchain plus one specific py_langchain tutorial
    python scripts/sync_to_arcade_ui.py --target-dir /path/to/arcade-ui --templates ts_langchain --only py-langchain-Slack

    # Dry run
    python scripts/sync_to_arcade_ui.py --target-dir /path/to/arcade-ui --templates ts_langchain --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDERED_DIR = REPO_ROOT / "rendered-tutorials"

FRAMEWORK_LABELS = {
    "crewai": "CrewAI",
    "langchain": "LangChain",
    "langchain-ts": "LangChain (TypeScript)",
    "google-adk": "Google ADK",
    "openai-agents-sdk": "OpenAI Agents SDK",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)


def extract_frontmatter(content: str) -> Tuple[str, str]:
    """Return (frontmatter_str, body) from a markdown file."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return "", content
    fm = match.group(1)
    body = content[match.end():]
    return fm, body


def build_description(title: str, toolkits: List[str], framework: str, language: str) -> str:
    """Synthesize an SEO description from tutorial metadata."""
    fw_label = FRAMEWORK_LABELS.get(framework, framework)
    if toolkits:
        toolkit_str = ", ".join(toolkits)
        return (
            f"Step-by-step {language.capitalize()} tutorial: build a {toolkit_str} "
            f"agent with {fw_label} and Arcade. Includes code examples, "
            f"authorization handling, and human-in-the-loop support."
        )
    return f"Build an AI agent with {fw_label} and Arcade. Full {language} tutorial with code examples."


def parse_yaml_field(frontmatter: str, field: str) -> Optional[str]:
    """Extract a simple scalar YAML field value."""
    for line in frontmatter.splitlines():
        if line.startswith(f"{field}:"):
            val = line[len(field) + 1:].strip().strip('"').strip("'")
            return val
    return None


def parse_yaml_list(frontmatter: str, field: str) -> List[str]:
    """Extract a JSON-style inline list from YAML frontmatter."""
    for line in frontmatter.splitlines():
        if line.startswith(f"{field}:"):
            val = line[len(field) + 1:].strip()
            if val.startswith("["):
                try:
                    return json.loads(val)
                except Exception:
                    return []
    return []


def add_description_to_frontmatter(frontmatter: str, description: str) -> str:
    """Insert a description field after the title field in frontmatter."""
    lines = frontmatter.splitlines(keepends=True)
    result = []
    for line in lines:
        result.append(line)
        if line.startswith("title:"):
            result.append(f'description: "{description}"\n')
    return "".join(result)


def update_slug_in_frontmatter(frontmatter: str, new_slug: str) -> str:
    """Replace the slug field value in frontmatter."""
    lines = frontmatter.splitlines(keepends=True)
    result = []
    for line in lines:
        if line.startswith("slug:"):
            result.append(f'slug: "{new_slug}"\n')
        else:
            result.append(line)
    return "".join(result)


def sync_tutorials(
    target_dir: Path,
    templates: Optional[List[str]] = None,
    only: Optional[List[str]] = None,
    dry_run: bool = False,
) -> int:
    """Sync rendered tutorials to the target content directory.

    Args:
        target_dir: Path to the arcade-ui repo root.
        templates: If set, only sync tutorials from these framework directories.
        only: If set, only sync tutorials matching these config stems (case-insensitive).
        dry_run: If True, print what would be done without writing.

    When both templates and only are provided, a tutorial is included if it
    matches either filter (union).

    Returns the number of files written.
    """
    content_dir = target_dir / "apps" / "web" / "src" / "content" / "tutorials"

    if not (target_dir / "apps" / "web").exists():
        print(f"Error: {target_dir}/apps/web does not exist. Is --target-dir correct?", file=sys.stderr)
        return 0

    if not dry_run:
        content_dir.mkdir(parents=True, exist_ok=True)

    # Normalize filters
    templates_set = {t.lower() for t in templates} if templates else None
    only_set = {o.lower() for o in only} if only else None

    slugs_seen = {}  # type: dict[str, str]
    written = 0
    skipped = 0
    warnings = []

    for framework_dir in sorted(RENDERED_DIR.iterdir()):
        if not framework_dir.is_dir():
            continue

        dir_name = framework_dir.name.lower()

        for md_file in sorted(framework_dir.glob("*.md")):
            stem_lower = md_file.stem.lower()

            # Apply filters (union: match either)
            if templates_set or only_set:
                matched_template = templates_set and dir_name in templates_set
                matched_only = only_set and stem_lower in only_set
                if not matched_template and not matched_only:
                    skipped += 1
                    continue

            content = md_file.read_text(encoding="utf-8")
            frontmatter, body = extract_frontmatter(content)

            if not frontmatter:
                warnings.append(f"No frontmatter: {md_file}")
                continue

            # Use lowercase filename stem as the unique slug
            slug = stem_lower

            if slug in slugs_seen:
                warnings.append(f"Slug collision: {slug} ({md_file.name} vs {slugs_seen[slug]})")
                continue
            slugs_seen[slug] = md_file.name

            # Extract metadata for description
            title = parse_yaml_field(frontmatter, "title") or slug
            framework = parse_yaml_field(frontmatter, "framework") or ""
            language = parse_yaml_field(frontmatter, "language") or ""
            toolkits = parse_yaml_list(frontmatter, "toolkits")

            # Build description and update frontmatter
            description = build_description(title, toolkits, framework, language)
            updated_fm = add_description_to_frontmatter(frontmatter, description)
            updated_fm = update_slug_in_frontmatter(updated_fm, slug)

            output = f"---\n{updated_fm}---\n{body}"
            out_file = content_dir / f"{slug}.md"

            if dry_run:
                print(f"  [dry-run] {md_file.relative_to(RENDERED_DIR)} -> {out_file.name}")
            else:
                out_file.write_text(output, encoding="utf-8")
                print(f"  {md_file.relative_to(RENDERED_DIR)} -> {out_file.name}")

            written += 1

    if skipped and (templates_set or only_set):
        print(f"\n  ({skipped} tutorials skipped by filter)")

    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    return written


def main():
    parser = argparse.ArgumentParser(description="Sync tutorials to arcade-ui")
    parser.add_argument("--target-dir", required=True, type=Path, help="Path to arcade-ui repo root")
    parser.add_argument("--templates", nargs="+", help="Only sync these template directories (e.g. ts_langchain py_langchain)")
    parser.add_argument("--only", nargs="+", help="Only sync these specific tutorials by config stem (e.g. ts-langchain-Github)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing files")
    args = parser.parse_args()

    print(f"Syncing tutorials to {args.target_dir}")
    if args.templates:
        print(f"  templates filter: {', '.join(args.templates)}")
    if args.only:
        print(f"  only filter: {', '.join(args.only)}")
    if args.dry_run:
        print("  (dry run)")
    print()

    count = sync_tutorials(
        args.target_dir,
        templates=args.templates,
        only=args.only,
        dry_run=args.dry_run,
    )
    print(f"\nDone: {count} tutorials {'would be' if args.dry_run else ''} synced.")


if __name__ == "__main__":
    main()
