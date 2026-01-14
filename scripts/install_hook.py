#!/usr/bin/env python3
"""Install post-commit hook for agent sync automation."""

import os
from pathlib import Path


def install_hook():
    """Install post-commit hook."""
    # Find repository root
    repo_root = Path(__file__).parent.parent
    hook_path = repo_root / '.git' / 'hooks' / 'post-commit'

    # Create hook content
    hook_content = """#!/bin/bash
# Auto-generated post-commit hook for agent sync automation
# This hook automatically syncs agents when configs or templates change

python3 -m sync.sync_agents --hook-mode
"""

    # Write hook file
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(hook_content)

    # Make executable
    hook_path.chmod(0o755)

    print(f"✓ Installed post-commit hook at: {hook_path}")
    print(f"\nThe hook will automatically run after each commit.")
    print(f"To bypass the hook, use: git commit --no-verify")


if __name__ == '__main__':
    install_hook()
