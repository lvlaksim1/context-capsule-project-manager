from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GitHubAtomicError(RuntimeError):
    pass


class ConcurrentBranchUpdate(GitHubAtomicError):
    pass


@dataclass(frozen=True)
class HeadState:
    sha: str
    tree_sha: str


@dataclass(frozen=True)
class MutationPlan:
    repository: str
    branch: str
    expected_head: str
    commit_message: str
    changes: dict[str, str]


class GitHubBackend(Protocol):
    def get_head(self, repository: str, branch: str) -> HeadState:
        ...

    def create_tree(
        self,
        repository: str,
        base_tree_sha: str,
        changes: dict[str, str],
    ) -> str:
        ...

    def create_commit(
        self,
        repository: str,
        message: str,
        tree_sha: str,
        parent_sha: str,
    ) -> str:
        ...

    def update_ref_fast_forward(
        self,
        repository: str,
        branch: str,
        new_commit_sha: str,
    ) -> bool:
        ...


def publish_single_commit(backend: GitHubBackend, plan: MutationPlan) -> str:
    """
    Publish a complete mutation as one branch-visible commit.

    Tree/commit objects may be created before the final ref move. They are harmless
    if publication is aborted; the target branch remains unchanged.
    """
    first = backend.get_head(plan.repository, plan.branch)
    if first.sha != plan.expected_head:
        raise ConcurrentBranchUpdate(
            f"branch moved before planning was published: expected {plan.expected_head}, got {first.sha}"
        )

    tree_sha = backend.create_tree(plan.repository, first.tree_sha, plan.changes)
    commit_sha = backend.create_commit(
        plan.repository,
        plan.commit_message,
        tree_sha,
        parent_sha=plan.expected_head,
    )

    second = backend.get_head(plan.repository, plan.branch)
    if second.sha != plan.expected_head:
        raise ConcurrentBranchUpdate(
            f"branch moved before ref update: expected {plan.expected_head}, got {second.sha}"
        )

    if not backend.update_ref_fast_forward(plan.repository, plan.branch, commit_sha):
        raise ConcurrentBranchUpdate("non-forced ref update was rejected")

    return commit_sha
