from __future__ import annotations

from pathlib import Path, PurePosixPath
import re

BEGIN_MARKER = "<!-- context-capsule:begin -->"
END_MARKER = "<!-- context-capsule:end -->"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class CapsuleSafetyError(ValueError):
    pass


def validate_core_commit(value: str) -> str:
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise CapsuleSafetyError("core_commit must be a lowercase 40-character Git SHA")
    return value


def normalize_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise CapsuleSafetyError("repository path must be a non-empty string")
    if "\x00" in value or "\\" in value:
        raise CapsuleSafetyError(f"unsafe repository path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise CapsuleSafetyError(f"absolute repository path is forbidden: {value}")
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise CapsuleSafetyError(f"unsafe repository path: {value}")
    normalized = str(path)
    if normalized.startswith("../") or normalized == "..":
        raise CapsuleSafetyError(f"path escapes repository: {value}")
    return normalized


def confined_local_path(root: Path, value: str) -> Path:
    rel = normalize_repo_path(value)
    root_real = root.resolve()
    candidate = root_real / rel
    try:
        resolved = candidate.resolve(strict=False)
    except RuntimeError as exc:
        raise CapsuleSafetyError(f"cannot resolve repository path {value}: {exc}") from exc
    try:
        resolved.relative_to(root_real)
    except ValueError as exc:
        raise CapsuleSafetyError(f"path escapes repository through symlink: {value}") from exc
    return candidate


def render_managed_block(existing: str | None, body: str, *, default_heading: str) -> str:
    body = body.strip()
    block = f"{BEGIN_MARKER}\n{body}\n{END_MARKER}"
    if existing is None:
        return f"{default_heading.rstrip()}\n\n{block}\n"

    begin_count = existing.count(BEGIN_MARKER)
    end_count = existing.count(END_MARKER)
    if begin_count == 0 and end_count == 0:
        prefix = existing.rstrip()
        return f"{prefix}\n\n{block}\n" if prefix else f"{default_heading.rstrip()}\n\n{block}\n"
    if begin_count != 1 or end_count != 1:
        raise CapsuleSafetyError("malformed Context Capsule managed block markers")

    begin = existing.index(BEGIN_MARKER)
    end = existing.index(END_MARKER, begin) + len(END_MARKER)
    if existing.find(END_MARKER) < begin:
        raise CapsuleSafetyError("managed block end marker precedes begin marker")
    replacement = existing[:begin] + block + existing[end:]
    if not replacement.endswith("\n"):
        replacement += "\n"
    return replacement
