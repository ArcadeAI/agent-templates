"""Rate limiting for GitHub operations."""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for GitHub operations."""

    def __init__(self, state_tracker, config_manager):
        """Initialize rate limiter.

        Args:
            state_tracker: StateTracker instance
            config_manager: ConfigManager instance
        """
        self.state = state_tracker
        self.config = config_manager

    def get_rate_limits(self) -> Tuple[Optional[int], Optional[int]]:
        """Get rate limits from config.

        Returns:
            Tuple of (new_repos_per_day, updates_per_hour)
            None values mean no limit
        """
        new_repos_limit = self.config.get_new_repos_per_day()
        updates_limit = self.config.get_updates_per_hour()
        return new_repos_limit, updates_limit

    def _clean_old_timestamps(self, timestamps: list, hours: int) -> list:
        """Remove timestamps older than specified hours.

        Args:
            timestamps: List of ISO timestamp strings
            hours: Number of hours to keep

        Returns:
            Cleaned list of timestamps
        """
        if not timestamps:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cleaned = []

        for ts_str in timestamps:
            try:
                ts = datetime.fromisoformat(ts_str.rstrip('Z'))
                if ts >= cutoff:
                    cleaned.append(ts_str)
            except (ValueError, AttributeError):
                # Skip invalid timestamps
                continue

        return cleaned

    def can_create_repo(self) -> Tuple[bool, str]:
        """Check if we can create a new repository.

        Returns:
            Tuple of (can_create, reason_if_not)
        """
        limit = self.config.get_new_repos_per_day()

        # No limit configured
        if limit is None or limit <= 0:
            return True, ""

        # Get tracking data
        state_data = self.state.load_state()
        tracking = state_data.get('rate_limit_tracking', {})
        new_repos = tracking.get('new_repos', [])

        # Clean old timestamps (keep last 24 hours)
        new_repos = self._clean_old_timestamps(new_repos, hours=24)

        # Check if under limit
        current_count = len(new_repos)
        if current_count >= limit:
            oldest = new_repos[0] if new_repos else None
            return False, (
                f"Rate limit reached: {current_count}/{limit} repos created in last 24 hours. "
                f"Oldest will expire at {oldest} + 24h" if oldest else ""
            )

        return True, ""

    def can_push_update(self) -> Tuple[bool, str]:
        """Check if we can push an update.

        Returns:
            Tuple of (can_push, reason_if_not)
        """
        limit = self.config.get_updates_per_hour()

        # No limit configured
        if limit is None or limit <= 0:
            return True, ""

        # Get tracking data
        state_data = self.state.load_state()
        tracking = state_data.get('rate_limit_tracking', {})
        updates = tracking.get('updates', [])

        # Clean old timestamps (keep last 1 hour)
        updates = self._clean_old_timestamps(updates, hours=1)

        # Check if under limit
        current_count = len(updates)
        if current_count >= limit:
            oldest = updates[0] if updates else None
            return False, (
                f"Rate limit reached: {current_count}/{limit} updates pushed in last hour. "
                f"Oldest will expire at {oldest} + 1h" if oldest else ""
            )

        return True, ""

    def record_repo_creation(self):
        """Record a repository creation."""
        state_data = self.state.load_state()

        if 'rate_limit_tracking' not in state_data:
            state_data['rate_limit_tracking'] = {}

        tracking = state_data['rate_limit_tracking']
        if 'new_repos' not in tracking:
            tracking['new_repos'] = []

        # Add current timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        tracking['new_repos'].append(now)

        # Clean old timestamps
        tracking['new_repos'] = self._clean_old_timestamps(tracking['new_repos'], hours=24)

        # Save state
        self.state._state = state_data
        self.state.save_state()

        logger.debug(f"Recorded repo creation. Total in last 24h: {len(tracking['new_repos'])}")

    def record_update(self):
        """Record an update push."""
        state_data = self.state.load_state()

        if 'rate_limit_tracking' not in state_data:
            state_data['rate_limit_tracking'] = {}

        tracking = state_data['rate_limit_tracking']
        if 'updates' not in tracking:
            tracking['updates'] = []

        # Add current timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        tracking['updates'].append(now)

        # Clean old timestamps
        tracking['updates'] = self._clean_old_timestamps(tracking['updates'], hours=1)

        # Save state
        self.state._state = state_data
        self.state.save_state()

        logger.debug(f"Recorded update. Total in last hour: {len(tracking['updates'])}")

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        state_data = self.state.load_state()
        tracking = state_data.get('rate_limit_tracking', {})

        # Clean old data
        new_repos = self._clean_old_timestamps(tracking.get('new_repos', []), hours=24)
        updates = self._clean_old_timestamps(tracking.get('updates', []), hours=1)

        new_repos_limit = self.config.get_new_repos_per_day()
        updates_limit = self.config.get_updates_per_hour()

        return {
            'new_repos': {
                'current': len(new_repos),
                'limit': new_repos_limit if new_repos_limit else 'unlimited',
                'remaining': (new_repos_limit - len(new_repos)) if new_repos_limit else 'unlimited',
                'window': 'last 24 hours'
            },
            'updates': {
                'current': len(updates),
                'limit': updates_limit if updates_limit else 'unlimited',
                'remaining': (updates_limit - len(updates)) if updates_limit else 'unlimited',
                'window': 'last hour'
            }
        }
