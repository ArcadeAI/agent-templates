#!/usr/bin/env python3
"""Force sync all or specific templates regardless of git state."""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path to import sync package
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync.sync_agents import AgentSync

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def force_sync_template(sync: AgentSync, template_name: str) -> tuple[int, int]:
    """Force sync all configs for a specific template.

    Args:
        sync: AgentSync instance
        template_name: Template name (e.g., 'py_langchain', 'ts_langchain')

    Returns:
        Tuple of (success_count, failure_count)
    """
    config_dir = sync.repo_root / 'agent-configurations' / template_name

    if not config_dir.exists():
        logger.error(f"Template directory not found: {config_dir}")
        return 0, 0

    # Find all config files
    config_files = list(config_dir.glob('*.json'))

    if not config_files:
        logger.warning(f"No config files found in {config_dir}")
        return 0, 0

    logger.info(f"Found {len(config_files)} configs for template '{template_name}'")

    success_count = 0
    failure_count = 0

    for config_file in config_files:
        # Get relative path from repo root
        config_path = str(config_file.relative_to(sync.repo_root))

        # Check if agent exists in state
        agent_key = sync.state_tracker.get_agent_key(config_path)
        agent_info = sync.state_tracker.get_agent_info(agent_key)

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {config_file.name}")

        if agent_info:
            # Existing agent - force update
            logger.info(f"Status: Existing (forcing update)")
            if sync.sync_modified_config(config_path, template_name):
                success_count += 1
            else:
                failure_count += 1
        else:
            # New agent
            logger.info(f"Status: New")
            if sync.sync_new_config(config_path, template_name):
                success_count += 1
            else:
                failure_count += 1

    return success_count, failure_count


def force_sync_all(sync: AgentSync) -> tuple[int, int]:
    """Force sync all templates.

    Args:
        sync: AgentSync instance

    Returns:
        Tuple of (success_count, failure_count)
    """
    config_dir = sync.repo_root / 'agent-configurations'

    if not config_dir.exists():
        logger.error(f"Config directory not found: {config_dir}")
        return 0, 0

    # Find all template directories
    template_dirs = [d for d in config_dir.iterdir() if d.is_dir()]

    if not template_dirs:
        logger.warning(f"No template directories found in {config_dir}")
        return 0, 0

    logger.info(f"Found {len(template_dirs)} template directories")

    total_success = 0
    total_failure = 0

    for template_dir in sorted(template_dirs):
        template_name = template_dir.name
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing template: {template_name}")
        logger.info(f"{'='*60}")

        success, failure = force_sync_template(sync, template_name)
        total_success += success
        total_failure += failure

    return total_success, total_failure


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Force sync templates regardless of git state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Force sync all py_langchain configs
  python sync/force_sync.py --template py_langchain

  # Force sync all templates
  python sync/force_sync.py --all

  # Dry run to see what would be synced
  python sync/force_sync.py --template py_langchain --dry-run
"""
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--template',
        help='Template name to force sync (e.g., py_langchain, ts_langchain)'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Force sync all templates'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without actually syncing'
    )

    args = parser.parse_args()

    # Find repository root
    repo_root = Path(__file__).parent.parent

    # Initialize sync system
    sync = AgentSync(repo_root)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("")

    try:
        # Initialize GitHub client (unless dry run)
        if not args.dry_run:
            sync.initialize_github_client()

        # Perform sync
        if args.template:
            logger.info(f"Force syncing template: {args.template}")

            if args.dry_run:
                # Just list configs
                config_dir = repo_root / 'agent-configurations' / args.template
                if config_dir.exists():
                    configs = list(config_dir.glob('*.json'))
                    logger.info(f"Would sync {len(configs)} configs:")
                    for cfg in configs:
                        logger.info(f"  - {cfg.name}")
                else:
                    logger.error(f"Template not found: {args.template}")
                return 0

            success, failure = force_sync_template(sync, args.template)
        else:
            logger.info("Force syncing all templates")

            if args.dry_run:
                # Just list all templates
                config_dir = repo_root / 'agent-configurations'
                for template_dir in sorted(config_dir.iterdir()):
                    if template_dir.is_dir():
                        configs = list(template_dir.glob('*.json'))
                        logger.info(f"{template_dir.name}: {len(configs)} configs")
                return 0

            success, failure = force_sync_all(sync)

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("SYNC SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"✓ Success: {success}")
        if failure > 0:
            logger.warning(f"✗ Failed: {failure}")

        return 0 if failure == 0 else 1

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
