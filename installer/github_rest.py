"""Minimal GitHub Git Data backend for single-commit durable publication.

Requires GITHUB_TOKEN with contents:write on the targeted repository.
All branch moves are non-forced; publish_single_commit checks the head twice.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from installer.github_atomic import GitHubAtomicError, HeadState
from installer.safety import normalize_repo_path


class GitHubRESTBackend:
    def __init__(self, token: str):
        if not token:
            raise GitHubAtomicError("GITHUB_TOKEN with contents:write is required")
        self._token = token

    def _request(self, repository: str, path: str, *, method: str = "GET", data=None) -> dict:
        url = "https://api.github.com/repos/" + repository + path
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        request = Request(url, data=payload, method=method, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "context-capsule-project-manager",
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            code = getattr(exc, "code", "network-error")
            raise GitHubAtomicError(f"GitHub request failed ({code}); no authorization secrets logged") from None

    def get_head(self, repository: str, branch: str) -> HeadState:
        ref = self._request(repository, "/git/ref/heads/" + quote(branch, safe=""))
        sha = ref["object"]["sha"]
        commit = self._request(repository, "/git/commits/" + sha)
        return HeadState(sha, commit["tree"]["sha"])

    def create_tree(self, repository: str, base_tree_sha: str, changes: dict[str, str]) -> str:
        tree = [{
            "path": normalize_repo_path(path), "mode": "100644",
            "type": "blob", "content": content,
        } for path, content in sorted(changes.items())]
        return self._request(repository, "/git/trees", method="POST", data={
            "base_tree": base_tree_sha, "tree": tree,
        })["sha"]

    def create_commit(self, repository: str, message: str, tree_sha: str, parent_sha: str) -> str:
        return self._request(repository, "/git/commits", method="POST", data={
            "message": message, "tree": tree_sha, "parents": [parent_sha],
        })["sha"]

    def update_ref_fast_forward(self, repository: str, branch: str, new_commit_sha: str) -> bool:
        try:
            answer = self._request(repository, "/git/refs/heads/" + quote(branch, safe=""),
                method="PATCH", data={"sha": new_commit_sha, "force": False})
        except GitHubAtomicError as exc:
            # Reject instead of retrying on a possible competing branch move.
            if "(422)" in str(exc) or "(409)" in str(exc):
                return False
            raise
        return answer.get("object", {}).get("sha") == new_commit_sha
