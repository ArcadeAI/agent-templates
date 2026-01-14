"""Track sync state for all agents."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class StateTracker:
    """Track and manage agent sync state."""

    def __init__(self, repo_root: Path):
        """Initialize state tracker.

        Args:
            repo_root: Path to repository root
        """
        self.repo_root = repo_root
        self.state_file = repo_root / '.sync-state.json'
        self._state: Optional[Dict[str, Any]] = None

    def load_state(self) -> Dict[str, Any]:
        """Load state from .sync-state.json.

        Returns:
            State dictionary
        """
        if self._state is not None:
            return self._state

        if not self.state_file.exists():
            # Initialize empty state
            self._state = {
                'version': '1.0',
                'last_sync': None,
                'agents': {},
                'sync_history': []
            }
            return self._state

        try:
            with open(self.state_file, 'r') as f:
                self._state = json.load(f)
            return self._state
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load state file: {e}")
            # Return empty state if file is corrupted
            self._state = {
                'version': '1.0',
                'last_sync': None,
                'agents': {},
                'sync_history': []
            }
            return self._state

    def save_state(self):
        """Save state to .sync-state.json."""
        if self._state is None:
            return

        with open(self.state_file, 'w') as f:
            json.dump(self._state, f, indent=2)

    def get_agent_key(self, config_path: str) -> str:
        """Get agent key from config path.

        Args:
            config_path: Path like 'agent-configurations/ts_langchain/gmail-slack.json'

        Returns:
            Agent key like 'ts_langchain/gmail-slack'
        """
        parts = Path(config_path).parts
        if len(parts) >= 3 and parts[0] == 'agent-configurations':
            template_name = parts[1]
            config_name = Path(parts[2]).stem
            return f"{template_name}/{config_name}"
        return ""

    def get_agent_info(self, agent_key: str) -> Optional[Dict[str, Any]]:
        """Get agent information from state.

        Args:
            agent_key: Agent key like 'ts_langchain/gmail-slack'

        Returns:
            Agent info dictionary or None
        """
        state = self.load_state()
        return state['agents'].get(agent_key)

    def update_agent(
        self,
        agent_key: str,
        config_path: str,
        agent_dir: str,
        repo_org: str,
        repo_name: str,
        repo_url: str,
        status: str = 'synced',
        last_commit_sha: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Update agent information in state.

        Args:
            agent_key: Agent key like 'ts_langchain/gmail-slack'
            config_path: Path to config file
            agent_dir: Path to agent directory
            repo_org: GitHub organization name
            repo_name: Repository name
            repo_url: Full repository URL
            status: Sync status ('synced', 'pending', 'failed')
            last_commit_sha: SHA of last commit
            error: Error message if failed
        """
        state = self.load_state()

        now = datetime.utcnow().isoformat() + 'Z'

        if agent_key not in state['agents']:
            # New agent
            state['agents'][agent_key] = {
                'config_path': config_path,
                'agent_dir': agent_dir,
                'repo_org': repo_org,
                'repo_name': repo_name,
                'repo_url': repo_url,
                'created_at': now,
                'last_synced': now if status == 'synced' else None,
                'last_commit_sha': last_commit_sha,
                'status': status,
                'last_error': error,
                'sync_count': 1 if status == 'synced' else 0
            }
        else:
            # Update existing agent
            agent = state['agents'][agent_key]
            agent['status'] = status
            agent['last_error'] = error

            if status == 'synced':
                agent['last_synced'] = now
                agent['sync_count'] = agent.get('sync_count', 0) + 1

            if last_commit_sha:
                agent['last_commit_sha'] = last_commit_sha

        state['last_sync'] = now
        self._state = state
        self.save_state()

    def mark_agent_failed(self, agent_key: str, error: str):
        """Mark agent as failed.

        Args:
            agent_key: Agent key
            error: Error message
        """
        state = self.load_state()
        if agent_key in state['agents']:
            state['agents'][agent_key]['status'] = 'failed'
            state['agents'][agent_key]['last_error'] = error
            self._state = state
            self.save_state()

    def mark_agent_pending(self, agent_key: str, reason: str):
        """Mark agent as pending sync.

        Args:
            agent_key: Agent key
            reason: Reason for pending status
        """
        state = self.load_state()
        if agent_key in state['agents']:
            state['agents'][agent_key]['status'] = 'pending'
            state['agents'][agent_key]['last_error'] = reason
            self._state = state
            self.save_state()

    def get_pending_agents(self) -> List[str]:
        """Get list of agents with pending status.

        Returns:
            List of agent keys
        """
        state = self.load_state()
        return [
            key for key, info in state['agents'].items()
            if info.get('status') == 'pending'
        ]

    def get_failed_agents(self) -> List[str]:
        """Get list of agents with failed status.

        Returns:
            List of agent keys
        """
        state = self.load_state()
        return [
            key for key, info in state['agents'].items()
            if info.get('status') == 'failed'
        ]

    def add_sync_history(
        self,
        trigger: str,
        affected_agents: List[str],
        status: str,
        duration: Optional[float] = None,
        changed_files: Optional[List[str]] = None
    ):
        """Add entry to sync history.

        Args:
            trigger: What triggered the sync
            affected_agents: List of agent keys affected
            status: Overall status ('success' or 'partial_failure')
            duration: Duration in seconds
            changed_files: List of changed files
        """
        state = self.load_state()

        history_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'trigger': trigger,
            'affected_agents': affected_agents,
            'status': status,
        }

        if duration is not None:
            history_entry['duration_seconds'] = round(duration, 2)

        if changed_files:
            history_entry['changed_files'] = changed_files

        state['sync_history'].append(history_entry)

        # Keep only last 50 history entries
        if len(state['sync_history']) > 50:
            state['sync_history'] = state['sync_history'][-50:]

        self._state = state
        self.save_state()

    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all agents from state.

        Returns:
            Dictionary of agent_key -> agent_info
        """
        state = self.load_state()
        return state['agents']

    def delete_agent(self, agent_key: str):
        """Delete agent from state.

        Args:
            agent_key: Agent key to delete
        """
        state = self.load_state()
        if agent_key in state['agents']:
            del state['agents'][agent_key]
            self._state = state
            self.save_state()
