"""Verified durable-event ingestion and atomic manager-state transaction planning.

A mutation is prepared against an exact manager branch head. Publication is
delegated to github_atomic.publish_single_commit (one branch-visible commit).
No event silently closes an older obligation or records owner acceptance.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass

from installer.github_atomic import MutationPlan
from installer.model import (
    CapsuleModelError,
    _manager_state_integrity_errors,
    build_manager_state_integrity,
    canonical_json,
    parse_json_text,
    readiness_snapshot,
)
from installer.working_index import (
    EVENTS_PATH, INDEX_PATH, LEDGER_PATH,
    index_document, validate_index,
)

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
KINDS = frozenset({"merge", "release", "owner-acceptance", "verified-regression"})
END_STATES = {
    "complete": "completed",
    "cancel": "cancelled",
    "invalidate": "invalidated",
    "supersede": "superseded",
}


def _plain_string(value: object, name: str, *, limit: int = 900) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CapsuleModelError(f"invalid event {name}")
    if any(ord(ch) < 32 for ch in value):
        raise CapsuleModelError(f"event {name} contains control characters")
    return value.strip()


def _parse_event(event: dict, repository: str, branch: str, *, evidence_verified: bool) -> dict:
    if not isinstance(event, dict):
        raise CapsuleModelError("event must be a JSON object")
    eid = _plain_string(event.get("id"), "id", limit=80)
    if not ID_PATTERN.fullmatch(eid):
        raise CapsuleModelError("invalid durable event id")
    kind = event.get("kind")
    if kind not in KINDS:
        raise CapsuleModelError("unknown durable event kind")
    if event.get("product_repository") != repository or event.get("product_branch") != branch:
        raise CapsuleModelError("event product authority differs from the capsule manifest")
    summary = _plain_string(event.get("summary"), "summary")
    url = _plain_string(event.get("evidence_url"), "evidence_url", limit=1024)
    if not url.startswith(f"https://github.com/{repository}/") and kind != "owner-acceptance":
        raise CapsuleModelError("non-owner events require matching GitHub product evidence")
    if kind == "owner-acceptance" and event.get("owner_confirmed") is not True:
        raise CapsuleModelError("owner acceptance requires explicit owner confirmation")
    if not evidence_verified:
        raise CapsuleModelError("event evidence is not verified; aborting durable publication")
    if kind != "owner-acceptance" and event.get("owner_confirmed"):
        raise CapsuleModelError("repository evidence cannot impersonate owner acceptance")
    changes = event.get("commitments", [])
    if not isinstance(changes, list):
        raise CapsuleModelError("commitments must be an array")
    normalized = []
    seen: set[str] = set()
    for raw in changes:
        if not isinstance(raw, dict):
            raise CapsuleModelError("invalid commitment transition")
        cid = _plain_string(raw.get("id"), "commitment id", limit=80)
        if not ID_PATTERN.fullmatch(cid) or cid in seen:
            raise CapsuleModelError("invalid or repeated commitment id")
        seen.add(cid)
        op = raw.get("action")
        if op not in {"open", *END_STATES}:
            raise CapsuleModelError("unknown commitment transition")
        if op == "open":
            statement = _plain_string(raw.get("statement"), "commitment statement")
            if not isinstance(raw.get("requires_owner_acceptance", False), bool):
                raise CapsuleModelError("requires_owner_acceptance must be a boolean")
            normalized.append({
                "id": cid, "action": op, "statement": statement,
                "requires_owner_acceptance": raw.get("requires_owner_acceptance", False),
            })
        else:
            reason = _plain_string(raw.get("reason"), "commitment terminal reason")
            normalized.append({"id": cid, "action": op, "reason": reason})
    return {
        "id": eid, "kind": kind, "summary": summary,
        "evidence_url": url, "product_repository": repository,
        "product_branch": branch, "owner_confirmed": kind == "owner-acceptance",
        "commitments": normalized,
    }


def _append(text: str, heading: str, facts: list[str]) -> str:
    if not text.strip():
        raise CapsuleModelError("cannot append event to missing/empty canonical state")
    return text.rstrip("\n") + "\n\n## " + heading + "\n" + "\n".join("- " + fact for fact in facts) + "\n"


def plan_durable_event(
    files: dict[str, str],
    event: dict,
    *,
    expected_head: str,
    evidence_verified: bool,
    max_index_chars: int = 8192,
) -> MutationPlan:
    if not SHA_PATTERN.fullmatch(expected_head):
        raise CapsuleModelError("expected manager branch head must be a 40-character SHA")
    manifest = parse_json_text(files, ".context/manifest.json")
    if not isinstance(manifest, dict):
        raise CapsuleModelError("missing capsule manifest")
    sync = manifest.get("sync_policy")
    if not isinstance(sync, dict) or sync.get("manager_state_coherence_required") is not True:
        raise CapsuleModelError("durable event requires a coherence-sealed v2 manager")
    if _manager_state_integrity_errors(files, manifest):
        raise CapsuleModelError("existing manager state seal is incoherent; publication refused")
    ready, reasons = readiness_snapshot(files)
    if not ready:
        raise CapsuleModelError("manager is not READY before event: " + "; ".join(reasons))

    repo = manifest["repository"]
    authority = manifest["authority"]
    manager_branch = authority["manager_state_branch"]
    product_branch = authority["product_branch"]
    item = _parse_event(event, repo, product_branch, evidence_verified=evidence_verified)

    next_files = dict(files)
    manager = copy.deepcopy(manifest["manager"])
    if manager.get("commitments") not in (None, LEDGER_PATH):
        raise CapsuleModelError("conflicting commitments path")
    if manager.get("events") not in (None, EVENTS_PATH):
        raise CapsuleModelError("conflicting durable events path")
    manager["commitments"], manager["events"] = LEDGER_PATH, EVENTS_PATH
    updated_manifest = copy.deepcopy(manifest)
    updated_manifest["manager"] = manager

    commitments = (
        parse_json_text(files, LEDGER_PATH)
        if LEDGER_PATH in files else {"schema": "pm-commitments-v1", "items": {}}
    )
    history = (
        parse_json_text(files, EVENTS_PATH)
        if EVENTS_PATH in files else {"schema": "pm-events-v1", "entries": []}
    )
    if not isinstance(commitments, dict) or commitments.get("schema") != "pm-commitments-v1" or not isinstance(commitments.get("items"), dict):
        raise CapsuleModelError("malformed commitment ledger")
    if not isinstance(history, dict) or history.get("schema") != "pm-events-v1" or not isinstance(history.get("entries"), list):
        raise CapsuleModelError("malformed durable event history")
    if any(not isinstance(e, dict) or not isinstance(e.get("id"), str) for e in history["entries"]):
        raise CapsuleModelError("malformed historical event entry")
    if any(e["id"] == item["id"] for e in history["entries"]):
        raise CapsuleModelError("durable event id already published")
    commitments = copy.deepcopy(commitments)
    history = copy.deepcopy(history)
    for change in item["commitments"]:
        cid, action = change["id"], change["action"]
        old = commitments["items"].get(cid)
        if action == "open":
            if old is not None:
                raise CapsuleModelError("commitment already exists: " + cid)
            commitments["items"][cid] = {
                "statement": change["statement"],
                "status": "active",
                "requires_owner_acceptance": change["requires_owner_acceptance"],
                "opened_by": item["id"], "opened_evidence": item["evidence_url"],
                "closed_by": None,
            }
        else:
            if not isinstance(old, dict) or old.get("status") != "active":
                raise CapsuleModelError("cannot finish missing/inactive commitment: " + cid)
            if action == "complete" and old.get("requires_owner_acceptance") and item["kind"] != "owner-acceptance":
                raise CapsuleModelError("owner acceptance is required to complete: " + cid)
            old["status"] = END_STATES[action]
            old["terminal_reason"] = change["reason"]
            old["closed_by"] = item["id"]
            old["terminal_evidence"] = item["evidence_url"]

    history["entries"].append(item)
    next_files[LEDGER_PATH] = canonical_json(commitments)
    next_files[EVENTS_PATH] = canonical_json(history)
    next_files[".context/manifest.json"] = canonical_json(updated_manifest)

    heading = f"Durable event {item['id']} ({item['kind']})"
    source = "source: " + item["evidence_url"]
    provenance = "authority: " + ("owner-confirmed" if item["owner_confirmed"] else "verified-github")
    # GitHub verifies the operation, not arbitrary semantic claims supplied in JSON.
    evidence_fact = f"Verified evidence: {item['kind']} at {item['evidence_url']}"
    scope = ("Owner-confirmed scope: " if item["owner_confirmed"] else "Reported scope (not independently verified): ") + item["summary"]
    details = [evidence_fact, scope, source, provenance]
    if item["commitments"]:
        details.append("Commitments: " + ", ".join(f"{c['id']}={c['action']}" for c in item["commitments"]))
    for section, key in (
        ("manager", "beliefs"), ("manager", "intentions"), ("manager", "plans"),
        ("current", "state"), ("current", "next"),
    ):
        path = manifest[section][key]
        next_files[path] = _append(files[path], heading, details)
    handoff = manifest["latest_handoff"]
    next_files[handoff] = _append(files[handoff], heading, details)

    seal_path = manager["state_integrity"]
    previous = parse_json_text(files, seal_path)
    next_files[seal_path] = canonical_json(build_manager_state_integrity(
        next_files, updated_manifest, existing=previous
    ))
    next_files[INDEX_PATH] = index_document(next_files, max_chars=max_index_chars)
    index_errors = validate_index(next_files, max_chars=max_index_chars)
    if index_errors:
        raise CapsuleModelError("; ".join(index_errors))
    ready, reasons = readiness_snapshot(next_files)
    if not ready:
        raise CapsuleModelError("post-event manager not READY: " + "; ".join(reasons))
    changes = {path: content for path, content in next_files.items() if files.get(path) != content}
    return MutationPlan(repo, manager_branch, expected_head, "durable: " + item["id"] + " " + item["kind"], changes)
