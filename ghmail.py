import os
import random
import re
import sys
import time
from typing import Literal

import requests
from dotenv import load_dotenv
from rich import print as rich_print

BASE = "https://api.github.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/vnd.github+json",
}

_STATUS = {
    "info":  ("✓", "green"),
    "debug": ("*", "blue"),
    "error": ("!", "red")
}

# If you have a token, enter it here to avoid request rate limits.
# TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

load_dotenv()

def get_token() -> str | None:
    return os.getenv("GITHUB_TOKEN") or None

TOKEN = os.getenv("GITHUB_TOKEN")
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"


def log(level: Literal["info", "debug", "error"], message: str) -> None:
    symbol, color = _STATUS[level]
    rich_print(f"[{color}][{symbol}][/{color}] {message}")


class GithubEmailHunter:
    def get_public_repos(self, username):
        """Returns all public repositories for the user (with pagination)."""
        repos = []
        page = 1
        while True:
            url = f"{BASE}/users/{username}/repos?per_page=100&page={page}&type=owner"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 404:
                log("error", f"User '{username}' was not found.")
                return []
            if r.status_code != 200:
                log("error", f"Error fetching repos: {r.status_code}")
                return repos
            data = r.json()
            if not data:
                break
            repos.extend(data)
            page += 1
            # Rate limit enforcement for users without tokens
            if not TOKEN:
                time.sleep(0.5)
        return repos

    def get_commits(self, owner, repo):
        """Returns all commits of a repository (with pagination)."""
        commits = []
        page = 1
        while True:
            url = f"{BASE}/repos/{owner}/{repo}/commits?per_page=100&page={page}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 409:  # Empty repo
                return []
            if r.status_code != 200:
                log("error", f"Error retrieving commits for {repo}: {r.status_code}")
                return commits
            data = r.json()
            if not data:
                break
            commits.extend(data)
            page += 1
            if not TOKEN:
                time.sleep(0.5)
            # For very large repos, five pages are enough.
            if page > 5:
                break
        return commits

    def extract_email_from_patch(self, owner, repo, commit_hash):
        """It extracts the commit author's email from the .patch file."""
        patch_url = f"https://github.com/{owner}/{repo}/commit/{commit_hash}.patch"
        r = requests.get(patch_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        emails = re.findall(r"<([^<>]+@[^<>]+)>", r.text)
        return emails[0] if emails else None

    def find_email(self, username, max_repos=10):
        """It randomly selects repositories and commits to find email addresses."""
        log("debug", f"Fetching {username}'s repos...")
        repos = self.get_public_repos(username)
        if not repos:
            log("error", "No public repository was found.")
            return None
        log("debug", f"{len(repos)} repos found.")

        random.shuffle(repos)

        for i, repo in enumerate(repos[:max_repos], 1):
            repo_name = repo["name"]
            log("debug", f"Random repo: {repo_name}")

            commits = self.get_commits(username, repo_name)
            if not commits:
                log("debug", "No commit found, moving to the next repo.")
                continue

            # Pick a random commit
            commit = random.choice(commits)
            sha = commit["sha"]
            log("debug", f"Random commit: {sha[:10]}")

            email: str = self.extract_email_from_patch(username, repo_name, sha)
            if email:
                if not email.endswith(".github.com"):
                    log("info", f"Email found: [bold]{email}[/bold]")
                    return email
                else:
                    log("error", "Email is hidden.")
                    
            else:
                log("debug", "Email not found; moving on to the next commit/repo.")

        log("error", "The email was not found despite these efforts.")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        rich_print("Instructions for use: python script.py <username>")
        rich_print("Example: python script.py torvalds")
        sys.exit(1)

    username = sys.argv[1]
    hunter = GithubEmailHunter()
    email = hunter.find_email(username)
