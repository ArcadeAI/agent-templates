"""Snippet extraction and marker stripping utilities for tutorial generation."""

import re
from pathlib import Path
from typing import Optional


# Matches both Python (# [snippet:name]) and TypeScript (// [snippet:name]) markers
SNIPPET_OPEN_RE = re.compile(
    r"^\s*(?:#|//)\s*\[snippet:(?P<name>[a-zA-Z0-9_-]+)\]\s*$"
)
SNIPPET_CLOSE_RE = re.compile(
    r"^\s*(?:#|//)\s*\[/snippet:(?P<name>[a-zA-Z0-9_-]+)\]\s*$"
)
SNIPPET_MARKER_RE = re.compile(
    r"^[^\S\n]*(?:#|//)\s*\[/?snippet:[a-zA-Z0-9_-]+\][^\S\n]*\n?", re.MULTILINE
)


def get_snippet(
    file_content: str,
    *,
    name: Optional[str] = None,
    lines: Optional[str] = None,
) -> str:
    """Extract a snippet from file content.

    Args:
        file_content: The full file content to extract from.
        name: Named snippet marker to extract (e.g. "agent-setup").
        lines: Line range like "15-43" to extract.

    Returns:
        The extracted snippet content. If neither name nor lines is given,
        returns the entire file with snippet markers stripped.
    """
    if name:
        return _extract_named_snippet(file_content, name)
    if lines:
        return _extract_line_range(file_content, lines)
    # Return full file with markers stripped
    return strip_snippet_markers(file_content)


def _extract_named_snippet(content: str, name: str) -> str:
    """Extract content between [snippet:name] and [/snippet:name] markers."""
    file_lines = content.splitlines(keepends=True)
    capturing = False
    captured: list[str] = []

    for line in file_lines:
        open_match = SNIPPET_OPEN_RE.match(line)
        if open_match and open_match.group("name") == name:
            capturing = True
            continue

        close_match = SNIPPET_CLOSE_RE.match(line)
        if close_match and close_match.group("name") == name:
            break

        if capturing:
            captured.append(line)

    if not captured:
        raise ValueError(f"Snippet '{name}' not found in file content")

    # Dedent: find minimum indentation and strip it
    result = "".join(captured)
    return result.rstrip("\n") + "\n"


def _extract_line_range(content: str, lines: str) -> str:
    """Extract a range of lines like '15-43' (1-indexed, inclusive)."""
    parts = lines.split("-", 1)
    start = int(parts[0])
    end = int(parts[1]) if len(parts) > 1 else start

    file_lines = content.splitlines(keepends=True)
    # Convert to 0-indexed
    selected = file_lines[start - 1 : end]
    result = "".join(selected)
    return result.rstrip("\n") + "\n"


def strip_snippet_markers(content: str) -> str:
    """Remove all snippet marker lines from content."""
    return SNIPPET_MARKER_RE.sub("", content)


def strip_markers_in_directory(directory: Path) -> None:
    """Strip snippet markers from all source files in a directory (recursively).

    Processes .py, .ts, .js, and .tsx files.
    """
    extensions = {".py", ".ts", ".js", ".tsx"}

    for filepath in directory.rglob("*"):
        if filepath.suffix in extensions and filepath.is_file():
            original = filepath.read_text(encoding="utf-8")
            stripped = strip_snippet_markers(original)
            if stripped != original:
                filepath.write_text(stripped, encoding="utf-8")
