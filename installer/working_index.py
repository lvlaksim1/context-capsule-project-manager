"""Bounded, non-authoritative Project Manager working index.

The index is never a substitute for sealed BDI, commitment ledger, or typed
memory; it holds references and all active structured commitment IDs.
"""
from __future__ import annotations

import json
from typing import Any

from installer.model import (
    CapsuleModelError,
    _git_blob_sha1,
    _manager_state_integrity_errors,
    manager_state_coupled_paths,
    parse_json_text,
)

INDEX_PATH = ".context/current/working-index.json"
LEDGER_PATH = ".context/manager/commitments.json"
EVENTS_PATH = ".context/manager/durable-events.json"
MAX_DEFAULT = 8192


def _manifest(files: dict[str, str]) -> dict:
    manifest = parse_json_text(files, ".context/manifest.json")
    if not isinstance(manifest, dict):
        raise CapsuleModelError("working index requires valid capsule manifest")
    return manifest


def _ledger(files: dict[str, str], manifest: dict) -> dict[str, dict]:
    path = manifest.get("manager", {}).get("commitments")
    if path is None:
        return {}
    if path != LEDGER_PATH:
        raise CapsuleModelError("unexpected manager commitments path")
    data = parse_json_text(files, LEDGER_PATH)
    if not isinstance(data, dict) or data.get("schema") != "pm-commitments-v1":
        raise CapsuleModelError("invalid structured commitment ledger")
    commitments = data.get("items")
    if not isinstance(commitments, dict):
        raise CapsuleModelError("invalid commitment items")
    for cid, item in commitments.items():
        if not isinstance(cid, str) or not isinstance(item, dict):
            raise CapsuleModelError("invalid commitment entry")
        if item.get("status") not in ("active", "completed", "cancelled", "invalidated", "superseded"):
            raise CapsuleModelError("invalid commitment status")
        if not isinstance(item.get("statement"), str) or not item["statement"]:
            raise CapsuleModelError("missing commitment statement")
    return commitments


def index_document(files: dict[str, str], *, max_chars: int = MAX_DEFAULT) -> str:
    if max_chars < 256:
        raise CapsuleModelError("working index budget too small")
    manifest = _manifest(files)
    if _manager_state_integrity_errors(files, manifest):
        raise CapsuleModelError("working index refused: manager state seal is incoherent")
    seal_path = manifest["manager"]["state_integrity"]
    seal = parse_json_text(files, seal_path)
    if not isinstance(seal, dict):
        raise CapsuleModelError("working index requires manager state integrity marker")

    paths = manager_state_coupled_paths(manifest)
    items = _ledger(files, manifest)
    active = sorted(cid for cid, item in items.items() if item["status"] == "active")
    document: dict[str, Any] = {
        "schema": "pm-working-index-v1",
        "non_authoritative": True,
        "seal_generation": seal["generation"],
        "manager_id_path": manifest["manager"]["identity"],
        "manager_state_branch": manifest["authority"]["manager_state_branch"],
        "product_branch": manifest["authority"]["product_branch"],
        "source_paths": paths,
        "source_digests": {path: "git-blob-sha1:" + _git_blob_sha1(files[path]) for path in paths},
        "active_commitment_ids": active,
        "commitments_source": manifest.get("manager", {}).get("commitments"),
        "legacy_intentions_source": manifest["manager"]["intentions"],
        "legacy_commitments_not_machine_enumerated": True,
        "freshness": "NOT_CHECKED",
        "omitted_contents": ["full BDI text", "historical state", "handoff", "full commitment statements", "typed memory"],
        "recovery_note": "Retrieve canonical source files; index must never authorize action or override newer evidence.",
    }
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(encoded) > max_chars:
        raise CapsuleModelError(
            f"working index exceeds {max_chars}-character budget ({len(encoded)}); "
            "do not truncate unresolved commitments or canonical source references"
        )
    return encoded


def validate_index(files: dict[str, str], *, max_chars: int = MAX_DEFAULT) -> list[str]:
    actual = files.get(INDEX_PATH)
    if actual is None:
        return ["working index absent; must generate from sealed manager state"]
    try:
        expected = index_document(files, max_chars=max_chars)
    except (CapsuleModelError, ValueError, TypeError, KeyError) as exc:
        return ["working index cannot be validated: " + str(exc)]
    if actual != expected:
        return ["working index is stale, modified or sourced from a different generation"]
    return []


def read_active_commitments(files: dict[str, str]) -> list[dict]:
    """Lossless deterministic retrieval; active commitments are *not* shortened."""
    manifest = _manifest(files)
    if _manager_state_integrity_errors(files, manifest):
        raise CapsuleModelError("cannot retrieve active obligations from incoherent manager state")
    ledger = _ledger(files, manifest)
    return [dict(id=cid, **ledger[cid]) for cid in sorted(ledger) if ledger[cid]["status"] == "active"]
