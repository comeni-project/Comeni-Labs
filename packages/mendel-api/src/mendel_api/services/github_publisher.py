"""`comeni-registry` on GitHub: a working clone and the REST API (forge MVP 5, spec §2).

**Only `forge_publish` holds one**, and a guard says so. The token is read from the environment by
an askpass script git runs, so it is never in a command line, a remote URL or `.git/config`, and
the API client carries it only as a header.
"""

import os
import stat
import subprocess
from pathlib import Path

import httpx
from mendel_forge.publishing import (
    GITHUB_API,
    Change,
    PublishUnavailable,
    PullRequest,
    PullRequestState,
    RegistryPublisher,
    checks_of,
)

from mendel_api.settings import settings

CLONE = "registry-publish"
GIT_TIMEOUT = 300
TOKEN_VARIABLE = "COMENI_FORGE_PUSH_TOKEN"
ASKPASS = f'#!/bin/sh\nprintf %s "${TOKEN_VARIABLE}"\n'
AUTHOR = ["-c", "user.name=Comeni forge", "-c", "user.email=forge@comeni.invalid"]


class GitHubPublisher:
    def __init__(self, repo: str, token: str, cache: Path, *, remote: str | None = None,
                 client: httpx.Client | None = None) -> None:
        self.repo, self._token, self.cache = repo, token, cache
        self.remote = remote or f"https://x-access-token@github.com/{repo}.git"
        self._client = client or httpx.Client(timeout=60.0)
        self._client.base_url = GITHUB_API
        self._client.headers.update({"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json"})

    @property
    def _clone(self) -> Path:
        return self.cache / CLONE

    def _git(self, *args: str, where: Path | None = None) -> str:
        askpass = self.cache / "askpass.sh"
        if not askpass.exists():
            askpass.write_text(ASKPASS)
            askpass.chmod(stat.S_IRWXU)
        env = {**os.environ, "GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0",
               TOKEN_VARIABLE: self._token}
        try:
            done = subprocess.run(["git", *args], cwd=where, env=env, check=True, text=True,
                                  capture_output=True, timeout=GIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise PublishUnavailable(f"`git {args[0]}` timed out") from None
        except (OSError, subprocess.CalledProcessError) as error:
            said = (getattr(error, "stderr", "") or str(error)).strip()
            raise PublishUnavailable(f"`git {args[0]}` failed: {self._safe(said)}") from None
        return done.stdout.strip()

    def _safe(self, text: str) -> str:
        return text.replace(self._token, "***") if self._token else text

    def checkout(self) -> Path:
        self.cache.mkdir(parents=True, exist_ok=True)
        if not (self._clone / ".git").is_dir():
            self._git("clone", "--quiet", self.remote, str(self._clone))
        self._git("fetch", "--quiet", "--prune", "origin", where=self._clone)
        self._git("checkout", "--quiet", "--detach", "origin/main", where=self._clone)
        self._git("clean", "-fdq", where=self._clone)
        self._git("reset", "--quiet", "--hard", "origin/main", where=self._clone)
        return self._clone

    def open_pull_request(self, change: Change) -> PullRequest:
        self._git("checkout", "--quiet", "-B", change.branch, where=self._clone)
        self._git("add", "--all", where=self._clone)
        self._git(*AUTHOR, "commit", "--quiet", "-m",
                  f"{change.title}\n\nForged by {change.author}", where=self._clone)
        self._git("push", "--quiet", "--force", "origin", f"HEAD:{change.branch}",
                  where=self._clone)
        opened = self._call("POST", f"/repos/{self.repo}/pulls", json={
            "title": change.title, "body": change.body, "head": change.branch, "base": "main"})
        return PullRequest(number=opened["number"], url=opened["html_url"], branch=change.branch)

    def _call(self, method: str, path: str, **kw) -> dict:
        try:
            answer = self._client.request(method, path, **kw)
        except httpx.HTTPError as error:
            raise PublishUnavailable(f"GitHub could not be reached: {type(error).__name__}") \
                from None
        if answer.status_code >= 400:
            raise PublishUnavailable(self._safe(
                f"GitHub refused {method} {path}: {answer.status_code} {answer.text[:300]}"))
        return answer.json()

    def state(self, number: int) -> PullRequestState:
        pull = self._call("GET", f"/repos/{self.repo}/pulls/{number}")
        head = pull["head"]["sha"]
        state = "merged" if pull.get("merged") else pull["state"]
        runs = self._call("GET", f"/repos/{self.repo}/commits/{head}/check-runs",
                          params={"per_page": 100})["check_runs"]
        checks, says = checks_of(runs)
        return PullRequestState(state=state, head=head, checks=checks, says=says)

    def merge(self, number: int, head: str) -> None:
        self._call("PUT", f"/repos/{self.repo}/pulls/{number}/merge",
                   json={"sha": head, "merge_method": "merge"})

    def close(self, number: int) -> None:
        self._call("PATCH", f"/repos/{self.repo}/pulls/{number}", json={"state": "closed"})


def publisher() -> RegistryPublisher | None:
    """The installation's publisher, or `None` with no token: publishing says so."""
    token = os.environ.get("COMENI_FORGE_GITHUB_TOKEN", "").strip()
    if not token:
        return None
    return GitHubPublisher(settings.registry_repo, token, settings.forge_cache)
