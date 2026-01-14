"""Detect changes in git commits to determine what needs syncing."""

import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detect and categorize git changes."""

    def __init__(self, repo_root: Path):
        """Initialize change detector.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root

    def get_changed_files(self) -> List[Tuple[str, str]]:
        """Get list of changed files between HEAD and HEAD~1.

        Returns:
            List of (status, filepath) tuples where status is A (added),
            M (modified), or D (deleted)
        """
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-status', 'HEAD~1', 'HEAD'],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )

            changes = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    status, filepath = parts
                    changes.append((status, filepath))

            return changes
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get git diff: {e}")
            return []

    def extract_template_from_path(self, config_path: str) -> str:
        """Extract template name from config file path.

        Args:
            config_path: Path like 'agent-configurations/ts_langchain/gmail-slack.json'

        Returns:
            Template name like 'ts_langchain'
        """
        parts = Path(config_path).parts
        if len(parts) >= 2 and parts[0] == 'agent-configurations':
            return parts[1]
        return ""

    def categorize_changes(self) -> Dict:
        """Categorize changes into different types.

        Returns:
            Dictionary with categorized changes:
            {
                'new_configs': [(filepath, template_name), ...],
                'modified_configs': [(filepath, template_name), ...],
                'deleted_configs': [(filepath, template_name), ...],
                'template_changes': {template_name: [changed_files], ...}
            }
        """
        changed_files = self.get_changed_files()

        changes = {
            'new_configs': [],
            'modified_configs': [],
            'deleted_configs': [],
            'template_changes': {}
        }

        for status, filepath in changed_files:
            # Check if it's a configuration file
            if filepath.startswith('agent-configurations/') and filepath.endswith('.json'):
                template_name = self.extract_template_from_path(filepath)

                if status == 'A':
                    changes['new_configs'].append((filepath, template_name))
                elif status == 'M':
                    changes['modified_configs'].append((filepath, template_name))
                elif status == 'D':
                    changes['deleted_configs'].append((filepath, template_name))

            # Check if it's a template file
            elif filepath.startswith('templates/'):
                parts = Path(filepath).parts
                if len(parts) >= 2:
                    template_name = parts[1]
                    if template_name not in changes['template_changes']:
                        changes['template_changes'][template_name] = []
                    changes['template_changes'][template_name].append(filepath)

        return changes

    def find_configs_for_template(self, template_name: str) -> List[str]:
        """Find all config files that use a specific template.

        Args:
            template_name: Template name like 'ts_langchain'

        Returns:
            List of config file paths
        """
        config_dir = self.repo_root / 'agent-configurations' / template_name
        if not config_dir.exists():
            return []

        configs = []
        for config_file in config_dir.glob('*.json'):
            configs.append(str(config_file.relative_to(self.repo_root)))

        return configs
