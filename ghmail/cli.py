"""GitHub Email Hunter — find a user's public email via the GitHub API."""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import __version__

BASE = "https://api.github.com"

HEADERS = {
    "User-Agent": "github-email-hunter",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# The From: header at the top of a .patch file carries the patch author.
_AUTHOR_EMAIL_RE = re.compile(r"^From:\s.*?<([^<>]+@[^<>]+)>", re.MULTILINE)
_ANY_EMAIL_RE = re.compile(r"<([^<>]+@[^<>]+)>")

_MAX_COMMITS_PER_REPO = 5

console = Console()

LEVEL_STYLE = {
    "debug": ("*", "blue"),
    "info": ("•", "cyan"),
    "success": ("✓", "bold green"),
    "warn": ("!", "yellow"),
    "error": ("✗", "bold red"),
}


class GithubAPIError(RuntimeError):
    """The GitHub API rejected (or rate-limited) a request."""


@dataclass(frozen=True)
class EmailResult:
    """A discovered email plus where it came from."""

    email: str
    repository: str
    commit_sha: str
    source_url: str


class GithubEmailHunter:
    """Queries the GitHub API to reveal a user's public email."""

    def __init__(self, *, token=None, timeout=15, throttle=0.5, logger=None):
        self.token = token
        self.timeout = timeout
        self.throttle = throttle
        self._logger = logger

        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _log(self, level, message):
        if self._logger:
            self._logger(level, message)

    def _get(self, url):
        if not self.token:
            time.sleep(self.throttle)  # Back off so unauthenticated users stay in limits.
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            raise GithubAPIError(
                "GitHub API rate limit reached. Wait a bit or provide a token "
                "via the GITHUB_TOKEN environment variable."
            )
        return resp

    def get_public_repos(self, username):
        """Return all public repositories owned by ``username`` (paginated).

        Returns ``None`` if the user does not exist, otherwise a (possibly
        empty) list of repositories.
        """
        repos = []
        page = 1
        while True:
            url = f"{BASE}/users/{username}/repos?per_page=100&page={page}&type=owner"
            self._log("debug", f"GET {url}")
            resp = self._get(url)
            if resp.status_code == 404:
                self._log("error", f"User '{username}' does not exist on GitHub.")
                return None
            if resp.status_code != 200:
                raise GithubAPIError(
                    f"Could not fetch repositories for '{username}' (HTTP {resp.status_code})."
                )
            data = resp.json()
            if not data:
                break
            repos.extend(data)
            page += 1
        return repos

    def get_commits(self, owner, repo, *, max_pages=5):
        """Return up to ``max_pages`` pages of commits for a repository."""
        commits = []
        page = 1
        while True:
            url = f"{BASE}/repos/{owner}/{repo}/commits?per_page=100&page={page}"
            self._log("debug", f"GET {url}")
            resp = self._get(url)
            if resp.status_code == 409:  # Repository exists but has no commits.
                return []
            if resp.status_code != 200:
                raise GithubAPIError(
                    f"Could not fetch commits for '{owner}/{repo}' (HTTP {resp.status_code})."
                )
            data = resp.json()
            if not data:
                break
            commits.extend(data)
            page += 1
            if page > max_pages:
                break
        return commits

    def extract_email_from_patch(self, owner, repo, commit_sha):
        """Extract the commit author's email from the raw ``.patch`` file."""
        patch_url = f"https://github.com/{owner}/{repo}/commit/{commit_sha}.patch"
        self._log("debug", f"GET {patch_url}")
        resp = self.session.get(patch_url, timeout=self.timeout)
        if resp.status_code != 200:
            return None

        author = _AUTHOR_EMAIL_RE.search(resp.text)
        if author:
            return author.group(1)

        fallback = _ANY_EMAIL_RE.findall(resp.text)
        return fallback[0] if fallback else None

    def find_email(self, username, *, max_repos=10, max_commit_pages=5):
        """Scan public commits for ``username`` and return the first real email."""
        try:
            self._log("info", f"Fetching public repositories for {username}")
            repos = self.get_public_repos(username)
            if repos is None:
                return None
            if not repos:
                self._log("error", "No public repositories were found.")
                return None

            random.shuffle(repos)
            selected = repos[:max_repos]
            self._log("info", f"Scanning {len(selected)} of {len(repos)} repositories")

            for i, repo in enumerate(selected, 1):
                repo_name = repo["name"]
                self._log("info", f"[{i}/{len(selected)}] Checking repository: {repo_name}")

                try:
                    commits = self.get_commits(username, repo_name, max_pages=max_commit_pages)
                except GithubAPIError as exc:
                    self._log("warn", str(exc))
                    continue

                if not commits:
                    self._log("debug", "Repository has no commits; skipping.")
                    continue

                candidates = random.sample(commits, min(len(commits), _MAX_COMMITS_PER_REPO))
                for attempt, commit in enumerate(candidates, 1):
                    sha = commit["sha"]
                    self._log("debug", f"Selected commit {sha[:10]} (attempt {attempt}/{len(candidates)})")

                    email = self.extract_email_from_patch(username, repo_name, sha)
                    if email is None:
                        self._log("debug", "No email found in the commit patch; skipping.")
                        continue
                    if email.endswith(".github.com"):
                        self._log("debug", "Author uses a GitHub noreply address; skipping.")
                        continue

                    source_url = f"https://github.com/{username}/{repo_name}/commit/{sha}.patch"
                    self._log("success", f"Email found: {email}")
                    return EmailResult(email=email, repository=repo_name, commit_sha=sha, source_url=source_url)

            self._log("error", "No public email found after scanning the available commits.")
            return None

        except GithubAPIError as exc:
            self._log("error", str(exc))
            return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class _Formatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass


def _force_utf8():
    """Make Unicode symbols survive on Windows when output is redirected."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ghmail",
        formatter_class=_Formatter,
        description=(
            "Find a GitHub user's public email address by scanning the author "
            "headers of their public commits."
        ),
        epilog=(
            "examples:\n"
            "  {prog} torvalds\n"
            "  {prog} torvalds --max-repos 5\n"
            "  {prog} octocat -v --token ghp_xxxxxxxx\n"
            "\n"
            "Providing a token (via --token or the GITHUB_TOKEN environment\n"
            "variable) lifts the unauthenticated 60 requests/hour limit."
        ).format(prog="ghmail"),
    )
    parser.add_argument("username", metavar="USERNAME", help="GitHub username to investigate")
    parser.add_argument(
        "-n", "--max-repos", type=int, default=10, metavar="N",
        help="maximum number of repositories to inspect (0 = all)",
    )
    parser.add_argument(
        "-p", "--max-commit-pages", type=int, default=5, metavar="N",
        help="maximum pages of commits to fetch per repository (100 commits each)",
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=15, metavar="SEC",
        help="HTTP request timeout in seconds",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="print debug diagnostics")
    parser.add_argument(
        "--token", metavar="TOKEN", default=None,
        help="GitHub token; overrides the GITHUB_TOKEN environment variable",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _render_log(level, message):
    symbol, style = LEVEL_STYLE[level]
    console.print(f"  [{style}]{symbol}[/{style}] {escape(message)}")


def _make_logger(verbose):
    def log(level, message):
        if verbose or level != "debug":
            _render_log(level, message)

    return log


def _print_header(username, has_token, max_repos, max_commit_pages):
    token_status = "provided" if has_token else "not provided — 60 requests/hour"
    table = Table.grid(expand=False, padding=(0, 2))
    table.add_column(justify="right", style="bold cyan")
    table.add_column()
    table.add_row("Target", escape(username))
    table.add_row("Token", token_status)
    table.add_row("Repos", str(max_repos))
    table.add_row("Commit pages", str(max_commit_pages))
    console.print(
        Panel(
            table,
            title="[bold] GitHub Email Hunter [/bold]",
            subtitle=f"v{__version__}",
            box=box.HEAVY,
            border_style="cyan",
        ),
        highlight=False,
    )


def _print_result(username, result):
    table = Table.grid(expand=False, padding=(0, 2))
    table.add_column(justify="right", style="bold cyan")
    table.add_column()
    table.add_row("Email", f"[bold green]{escape(result.email)}[/]")
    table.add_row("Target", escape(username))
    table.add_row("Repo", escape(result.repository))
    table.add_row("Commit", result.commit_sha[:10])
    table.add_row("Source", f"[dim]{escape(result.source_url)}[/]")
    console.print()
    console.print(
        Panel(
            table,
            title=" [bold green]Email found[/] ",
            box=box.HEAVY,
            border_style="green",
            padding=(1, 2),
        )
    )


def _print_not_found(username):
    console.print()
    console.print(
        Panel(
            f"[bold red]No public email found[/] for [bold cyan]{escape(username)}[/].\n\n"
            "[dim]The user most likely hides their email address on GitHub.\n"
            "They may also use a noreply address such as "
            "user@users.noreply.github.com, which is deliberately skipped.[/]",
            title=" [bold red]No result[/] ",
            box=box.HEAVY,
            border_style="red",
            padding=(1, 2),
        )
    )


def main(argv=None):
    _force_utf8()
    load_dotenv()
    args = build_parser().parse_args(argv)

    token = args.token or os.getenv("GITHUB_TOKEN")

    _print_header(args.username, bool(token), args.max_repos, args.max_commit_pages)

    if args.verbose:
        _render_log("debug", "Verbose diagnostics enabled")

    hunter = GithubEmailHunter(token=token, timeout=args.timeout, logger=_make_logger(args.verbose))

    try:
        result = hunter.find_email(args.username, max_repos=args.max_repos, max_commit_pages=args.max_commit_pages)
    except KeyboardInterrupt:
        _render_log("warn", "Interrupted by user.")
        return 130
    except requests.RequestException as exc:
        _render_log("error", f"Network error: {exc}")
        return 1

    if result is None:
        _print_not_found(args.username)
        return 1

    _print_result(args.username, result)
    return 0