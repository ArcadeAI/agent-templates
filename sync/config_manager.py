"""Configuration management for sync system."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage sync system configuration."""

    def __init__(self, repo_root: Path):
        """Initialize configuration manager.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root
        self.config_file = repo_root / '.sync-config.json'
        self.env_file = repo_root / '.env'
        self._config: Optional[Dict[str, Any]] = None

    def load_env_file(self):
        """Load environment variables from .env file if it exists."""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                        logger.debug(f"Loaded {key} from .env file")

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from .sync-config.json.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if self._config is not None:
            return self._config

        # Load .env file first if it exists
        self.load_env_file()

        if not self.config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}\n"
                f"Please create .sync-config.json with your GitHub org name."
            )

        with open(self.config_file, 'r') as f:
            self._config = json.load(f)

        # Validate required fields
        self.validate_config(self._config)

        return self._config

    def validate_config(self, config: Dict[str, Any]):
        """Validate configuration has required fields.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If required fields are missing
        """
        if 'github' not in config:
            raise ValueError("Config missing 'github' section")

        if 'org' not in config['github']:
            raise ValueError("Config missing 'github.org' field")

        # Check for GitHub token
        token_env_var = config['github'].get('token_env_var', 'GITHUB_TOKEN')
        if not os.getenv(token_env_var):
            logger.warning(
                f"{token_env_var} not set. GitHub operations will fail. "
                f"Please set it in your shell profile or .env file."
            )

    def get_github_org(self) -> str:
        """Get GitHub organization name from config.

        Returns:
            GitHub organization name
        """
        config = self.load_config()
        return config['github']['org']

    def get_github_token(self) -> str:
        """Get GitHub token from environment.

        Returns:
            GitHub token

        Raises:
            ValueError: If token not found
        """
        config = self.load_config()
        token_env_var = config['github'].get('token_env_var', 'GITHUB_TOKEN')
        token = os.getenv(token_env_var)

        if not token:
            raise ValueError(
                f"{token_env_var} not set. Please set it in your shell profile "
                f"or create a .env file with: {token_env_var}=ghp_xxxxx"
            )

        return token

    def get_auth_method(self) -> str:
        """Get authentication method (ssh or https).

        Returns:
            'ssh' or 'https'
        """
        config = self.load_config()
        return config['github'].get('auth_method', 'ssh')

    def should_auto_sync(self) -> bool:
        """Check if auto-sync on commit is enabled.

        Returns:
            True if auto-sync is enabled
        """
        config = self.load_config()
        return config.get('sync', {}).get('auto_sync_on_commit', True)

    def should_push_to_main(self) -> bool:
        """Check if pushing directly to main is enabled.

        Returns:
            True if pushing to main is enabled
        """
        config = self.load_config()
        return config.get('sync', {}).get('push_to_main', True)

    def get_repo_naming(self) -> str:
        """Get repository naming pattern.

        Returns:
            Naming pattern string (default: '{config_stem}')
        """
        config = self.load_config()
        return config.get('agent_config', {}).get('repo_naming', '{config_stem}')

    def get_default_visibility(self) -> str:
        """Get default repository visibility.

        Returns:
            'public' or 'private'
        """
        config = self.load_config()
        return config['github'].get('default_visibility', 'public')

    def is_excluded_config(self, config_path: str) -> bool:
        """Check if a config file is excluded from syncing.

        Args:
            config_path: Path to config file

        Returns:
            True if config should be excluded
        """
        config = self.load_config()
        excluded_patterns = config.get('excluded_configs', [])

        from fnmatch import fnmatch
        for pattern in excluded_patterns:
            if fnmatch(config_path, pattern):
                return True

        return False
