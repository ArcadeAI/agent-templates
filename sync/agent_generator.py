"""Agent generation and git operations."""

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class AgentGenerator:
    """Generate agents and manage their git repositories."""

    def __init__(self, repo_root: Path):
        """Initialize agent generator.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root

    def generate_agent(
        self,
        config_path: str,
        template_name: str,
        output_dir: Optional[Path] = None
    ) -> Path:
        """Generate an agent from configuration.

        Args:
            config_path: Path to configuration JSON file
            template_name: Template name (e.g., 'ts_langchain')
            output_dir: Output directory (optional, will be inferred if not provided)

        Returns:
            Path to generated agent directory

        Raises:
            RuntimeError: If agent generation fails
        """
        config_file = self.repo_root / config_path
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        # Load configuration
        try:
            with open(config_file, 'r') as f:
                configuration = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {config_file}\n{e}")

        # Determine template directory
        template_dir = self.repo_root / "templates" / template_name
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # Determine output directory
        if not output_dir:
            config_stem = config_file.stem
            output_dir = self.repo_root / "real_agents" / template_name / config_stem

        logger.info(f"Generating agent: {config_path}")
        logger.info(f"  Template: {template_name}")
        logger.info(f"  Output: {output_dir}")

        # If output directory exists, nuke everything except .git
        if output_dir.exists():
            logger.info(f"Cleaning existing agent directory (preserving .git)")
            for item in output_dir.iterdir():
                if item.name != '.git':
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

        # Import and use the create_agent function from render_utils
        try:
            # Add repo root to sys.path to import render_utils
            if str(self.repo_root) not in sys.path:
                sys.path.insert(0, str(self.repo_root))

            from render_utils import create_agent

            # Generate the agent
            create_agent(output_dir, template_dir, configuration)

            logger.info(f"Successfully generated agent at: {output_dir}")
            return output_dir

        except Exception as e:
            logger.error(f"Failed to generate agent: {e}")
            raise RuntimeError(f"Agent generation failed: {e}")

    def init_git_repo(self, agent_dir: Path) -> bool:
        """Initialize git repository in agent directory.

        Args:
            agent_dir: Path to agent directory

        Returns:
            True if git repo was initialized (new), False if already exists
        """
        git_dir = agent_dir / '.git'
        if git_dir.exists():
            logger.debug(f"Git repo already exists in {agent_dir}")
            return False

        try:
            subprocess.run(
                ['git', 'init'],
                cwd=agent_dir,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Initialized git repo in {agent_dir}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to init git repo: {e}")
            raise RuntimeError(f"Git init failed: {e}")

    def setup_remote(self, agent_dir: Path, repo_url: str):
        """Setup or update git remote for agent repository.

        Args:
            agent_dir: Path to agent directory
            repo_url: Remote repository URL
        """
        try:
            # Check if remote already exists
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=agent_dir,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Remote exists, update it
                current_url = result.stdout.strip()
                if current_url != repo_url:
                    subprocess.run(
                        ['git', 'remote', 'set-url', 'origin', repo_url],
                        cwd=agent_dir,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    logger.info(f"Updated remote origin to: {repo_url}")
            else:
                # Remote doesn't exist, add it
                subprocess.run(
                    ['git', 'remote', 'add', 'origin', repo_url],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Added remote origin: {repo_url}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup remote: {e}")
            raise RuntimeError(f"Git remote setup failed: {e}")

    def commit_changes(
        self,
        agent_dir: Path,
        message: str,
        initial: bool = False
    ) -> str:
        """Commit all changes in agent directory.

        Args:
            agent_dir: Path to agent directory
            message: Commit message
            initial: Whether this is an initial commit

        Returns:
            Commit SHA

        Raises:
            RuntimeError: If commit fails
        """
        try:
            # Stage all files
            subprocess.run(
                ['git', 'add', '-A'],
                cwd=agent_dir,
                capture_output=True,
                text=True,
                check=True
            )

            # Commit
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=agent_dir,
                capture_output=True,
                text=True,
                check=True
            )

            # Get commit SHA
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=agent_dir,
                capture_output=True,
                text=True,
                check=True
            )

            commit_sha = result.stdout.strip()
            logger.info(f"Created commit: {commit_sha[:7]} - {message}")
            return commit_sha

        except subprocess.CalledProcessError as e:
            if 'nothing to commit' in e.stderr:
                logger.info("No changes to commit")
                # Get current HEAD SHA
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            else:
                logger.error(f"Failed to commit: {e.stderr}")
                raise RuntimeError(f"Git commit failed: {e}")

    def push_to_remote(
        self,
        agent_dir: Path,
        branch: str = 'main',
        force: bool = False
    ):
        """Push commits to remote repository.

        Args:
            agent_dir: Path to agent directory
            branch: Branch name to push
            force: Whether to force push

        Raises:
            RuntimeError: If push fails
        """
        try:
            # Check if branch exists locally
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', branch],
                cwd=agent_dir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                # Branch doesn't exist, create it
                subprocess.run(
                    ['git', 'checkout', '-b', branch],
                    cwd=agent_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Created branch: {branch}")

            # Push to remote
            push_args = ['git', 'push', '-u', 'origin', branch]
            if force:
                push_args.insert(2, '--force')

            subprocess.run(
                push_args,
                cwd=agent_dir,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"Pushed to origin/{branch}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push: {e.stderr}")
            raise RuntimeError(f"Git push failed: {e.stderr}")

    def sync_agent(
        self,
        config_path: str,
        template_name: str,
        repo_url: str,
        initial: bool = False
    ) -> Tuple[Path, str]:
        """Full sync workflow: generate, commit, and push agent.

        Args:
            config_path: Path to configuration JSON file
            template_name: Template name
            repo_url: Remote repository URL
            initial: Whether this is initial creation

        Returns:
            Tuple of (agent_dir, commit_sha)

        Raises:
            RuntimeError: If any step fails
        """
        # Generate agent
        agent_dir = self.generate_agent(config_path, template_name)

        # Initialize git repo if needed
        is_new = self.init_git_repo(agent_dir)

        # Setup remote
        self.setup_remote(agent_dir, repo_url)

        # Commit changes
        if initial or is_new:
            message = "Initial commit: Agent generated from template"
        else:
            message = "Update: Regenerated from updated configuration"

        commit_sha = self.commit_changes(agent_dir, message, initial=initial)

        # Push to remote
        self.push_to_remote(agent_dir, branch='main', force=initial)

        return agent_dir, commit_sha
