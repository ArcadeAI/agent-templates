#!/usr/bin/env python3
"""Main sync orchestrator for agent template automation."""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple

from .change_detector import ChangeDetector
from .config_manager import ConfigManager
from .state_tracker import StateTracker
from .github_client import GitHubClient
from .agent_generator import AgentGenerator
from .rate_limiter import RateLimiter


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class AgentSync:
    """Main orchestrator for agent syncing."""

    def __init__(self, repo_root: Path):
        """Initialize agent sync system.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root
        self.config_manager = ConfigManager(repo_root)
        self.state_tracker = StateTracker(repo_root)
        self.change_detector = ChangeDetector(repo_root)
        self.agent_generator = AgentGenerator(repo_root)
        self.github_client = None
        self.rate_limiter = RateLimiter(self.state_tracker, self.config_manager)

    def initialize_github_client(self):
        """Initialize GitHub client with token from config."""
        try:
            token = self.config_manager.get_github_token()
            self.github_client = GitHubClient(token)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

    def get_repo_name_from_config(self, config_path: str) -> str:
        """Get repository name from config path.

        Args:
            config_path: Path like 'agent-configurations/ts_langchain/gmail-slack.json'

        Returns:
            Repository name like 'gmail-slack'
        """
        return Path(config_path).stem

    def sync_new_config(self, config_path: str, template_name: str) -> bool:
        """Sync a new configuration file.

        Args:
            config_path: Path to config file
            template_name: Template name

        Returns:
            True if successful
        """
        if self.config_manager.is_excluded_config(config_path):
            logger.info(f"Skipping excluded config: {config_path}")
            return True

        # Check rate limit for creating new repos
        can_create, reason = self.rate_limiter.can_create_repo()
        if not can_create:
            logger.warning(f"⏳ Rate limit: {reason}")
            logger.warning(f"Deferring new config: {config_path}")
            agent_key = self.state_tracker.get_agent_key(config_path)
            self.state_tracker.mark_agent_pending(agent_key, f"Rate limited: {reason}")
            return False

        try:
            logger.info(f"Processing new config: {config_path}")

            # Get GitHub org and repo info
            org = self.config_manager.get_github_org()
            repo_name = self.get_repo_name_from_config(config_path)
            auth_method = self.config_manager.get_auth_method()

            repo_created = False
            # Check if repo already exists
            if self.github_client.repo_exists(org, repo_name):
                logger.info(f"Repository {org}/{repo_name} already exists")
                repo_url = self.github_client.get_repo_url(org, repo_name, auth_method)
            else:
                # Create GitHub repository
                logger.info(f"Creating GitHub repository: {org}/{repo_name}")
                visibility = self.config_manager.get_default_visibility()
                repo_url = self.github_client.create_repo(
                    org,
                    repo_name,
                    description=f"Agent generated from {template_name} template",
                    visibility=visibility
                )
                repo_created = True

            # Generate agent and push
            agent_dir, commit_sha = self.agent_generator.sync_agent(
                config_path,
                template_name,
                repo_url,
                initial=True
            )

            # Update state
            agent_key = self.state_tracker.get_agent_key(config_path)
            self.state_tracker.update_agent(
                agent_key,
                config_path,
                str(agent_dir),
                org,
                repo_name,
                repo_url,
                status='synced',
                last_commit_sha=commit_sha
            )

            # Record rate limit usage
            if repo_created:
                self.rate_limiter.record_repo_creation()
            self.rate_limiter.record_update()

            logger.info(f"✓ Successfully synced new agent: {repo_name}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to sync new config {config_path}: {e}")
            agent_key = self.state_tracker.get_agent_key(config_path)
            self.state_tracker.mark_agent_failed(agent_key, str(e))
            return False

    def sync_modified_config(self, config_path: str, template_name: str) -> bool:
        """Sync a modified configuration file.

        Args:
            config_path: Path to config file
            template_name: Template name

        Returns:
            True if successful
        """
        if self.config_manager.is_excluded_config(config_path):
            logger.info(f"Skipping excluded config: {config_path}")
            return True

        # Check rate limit for updates
        can_push, reason = self.rate_limiter.can_push_update()
        if not can_push:
            logger.warning(f"⏳ Rate limit: {reason}")
            logger.warning(f"Deferring update: {config_path}")
            agent_key = self.state_tracker.get_agent_key(config_path)
            self.state_tracker.mark_agent_pending(agent_key, f"Rate limited: {reason}")
            return False

        try:
            logger.info(f"Processing modified config: {config_path}")

            # Get agent info from state
            agent_key = self.state_tracker.get_agent_key(config_path)
            agent_info = self.state_tracker.get_agent_info(agent_key)

            if not agent_info:
                # Agent not in state, treat as new
                logger.warning(f"Agent {agent_key} not in state, treating as new")
                return self.sync_new_config(config_path, template_name)

            # Regenerate agent and push
            repo_url = agent_info['repo_url']
            agent_dir, commit_sha = self.agent_generator.sync_agent(
                config_path,
                template_name,
                repo_url,
                initial=False
            )

            # Update state
            self.state_tracker.update_agent(
                agent_key,
                config_path,
                str(agent_dir),
                agent_info['repo_org'],
                agent_info['repo_name'],
                repo_url,
                status='synced',
                last_commit_sha=commit_sha
            )

            # Record rate limit usage
            self.rate_limiter.record_update()

            logger.info(f"✓ Successfully synced modified agent: {agent_info['repo_name']}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to sync modified config {config_path}: {e}")
            agent_key = self.state_tracker.get_agent_key(config_path)
            self.state_tracker.mark_agent_failed(agent_key, str(e))
            return False

    def sync_template_changes(self, template_name: str) -> Tuple[int, int]:
        """Sync all agents affected by template changes.

        Args:
            template_name: Template name that changed

        Returns:
            Tuple of (success_count, failure_count)
        """
        logger.info(f"Template {template_name} changed, finding affected agents...")

        # Find all configs using this template
        configs = self.change_detector.find_configs_for_template(template_name)

        if not configs:
            logger.info(f"No configs found for template {template_name}")
            return 0, 0

        logger.info(f"Found {len(configs)} agents using template {template_name}")

        success_count = 0
        failure_count = 0

        for config_path in configs:
            if self.sync_modified_config(config_path, template_name):
                success_count += 1
            else:
                failure_count += 1

        return success_count, failure_count

    def run_hook_mode(self) -> int:
        """Run in hook mode (called by post-commit hook).

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        start_time = time.time()

        logger.info("=== Agent Sync Hook ===")

        # Initialize GitHub client
        try:
            self.initialize_github_client()
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return 1

        # Detect changes
        changes = self.change_detector.categorize_changes()

        # Check if there are any relevant changes
        has_changes = (
            changes['new_configs'] or
            changes['modified_configs'] or
            changes['template_changes']
        )

        if not has_changes:
            logger.info("No agent-related changes detected")
            return 0

        # Track results
        total_success = 0
        total_failure = 0
        affected_agents = []

        # Process new configs
        for config_path, template_name in changes['new_configs']:
            if self.sync_new_config(config_path, template_name):
                total_success += 1
                affected_agents.append(self.state_tracker.get_agent_key(config_path))
            else:
                total_failure += 1

        # Process modified configs
        for config_path, template_name in changes['modified_configs']:
            if self.sync_modified_config(config_path, template_name):
                total_success += 1
                affected_agents.append(self.state_tracker.get_agent_key(config_path))
            else:
                total_failure += 1

        # Process template changes
        for template_name, changed_files in changes['template_changes'].items():
            success, failure = self.sync_template_changes(template_name)
            total_success += success
            total_failure += failure

        # Record sync history
        duration = time.time() - start_time
        status = 'success' if total_failure == 0 else 'partial_failure'
        self.state_tracker.add_sync_history(
            trigger='post_commit_hook',
            affected_agents=affected_agents,
            status=status,
            duration=duration
        )

        # Print summary
        logger.info("\n=== Sync Summary ===")
        logger.info(f"✓ Success: {total_success}")
        if total_failure > 0:
            logger.warning(f"✗ Failed: {total_failure}")
        logger.info(f"Duration: {duration:.1f}s")

        return 0 if total_failure == 0 else 1

    def show_status(self):
        """Show current sync status."""
        state = self.state_tracker.load_state()

        logger.info("\n=== Agent Sync Status ===")
        logger.info(f"Last sync: {state.get('last_sync', 'Never')}")

        agents = state.get('agents', {})
        if not agents:
            logger.info("No agents tracked yet")
            return

        synced = [k for k, v in agents.items() if v.get('status') == 'synced']
        pending = [k for k, v in agents.items() if v.get('status') == 'pending']
        failed = [k for k, v in agents.items() if v.get('status') == 'failed']

        logger.info(f"\nTotal agents: {len(agents)}")
        logger.info(f"  ✓ Synced: {len(synced)}")
        if pending:
            logger.info(f"  ⏳ Pending: {len(pending)}")
            for agent_key in pending:
                logger.info(f"    - {agent_key}")
        if failed:
            logger.warning(f"  ✗ Failed: {len(failed)}")
            for agent_key in failed:
                error = agents[agent_key].get('last_error', 'Unknown error')
                logger.warning(f"    - {agent_key}: {error}")

    def retry_failed(self) -> int:
        """Retry failed agents.

        Returns:
            Exit code
        """
        failed = self.state_tracker.get_failed_agents()
        pending = self.state_tracker.get_pending_agents()

        all_to_retry = failed + pending

        if not all_to_retry:
            logger.info("No failed or pending agents to retry")
            return 0

        logger.info(f"Retrying {len(all_to_retry)} agents...")

        self.initialize_github_client()

        success = 0
        for agent_key in all_to_retry:
            agent_info = self.state_tracker.get_agent_info(agent_key)
            if not agent_info:
                continue

            config_path = agent_info['config_path']
            template_name = Path(config_path).parent.name

            if self.sync_modified_config(config_path, template_name):
                success += 1

        logger.info(f"Retry complete: {success}/{len(all_to_retry)} succeeded")
        return 0 if success == len(all_to_retry) else 1

    def show_rate_limits(self):
        """Show current rate limit status."""
        status = self.rate_limiter.get_rate_limit_status()

        logger.info("\n=== Rate Limit Status ===")

        # New repos
        new_repos = status['new_repos']
        logger.info(f"\nNew Repository Creation ({new_repos['window']}):")
        logger.info(f"  Current: {new_repos['current']}")
        logger.info(f"  Limit: {new_repos['limit']}")
        if new_repos['limit'] != 'unlimited':
            logger.info(f"  Remaining: {new_repos['remaining']}")

        # Updates
        updates = status['updates']
        logger.info(f"\nAgent Updates ({updates['window']}):")
        logger.info(f"  Current: {updates['current']}")
        logger.info(f"  Limit: {updates['limit']}")
        if updates['limit'] != 'unlimited':
            logger.info(f"  Remaining: {updates['remaining']}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agent template sync automation"
    )
    parser.add_argument(
        '--hook-mode',
        action='store_true',
        help='Run in post-commit hook mode'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show sync status'
    )
    parser.add_argument(
        '--retry',
        action='store_true',
        help='Retry failed/pending agents'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Health check'
    )
    parser.add_argument(
        '--rate-status',
        action='store_true',
        help='Show rate limit status'
    )

    args = parser.parse_args()

    # Find repository root
    repo_root = Path(__file__).parent.parent

    sync = AgentSync(repo_root)

    try:
        if args.hook_mode:
            return sync.run_hook_mode()
        elif args.status:
            sync.show_status()
            return 0
        elif args.retry:
            return sync.retry_failed()
        elif args.rate_status:
            sync.show_rate_limits()
            return 0
        elif args.check:
            logger.info("Sync system health check: OK")
            return 0
        else:
            parser.print_help()
            return 0

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
