from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .model import PROJECT_MANAGER_GOVERNING_PATHS
from .safety import CapsuleSafetyError, validate_core_commit


class LifecycleGuardError(ValueError):
    pass


def _git_output(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def snapshot_project_manager_commit(files: dict[str, str]) -> str:
    raw = files.get(".context/capsule.json")
    if raw is None:
        raise LifecycleGuardError("missing .context/capsule.json; cannot bind Project Manager provenance")
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LifecycleGuardError(f"invalid .context/capsule.json: {exc}") from exc
    if not isinstance(meta, dict):
        raise LifecycleGuardError(".context/capsule.json root must be an object")

    provenance = meta.get("provenance")
    if isinstance(provenance, dict):
        pm = provenance.get("project_manager")
        if isinstance(pm, dict) and isinstance(pm.get("commit"), str):
            candidate = pm["commit"]
        else:
            candidate = ""
    else:
        candidate = meta.get("project_manager_commit") or meta.get("core_commit", "")
    try:
        return validate_core_commit(candidate)
    except CapsuleSafetyError as exc:
        raise LifecycleGuardError(f"invalid declared Project Manager commit: {exc}") from exc


def snapshot_core_commit(files: dict[str, str]) -> str:
    """Deprecated compatibility alias for pre-split callers."""
    return snapshot_project_manager_commit(files)


def load_project_manager_reference(core_root: Path, core_commit: str) -> dict[str, str]:
    try:
        validate_core_commit(core_commit)
    except CapsuleSafetyError as exc:
        raise LifecycleGuardError(str(exc)) from exc

    commit = _git_output(core_root, "rev-parse", "--verify", f"{core_commit}^{{commit}}")
    if commit != core_commit:
        raise LifecycleGuardError(
            "declared Project Manager commit is not available as an exact commit in the local Project Manager Git object database; "
            "fetch the declared Project Manager commit or use a full Project Manager clone"
        )

    reference: dict[str, str] = {}
    for target_path in PROJECT_MANAGER_GOVERNING_PATHS:
        template_path = f"templates/{target_path}"
        try:
            result = subprocess.run(
                ["git", "-C", str(core_root), "show", f"{core_commit}:{template_path}"],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise LifecycleGuardError("Git is required for exact Project Manager provenance binding") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or "Git object/path unavailable"
            raise LifecycleGuardError(
                f"declared Project Manager commit cannot resolve governing template {template_path}: {detail}"
            )
        reference[target_path] = result.stdout
    return reference


def load_core_reference(core_root: Path, core_commit: str) -> dict[str, str]:
    """Deprecated compatibility alias for pre-split callers."""
    return load_project_manager_reference(core_root, core_commit)


def _effective_branch(target: Path, head: str | None) -> str | None:
    branch = _git_output(target, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch:
        return branch

    workspace = os.environ.get("GITHUB_WORKSPACE")
    ref_name = os.environ.get("GITHUB_REF_NAME")
    ref_type = os.environ.get("GITHUB_REF_TYPE")
    github_sha = os.environ.get("GITHUB_SHA")
    if not (workspace and ref_name and ref_type == "branch" and github_sha and head):
        return None
    try:
        same_workspace = Path(workspace).resolve() == target.resolve()
    except OSError:
        same_workspace = False
    if same_workspace and github_sha == head:
        return ref_name
    return None


def manager_checkout_status(
    target: Path,
    files: dict[str, str],
    *,
    expected_ref: str | None = None,
    non_authoritative: bool = False,
) -> tuple[bool, str | None, str | None]:
    raw = files.get(".context/manifest.json")
    if raw is None:
        raise LifecycleGuardError("missing .context/manifest.json; cannot verify manager-state authority")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LifecycleGuardError(f"invalid .context/manifest.json: {exc}") from exc
    authority = manifest.get("authority") if isinstance(manifest, dict) else None
    manager_branch = authority.get("manager_state_branch") if isinstance(authority, dict) else None
    if not isinstance(manager_branch, str) or not manager_branch:
        raise LifecycleGuardError("manifest has no authority.manager_state_branch")

    head = _git_output(target, "rev-parse", "--verify", "HEAD^{commit}")
    branch = _effective_branch(target, head)

    if expected_ref is not None:
        expected_sha = _git_output(target, "rev-parse", "--verify", f"{expected_ref}^{{commit}}")
        if expected_sha is None:
            raise LifecycleGuardError(f"expected manager ref cannot be resolved: {expected_ref}")
        if head != expected_sha:
            raise LifecycleGuardError(
                f"checkout HEAD {head or 'unknown'} does not match expected manager ref "
                f"{expected_ref} ({expected_sha})"
            )

    if non_authoritative:
        return False, branch, head

    if head is None:
        raise LifecycleGuardError(
            "normal READY/recover requires a Git checkout of the authoritative manager-state branch; "
            "use --non-authoritative only for maintenance/audit inspection"
        )
    if branch != manager_branch:
        raise LifecycleGuardError(
            f"checkout is not the manager-state authority branch {manager_branch!r}; "
            f"actual branch is {branch or 'detached/unknown'!r}. "
            "Use --non-authoritative only for maintenance/audit inspection."
        )
    return True, branch, head
