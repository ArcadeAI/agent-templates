"""GitHub API client for repository management."""

from github import Github, GithubException
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations."""

    def __init__(self, token: str):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token
        """
        self.token = token
        self.client = Github(token)

    def create_repo(
        self,
        org_name: str,
        repo_name: str,
        description: str = "",
        visibility: str = 'public'
    ) -> str:
        """Create a new repository in the specified organization.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name
            description: Repository description
            visibility: 'public' or 'private'

        Returns:
            Clone URL for the repository (SSH or HTTPS)

        Raises:
            GithubException: If repo creation fails
        """
        try:
            logger.info(f"Creating GitHub repo: {org_name}/{repo_name}")

            org = self.client.get_organization(org_name)
            repo = org.create_repo(
                name=repo_name,
                description=description,
                private=(visibility == 'private'),
                auto_init=False,  # We'll push initial commit
                has_issues=True,
                has_wiki=False,
                has_downloads=True
            )

            logger.info(f"Successfully created repo: {repo.html_url}")
            return repo.ssh_url

        except GithubException as e:
            if e.status == 422 and 'already exists' in str(e.data):
                logger.warning(f"Repository {org_name}/{repo_name} already exists")
                # Get the existing repo URL
                try:
                    org = self.client.get_organization(org_name)
                    repo = org.get_repo(repo_name)
                    return repo.ssh_url
                except:
                    # Fallback to constructing URL
                    return f"git@github.com:{org_name}/{repo_name}.git"
            else:
                logger.error(f"Failed to create repo: {e}")
                raise

    def repo_exists(self, org_name: str, repo_name: str) -> bool:
        """Check if repository already exists.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name

        Returns:
            True if repository exists
        """
        try:
            self.client.get_repo(f"{org_name}/{repo_name}")
            return True
        except GithubException:
            return False

    def get_repo_url(
        self,
        org_name: str,
        repo_name: str,
        auth_method: str = 'ssh'
    ) -> str:
        """Get repository URL.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name
            auth_method: 'ssh' or 'https'

        Returns:
            Repository clone URL
        """
        if auth_method == 'https':
            return f"https://github.com/{org_name}/{repo_name}.git"
        else:
            return f"git@github.com:{org_name}/{repo_name}.git"

    def archive_repo(self, org_name: str, repo_name: str):
        """Archive a repository.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name
        """
        try:
            repo = self.client.get_repo(f"{org_name}/{repo_name}")
            repo.edit(archived=True)
            logger.info(f"Archived repository: {org_name}/{repo_name}")
        except GithubException as e:
            logger.error(f"Failed to archive repo: {e}")
            raise

    def delete_repo(self, org_name: str, repo_name: str):
        """Delete a repository.

        WARNING: This is destructive and cannot be undone!

        Args:
            org_name: GitHub organization name
            repo_name: Repository name
        """
        try:
            repo = self.client.get_repo(f"{org_name}/{repo_name}")
            repo.delete()
            logger.info(f"Deleted repository: {org_name}/{repo_name}")
        except GithubException as e:
            logger.error(f"Failed to delete repo: {e}")
            raise

    def get_default_branch(self, org_name: str, repo_name: str) -> str:
        """Get default branch name for repository.

        Args:
            org_name: GitHub organization name
            repo_name: Repository name

        Returns:
            Default branch name (usually 'main' or 'master')
        """
        try:
            repo = self.client.get_repo(f"{org_name}/{repo_name}")
            return repo.default_branch
        except GithubException:
            return 'main'  # Default fallback
