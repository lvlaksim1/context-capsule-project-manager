from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from .safety import CapsuleSafetyError, normalize_repo_path, render_managed_block, validate_core_commit

VERSION = "2.0.0-dev"
SOURCE_REPOSITORY = "lvlaksim1/context-capsule-project-manager"
CONTEXT_CAPSULE_REPOSITORY = "lvlaksim1/context-capsule"
DEFAULT_CONTEXT_CAPSULE_COMMIT = "2ef41a5ed57ae514cc5980065560d7e55d5e4b9a"
MANIFEST_SCHEMA_VERSION = 4
MANAGER_IDENTITY_SCHEMA_VERSION = 1
MANAGER_IDENTITY_PATH = ".context/manager/identity.json"
MANAGER_STATE_INTEGRITY_PATH = ".context/manager/state-integrity.json"
MANAGER_STATE_INTEGRITY_SCHEMA_VERSION = 1

SYSTEM_TEXT_PATHS = (
    ".context/ENTRYPOINT.md",
    ".context/protocol.md",
    ".context/manager/CONTRACT.md",
    ".context/manager/PROTOCOL.md",
)
PROJECT_MANAGER_GOVERNING_PATHS = SYSTEM_TEXT_PATHS
CORE_GOVERNING_PATHS = PROJECT_MANAGER_GOVERNING_PATHS  # deprecated compatibility alias
_PROVENANCE_ENTRY_START = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
PROJECT_SEED_PATHS = (
    ".context/project/identity.md",
    ".context/project/goals.md",
    ".context/project/architecture.md",
    ".context/project/constraints.md",
    ".context/current/state.md",
    ".context/current/blockers.md",
    ".context/current/next.md",
    ".context/rules/project-rules.md",
    ".context/decisions/README.md",
    ".context/handoffs/latest.md",
    ".context/dialogues/README.md",
    ".context/history/README.md",
    ".context/manager/mandate.md",
    ".context/manager/beliefs.md",
    ".context/manager/goals.md",
    ".context/manager/intentions.md",
    ".context/manager/plans.md",
    ".context/memory/index.md",
    ".context/memory/semantic.md",
    ".context/memory/procedural.md",
    ".context/memory/episodes/README.md",
)
BOOTSTRAP_FILES = ("AI_CONTEXT.md", "AGENTS.md")

PLACEHOLDER_PATTERNS = (
    "capture the ",
    "capture durable ",
    "not yet captured",
    "no handoff recorded yet",
    "perform initial context capture",
    "no project-specific rules have been captured",
    "record only ",
    "record the currently actionable",
    "describe the manager",
    "define what the manager",
    "record current verified beliefs",
    "record the active goals",
    "record active commitments",
    "record the current plan",
    "record reusable durable knowledge",
    "record learned procedures",
)
_MANAGER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


class CapsuleModelError(ValueError):
    pass


def canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def parse_json_text(files: dict[str, str], path: str) -> dict | None:
    text = files.get(path)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CapsuleModelError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CapsuleModelError(f"JSON root must be an object: {path}")
    return value


def _load_template(template_root: Path, rel: str) -> str:
    path = template_root / rel
    if not path.exists():
        raise CapsuleModelError(f"missing Core template: {rel}")
    return path.read_text(encoding="utf-8")


def _bootstrap_body(kind: str, template_root: Path) -> str:
    path = template_root / kind
    if not path.exists():
        raise CapsuleModelError(f"missing Core bootstrap template: {kind}")
    return path.read_text(encoding="utf-8").strip()


def bootstrap_changes(files: dict[str, str], template_root: Path) -> dict[str, str]:
    return {
        "AI_CONTEXT.md": render_managed_block(
            files.get("AI_CONTEXT.md"),
            _bootstrap_body("AI_CONTEXT.md", template_root),
            default_heading="# AI Context",
        ),
        "AGENTS.md": render_managed_block(
            files.get("AGENTS.md"),
            _bootstrap_body("AGENTS.md", template_root),
            default_heading="# Agent Instructions",
        ),
    }


def discovery_redirect_changes(
    files: dict[str, str],
    template_root: Path,
    authoritative_branch: str,
    discovery_branch: str,
) -> dict[str, str | None]:
    if authoritative_branch == discovery_branch:
        raise CapsuleModelError("discovery redirect requires different authoritative and discovery branches")

    def discovery_text(name: str) -> str:
        text = _load_template(template_root, f"discovery/{name}")
        return text.replace("{{AUTHORITATIVE_BRANCH}}", authoritative_branch).replace(
            "{{DISCOVERY_BRANCH}}", discovery_branch
        )

    changes: dict[str, str | None] = {
        "AI_CONTEXT.md": render_managed_block(
            files.get("AI_CONTEXT.md"), discovery_text("AI_CONTEXT.md").strip(), default_heading="# AI Context"
        ),
        "AGENTS.md": render_managed_block(
            files.get("AGENTS.md"), discovery_text("AGENTS.md").strip(), default_heading="# Agent Instructions"
        ),
        ".context/ENTRYPOINT.md": discovery_text(".context/ENTRYPOINT.md"),
    }
    for path in files:
        if path.startswith(".context/") and path != ".context/ENTRYPOINT.md":
            changes[path] = None
    return changes


def build_capsule_metadata(
    repository: str,
    core_commit: str,
    *,
    context_capsule_commit: str | None = None,
    existing: dict | None = None,
    adopted_from: str | None = None,
) -> dict:
    # Compatibility note: the historical parameter name core_commit carries the
    # Project Manager source commit for v2. New metadata records both products.
    project_manager_commit = validate_core_commit(core_commit)
    context_capsule_commit = validate_core_commit(
        context_capsule_commit or DEFAULT_CONTEXT_CAPSULE_COMMIT
    )
    old = copy.deepcopy(existing or {})
    result = old
    result.update(
        {
            "schema": "context-capsule",
            "version": VERSION,
            "source": SOURCE_REPOSITORY,
            # Deprecated compatibility alias retained for existing v2 consumers.
            "core_commit": project_manager_commit,
            "project_manager_commit": project_manager_commit,
            "context_capsule_commit": context_capsule_commit,
            "provenance": {
                "context_capsule": {
                    "repository": CONTEXT_CAPSULE_REPOSITORY,
                    "commit": context_capsule_commit,
                },
                "project_manager": {
                    "repository": SOURCE_REPOSITORY,
                    "commit": project_manager_commit,
                },
            },
            "installed_at": old.get("installed_at") or dt.date.today().isoformat(),
            "repository": repository,
            "update_policy": "manual",
        }
    )
    if adopted_from:
        result["adopted_from"] = adopted_from
    return result

def build_manager_identity(repository: str, *, existing: dict | None = None) -> dict:
    old = copy.deepcopy(existing or {})
    manager_id = old.get("manager_id") or "project-manager"
    result = old
    result.update(
        {
            "schema": "context-capsule-manager-identity",
            "schema_version": MANAGER_IDENTITY_SCHEMA_VERSION,
            "manager_id": manager_id,
            "role": old.get("role") or "Project Manager",
            "repository": repository,
            "continuity": "runtime-independent",
            "authority_model": "bounded-by-mandate",
            "state_model": "beliefs-goals-intentions-plans",
            "memory_model": "typed-with-provenance",
        }
    )
    return result


def _merge_unique(existing: object, discovered: Iterable[str]) -> list[str]:
    result: list[str] = []
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item not in result:
                result.append(item)
    for item in discovered:
        if item not in result:
            result.append(item)
    return result


def _markdown_files(files: dict[str, str], prefix: str, *, omit_readme: bool = True) -> list[str]:
    prefix = prefix.rstrip("/") + "/"
    result = []
    for path in sorted(files):
        if not path.startswith(prefix) or not path.endswith(".md"):
            continue
        if omit_readme and path.lower().endswith("/readme.md"):
            continue
        result.append(path)
    return result


def _copy_nested(existing: dict, key: str) -> dict:
    value = existing.get(key)
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def build_manifest(
    files: dict[str, str],
    repository: str,
    branch: str,
    *,
    existing: dict | None = None,
    redirect_topology: tuple[str, str] | None = None,
    product_branch: str | None = None,
) -> dict:
    old = copy.deepcopy(existing or {})
    manifest = old

    if redirect_topology:
        authoritative_branch, discovery_branch = redirect_topology
        branch_mode = "redirect" if authoritative_branch != discovery_branch else "single"
    elif existing:
        authoritative_branch = old.get("authoritative_branch") or branch
        discovery_branch = old.get("discovery_branch") or authoritative_branch
        branch_mode = old.get("branch_mode") or (
            "redirect" if authoritative_branch != discovery_branch else "single"
        )
    else:
        authoritative_branch = branch
        discovery_branch = branch
        branch_mode = "single"

    authority_old = _copy_nested(old, "authority")
    product_authority_branch = product_branch or authority_old.get("product_branch")
    if not isinstance(product_authority_branch, str) or not product_authority_branch:
        product_authority_branch = discovery_branch if branch_mode == "redirect" else authoritative_branch
    authority_old.update(
        {
            "manager_state_branch": authoritative_branch,
            "product_branch": product_authority_branch,
        }
    )

    project_old = _copy_nested(old, "project")
    project_old.update(
        {
            "identity": project_old.get("identity") or ".context/project/identity.md",
            "goals": project_old.get("goals") or ".context/project/goals.md",
            "architecture": project_old.get("architecture") or ".context/project/architecture.md",
            "constraints": project_old.get("constraints") or ".context/project/constraints.md",
        }
    )

    current_old = _copy_nested(old, "current")
    current_old.update(
        {
            "state": current_old.get("state") or old.get("current_state") or ".context/current/state.md",
            "blockers": current_old.get("blockers") or ".context/current/blockers.md",
            "next": current_old.get("next") or ".context/current/next.md",
        }
    )

    manager_old = _copy_nested(old, "manager")
    manager_old.update(
        {
            "contract": manager_old.get("contract") or ".context/manager/CONTRACT.md",
            "protocol": manager_old.get("protocol") or ".context/manager/PROTOCOL.md",
            "identity": manager_old.get("identity") or MANAGER_IDENTITY_PATH,
            "mandate": manager_old.get("mandate") or ".context/manager/mandate.md",
            "beliefs": manager_old.get("beliefs") or ".context/manager/beliefs.md",
            "goals": manager_old.get("goals") or ".context/manager/goals.md",
            "intentions": manager_old.get("intentions") or ".context/manager/intentions.md",
            "plans": manager_old.get("plans") or ".context/manager/plans.md",
            "state_integrity": manager_old.get("state_integrity") or MANAGER_STATE_INTEGRITY_PATH,
        }
    )

    memory_old = _copy_nested(old, "memory")
    memory_old.update(
        {
            "index": memory_old.get("index") or ".context/memory/index.md",
            "semantic": memory_old.get("semantic") or ".context/memory/semantic.md",
            "procedural": memory_old.get("procedural") or ".context/memory/procedural.md",
            "episodes": _merge_unique(
                memory_old.get("episodes"), _markdown_files(files, ".context/memory/episodes")
            ),
        }
    )

    runtime_old = _copy_nested(old, "runtime")
    runtime_paths = runtime_old.get("authoritative_paths")
    if not isinstance(runtime_paths, list):
        runtime_paths = []
    runtime_old.update(
        {
            "authoritative_paths": runtime_paths,
            "volatile": bool(runtime_old.get("volatile", bool(runtime_paths))),
            "promote_semantic_changes_only": bool(
                runtime_old.get("promote_semantic_changes_only", bool(runtime_paths))
            ),
            "checkpoint_is_capsule_state": False,
        }
    )

    sync_old = _copy_nested(old, "sync_policy")
    sync_old.update(
        {
            "semantic_only": True,
            "volatile_runtime_excluded": True,
            "atomic_git_publication": True,
            "provenance_required_for_manager_beliefs": True,
            "working_views_non_authoritative": True,
            "freshness_not_supersession": True,
            "owner_directives_must_be_explicit": True,
            "commitment_lifecycle_required": True,
            "memory_writes_require_provenance": True,
            "durable_finding_gate_required": True,
            "reconcile_before_high_impact_action": True,
            "self_authority_expansion_forbidden": True,
            "service_expertise_not_project_authority": True,
            "direct_owner_invocation_first_class": True,
            "interactive_first_execution_required": True,
            "autonomous_scheduler_fallback_only": True,
            "task_scoped_live_carrier_required": True,
            "scheduler_global_shutdown_on_owner_presence_forbidden": True,
            "expired_live_carrier_fallback_supported": True,
            "live_bounded_delegation_return_required": True,
            "delegation_preserves_commitment_owner": True,
            "explicit_handoff_required_for_responsibility_transfer": True,
            "responsibility_authority_orthogonal": True,
            "handoff_requires_target_acceptance": True,
            "delegated_authority_attenuation_required": True,
            "authority_root_provenance_required": True,
            "subdelegation_inherits_constraints": True,
            "owner_root_grant_normalized": True,
            "first_delegation_attenuates_owner_grant": True,
            "delegated_scope_attenuation_required": True,
            "handoff_acceptance_target_home_verified": True,
            "handoff_acceptance_execution_fence_bound": True,
            "external_task_authority_non_escalating": True,
            "supplied_execution_fence_enforced": True,
            "evidence_backed_external_completion_required": True,
            "terminal_execution_cleanup_required": True,
            "external_gate_reconciliation_required": True,
            "manager_state_coherence_required": True,
        }
    )

    manifest.update(
        {
            "schema": "context-capsule-manifest",
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "repository": repository,
            "authority": authority_old,
            "authoritative_branch": authoritative_branch,
            "discovery_branch": discovery_branch,
            "branch_mode": branch_mode,
            "entrypoint": old.get("entrypoint") or ".context/ENTRYPOINT.md",
            "capsule_metadata": ".context/capsule.json",
            "protocol": old.get("protocol") or ".context/protocol.md",
            "latest_handoff": old.get("latest_handoff")
            or old.get("active_handoff")
            or ".context/handoffs/latest.md",
            "project": project_old,
            "manager": manager_old,
            "memory": memory_old,
            "current": current_old,
            "current_state": current_old["state"],
            "rules": _merge_unique(old.get("rules"), _markdown_files(files, ".context/rules")),
            "decisions": _merge_unique(old.get("decisions"), _markdown_files(files, ".context/decisions")),
            "dialogues": _merge_unique(old.get("dialogues"), _markdown_files(files, ".context/dialogues")),
            "history": _merge_unique(old.get("history"), _markdown_files(files, ".context/history")),
            "runtime": runtime_old,
            "sync_policy": sync_old,
            "updated_at": dt.date.today().isoformat(),
            "context_version": VERSION,
        }
    )
    if not manifest["rules"] and ".context/rules/project-rules.md" in files:
        manifest["rules"] = [".context/rules/project-rules.md"]
    return manifest


def referenced_paths(manifest: dict) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for key in ("entrypoint", "capsule_metadata", "protocol", "latest_handoff"):
        value = manifest.get(key)
        if isinstance(value, str):
            refs.append((key, value))
    project = manifest.get("project")
    if isinstance(project, dict):
        for key in ("identity", "goals", "architecture", "constraints"):
            value = project.get(key)
            if isinstance(value, str):
                refs.append((f"project.{key}", value))
    manager = manifest.get("manager")
    if isinstance(manager, dict):
        for key in ("contract", "protocol", "identity", "mandate", "beliefs", "goals", "intentions", "plans", "state_integrity"):
            value = manager.get(key)
            if isinstance(value, str):
                refs.append((f"manager.{key}", value))
    memory = manifest.get("memory")
    if isinstance(memory, dict):
        for key in ("index", "semantic", "procedural"):
            value = memory.get(key)
            if isinstance(value, str):
                refs.append((f"memory.{key}", value))
        episodes = memory.get("episodes")
        if isinstance(episodes, list):
            for index, item in enumerate(episodes):
                if isinstance(item, str):
                    refs.append((f"memory.episodes[{index}]", item))
    current = manifest.get("current")
    if isinstance(current, dict):
        for key in ("state", "blockers", "next"):
            value = current.get(key)
            if isinstance(value, str):
                refs.append((f"current.{key}", value))
    for key in ("rules", "decisions", "dialogues", "history"):
        value = manifest.get(key)
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    refs.append((f"{key}[{index}]", item))
    return refs


def _validate_manager_identity(files: dict[str, str], repository: str | None) -> list[str]:
    errors: list[str] = []
    try:
        identity = parse_json_text(files, MANAGER_IDENTITY_PATH)
    except CapsuleModelError as exc:
        return [str(exc)]
    if identity is None:
        return [f"missing {MANAGER_IDENTITY_PATH}"]
    if identity.get("schema") != "context-capsule-manager-identity":
        errors.append("manager identity: invalid schema")
    if identity.get("schema_version") != MANAGER_IDENTITY_SCHEMA_VERSION:
        errors.append(f"manager identity: schema_version must be {MANAGER_IDENTITY_SCHEMA_VERSION}")
    manager_id = identity.get("manager_id")
    if not isinstance(manager_id, str) or not _MANAGER_ID.fullmatch(manager_id):
        errors.append("manager identity: manager_id must be a stable 3-128 character identifier")
    if identity.get("continuity") != "runtime-independent":
        errors.append("manager identity: continuity must be runtime-independent")
    if repository and identity.get("repository") != repository:
        errors.append("manager identity repository does not match capsule repository")
    return errors


def validate_snapshot(
    files: dict[str, str],
    *,
    core_reference: dict[str, str] | None = None,
    require_core_binding: bool = False,
) -> list[str]:
    errors: list[str] = []
    try:
        meta = parse_json_text(files, ".context/capsule.json")
    except CapsuleModelError as exc:
        errors.append(str(exc))
        meta = None
    try:
        manifest = parse_json_text(files, ".context/manifest.json")
    except CapsuleModelError as exc:
        errors.append(str(exc))
        manifest = None

    if meta is None:
        errors.append("missing .context/capsule.json")
    else:
        if meta.get("schema") != "context-capsule":
            errors.append("capsule.json: invalid schema")
        if meta.get("version") != VERSION:
            errors.append(f"capsule.json: version must be {VERSION}; use explicit upgrade for older capsules")
        provenance = meta.get("provenance")
        if isinstance(provenance, dict):
            pm = provenance.get("project_manager")
            cc = provenance.get("context_capsule")
            if not isinstance(pm, dict) or pm.get("repository") != SOURCE_REPOSITORY:
                errors.append("capsule.json: provenance.project_manager.repository is invalid")
            if not isinstance(cc, dict) or cc.get("repository") != CONTEXT_CAPSULE_REPOSITORY:
                errors.append("capsule.json: provenance.context_capsule.repository is invalid")
            try:
                pm_commit = validate_core_commit(pm.get("commit", "") if isinstance(pm, dict) else "")
                cc_commit = validate_core_commit(cc.get("commit", "") if isinstance(cc, dict) else "")
                if meta.get("project_manager_commit") not in (None, pm_commit):
                    errors.append("capsule.json: project_manager_commit disagrees with provenance")
                if meta.get("context_capsule_commit") not in (None, cc_commit):
                    errors.append("capsule.json: context_capsule_commit disagrees with provenance")
                if meta.get("core_commit") not in (None, pm_commit):
                    errors.append("capsule.json: deprecated core_commit alias disagrees with Project Manager provenance")
            except CapsuleSafetyError as exc:
                errors.append(f"capsule.json: {exc}")
        else:
            # Legacy v2 metadata: core_commit historically carried the PM source commit.
            try:
                validate_core_commit(meta.get("core_commit", ""))
            except CapsuleSafetyError as exc:
                errors.append(f"capsule.json: {exc}")
        if not isinstance(meta.get("repository"), str) or meta["repository"].count("/") != 1:
            errors.append("capsule.json: repository must be owner/name")
        if meta.get("update_policy") != "manual":
            errors.append("capsule.json: update_policy must be manual")

    for path in SYSTEM_TEXT_PATHS:
        if path not in files:
            errors.append(f"missing system file: {path}")
    for path in BOOTSTRAP_FILES:
        if path not in files:
            errors.append(f"missing bootstrap file: {path}")

    if manifest is None:
        errors.append("missing .context/manifest.json")
    else:
        if manifest.get("schema") != "context-capsule-manifest":
            errors.append("manifest.json: invalid schema")
        if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            errors.append(f"manifest.json: schema_version must be {MANIFEST_SCHEMA_VERSION}")
        authority = manifest.get("authority")
        if not isinstance(authority, dict):
            errors.append("manifest.json: authority section is required")
        else:
            manager_state_branch = authority.get("manager_state_branch")
            product_authority_branch = authority.get("product_branch")
            if not isinstance(manager_state_branch, str) or not manager_state_branch:
                errors.append("manifest.json: authority.manager_state_branch is required")
            if not isinstance(product_authority_branch, str) or not product_authority_branch:
                errors.append("manifest.json: authority.product_branch is required")
            if manager_state_branch != manifest.get("authoritative_branch"):
                errors.append("manifest.json: authoritative_branch must alias authority.manager_state_branch")
        if manifest.get("branch_mode") not in ("single", "redirect"):
            errors.append("manifest.json: branch_mode must be single or redirect")
        if not isinstance(manifest.get("authoritative_branch"), str) or not manifest.get("authoritative_branch"):
            errors.append("manifest.json: authoritative_branch is required")
        if not isinstance(manifest.get("discovery_branch"), str) or not manifest.get("discovery_branch"):
            errors.append("manifest.json: discovery_branch is required")
        if meta and manifest.get("repository") != meta.get("repository"):
            errors.append("manifest.json repository does not match capsule.json")
        if not isinstance(manifest.get("manager"), dict):
            errors.append("manifest.json: manager section is required")
        if not isinstance(manifest.get("memory"), dict):
            errors.append("manifest.json: memory section is required")

        for label, raw_path in referenced_paths(manifest):
            try:
                safe = normalize_repo_path(raw_path)
            except CapsuleSafetyError as exc:
                errors.append(f"manifest.json {label}: {exc}")
                continue
            if safe not in files:
                errors.append(f"manifest.json {label}: referenced path does not exist: {safe}")

        sync = manifest.get("sync_policy")
        if not isinstance(sync, dict) or sync.get("semantic_only") is not True:
            errors.append("manifest.json: sync_policy.semantic_only must be true")
        if not isinstance(sync, dict) or sync.get("atomic_git_publication") is not True:
            errors.append("manifest.json: sync_policy.atomic_git_publication must be true")
        if not isinstance(sync, dict) or sync.get("provenance_required_for_manager_beliefs") is not True:
            errors.append("manifest.json: manager belief provenance must be required")
        if not isinstance(sync, dict) or sync.get("working_views_non_authoritative") is not True:
            errors.append("manifest.json: current/handoff working views must be non-authoritative")
        if not isinstance(sync, dict) or sync.get("freshness_not_supersession") is not True:
            errors.append("manifest.json: evidence freshness must not imply semantic supersession")
        if not isinstance(sync, dict) or sync.get("owner_directives_must_be_explicit") is not True:
            errors.append("manifest.json: owner directives must remain explicit")
        if not isinstance(sync, dict) or sync.get("commitment_lifecycle_required") is not True:
            errors.append("manifest.json: manager commitment lifecycle must be explicit")
        if not isinstance(sync, dict) or sync.get("memory_writes_require_provenance") is not True:
            errors.append("manifest.json: durable memory writes must preserve provenance")
        if not isinstance(sync, dict) or sync.get("durable_finding_gate_required") is not True:
            errors.append("manifest.json: verified reusable findings must pass the durable finding gate")
        if not isinstance(sync, dict) or sync.get("reconcile_before_high_impact_action") is not True:
            errors.append("manifest.json: high-impact action requires prior reconciliation")
        if not isinstance(sync, dict) or sync.get("self_authority_expansion_forbidden") is not True:
            errors.append("manifest.json: manager must not self-expand authority")
        if not isinstance(sync, dict) or sync.get("service_expertise_not_project_authority") is not True:
            errors.append("manifest.json: service expertise must not imply project authority")
        if not isinstance(sync, dict) or sync.get("direct_owner_invocation_first_class") is not True:
            errors.append("manifest.json: direct owner invocation must remain first-class")
        if not isinstance(sync, dict) or sync.get("interactive_first_execution_required") is not True:
            errors.append("manifest.json: interactive-first execution must be required")
        if not isinstance(sync, dict) or sync.get("autonomous_scheduler_fallback_only") is not True:
            errors.append("manifest.json: autonomous scheduler transport must remain fallback-only")
        if not isinstance(sync, dict) or sync.get("task_scoped_live_carrier_required") is not True:
            errors.append("manifest.json: interactive live carriers must be task-scoped")
        if not isinstance(sync, dict) or sync.get("scheduler_global_shutdown_on_owner_presence_forbidden") is not True:
            errors.append("manifest.json: owner presence must not globally disable scheduler infrastructure")
        if not isinstance(sync, dict) or sync.get("expired_live_carrier_fallback_supported") is not True:
            errors.append("manifest.json: expired live carriers must support declared autonomous fallback")
        if not isinstance(sync, dict) or sync.get("live_bounded_delegation_return_required") is not True:
            errors.append("manifest.json: bounded live delegation must automatically return to its caller")
        if not isinstance(sync, dict) or sync.get("delegation_preserves_commitment_owner") is not True:
            errors.append("manifest.json: bounded delegation must preserve caller commitment ownership")
        if not isinstance(sync, dict) or sync.get("explicit_handoff_required_for_responsibility_transfer") is not True:
            errors.append("manifest.json: responsibility transfer requires explicit handoff")
        if not isinstance(sync, dict) or sync.get("responsibility_authority_orthogonal") is not True:
            errors.append("manifest.json: responsibility and authority must remain orthogonal")
        if not isinstance(sync, dict) or sync.get("handoff_requires_target_acceptance") is not True:
            errors.append("manifest.json: explicit handoff requires target acceptance")
        if not isinstance(sync, dict) or sync.get("delegated_authority_attenuation_required") is not True:
            errors.append("manifest.json: delegated authority must attenuate")
        if not isinstance(sync, dict) or sync.get("authority_root_provenance_required") is not True:
            errors.append("manifest.json: nested delegation must preserve root authority provenance")
        if not isinstance(sync, dict) or sync.get("subdelegation_inherits_constraints") is not True:
            errors.append("manifest.json: subdelegation must inherit constraints")
        if not isinstance(sync, dict) or sync.get("external_task_authority_non_escalating") is not True:
            errors.append("manifest.json: external task transport must not escalate authority")
        if not isinstance(sync, dict) or sync.get("supplied_execution_fence_enforced") is not True:
            errors.append("manifest.json: supplied execution fences must guard consequential writes")
        if not isinstance(sync, dict) or sync.get("evidence_backed_external_completion_required") is not True:
            errors.append("manifest.json: external completion must be evidence-backed")
        if not isinstance(sync, dict) or sync.get("terminal_execution_cleanup_required") is not True:
            errors.append("manifest.json: terminal external execution must clear active ownership")
        if not isinstance(sync, dict) or sync.get("external_gate_reconciliation_required") is not True:
            errors.append("manifest.json: pending external gates must be reconciled against authoritative durable results")
        coherence_required = isinstance(sync, dict) and sync.get("manager_state_coherence_required") is True
        manager_section = manifest.get("manager") if isinstance(manifest.get("manager"), dict) else {}
        integrity_path = manager_section.get("state_integrity") if isinstance(manager_section, dict) else None
        if coherence_required and not isinstance(integrity_path, str):
            errors.append("manifest.json: manager_state_coherence_required needs manager.state_integrity")
        if isinstance(integrity_path, str) and not coherence_required:
            errors.append("manifest.json: manager.state_integrity requires manager_state_coherence_required=true")
        runtime = manifest.get("runtime")
        if not isinstance(runtime, dict) or runtime.get("checkpoint_is_capsule_state") is not False:
            errors.append("manifest.json: runtime checkpoint must remain separate from capsule state")

    repository = meta.get("repository") if isinstance(meta, dict) else None
    errors.extend(_validate_manager_identity(files, repository))
    errors.extend(_core_binding_errors(files, core_reference, require_core_binding=require_core_binding))
    return errors


def _semantic_text(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _is_substantive(text: str | None) -> bool:
    if text is None:
        return False
    body = _semantic_text(text)
    if len(body) < 32:
        return False
    lower = body.lower()
    # Placeholder detection must identify template text itself, not reject real
    # project state merely because it contains generic phrases such as
    # "capture the ..." or "record the ...".
    return not any(lower.startswith(pattern) for pattern in PLACEHOLDER_PATTERNS)


def _durable_entry_spans(text: str | None) -> tuple[list[str], list[tuple[int, int, str]]]:
    if text is None:
        return [], []
    lines = text.splitlines()

    section_starts = [
        index
        for index, raw in enumerate(lines)
        if raw.strip().startswith("## ")
    ]
    if section_starts:
        spans = []
        for pos, start in enumerate(section_starts):
            end = section_starts[pos + 1] if pos + 1 < len(section_starts) else len(lines)
            spans.append((start, end, "section"))
        return lines, spans

    top_level_bullets = [
        index
        for index, raw in enumerate(lines)
        if raw == raw.lstrip() and _PROVENANCE_ENTRY_START.match(raw.strip())
    ]
    if top_level_bullets:
        spans = []
        for pos, start in enumerate(top_level_bullets):
            end = top_level_bullets[pos + 1] if pos + 1 < len(top_level_bullets) else len(lines)
            spans.append((start, end, "bullet"))
        return lines, spans

    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    for index, raw in enumerate(lines + [""]):
        stripped = raw.strip()
        is_content = bool(stripped) and not stripped.startswith("#") and not stripped.startswith("<!--")
        if is_content and start is None:
            start = index
        elif not is_content and start is not None:
            spans.append((start, index, "paragraph"))
            start = None
    return lines, spans


def _durable_entries(text: str | None) -> list[str]:
    lines, spans = _durable_entry_spans(text)
    entries: list[str] = []
    for start, end, _kind in spans:
        entry = " ".join(
            raw.strip()
            for raw in lines[start:end]
            if raw.strip() and not raw.strip().startswith("<!--")
        ).strip()
        if entry:
            entries.append(entry)
    return entries


def _entry_provenance_errors(text: str | None, label: str) -> list[str]:
    if not _is_substantive(text):
        return []
    errors: list[str] = []
    for index, entry in enumerate(_durable_entries(text), start=1):
        lower = entry.lower()
        missing = []
        if "source:" not in lower:
            missing.append("source:")
        if "authority:" not in lower:
            missing.append("authority:")
        if missing:
            errors.append(
                f"{label} entry {index} missing provenance field(s): {', '.join(missing)}"
            )
    return errors


def _normalize_legacy_provenance_text(text: str) -> tuple[str, int]:
    if not _is_substantive(text):
        return text, 0

    lines, spans = _durable_entry_spans(text)
    changed = 0
    for start, end, kind in reversed(spans):
        entry = " ".join(raw.strip() for raw in lines[start:end] if raw.strip()).lower()
        missing_source = "source:" not in entry
        missing_authority = "authority:" not in entry
        if not (missing_source or missing_authority):
            continue

        additions: list[str] = []
        if missing_source:
            additions.append("source: legacy-v2-state")
        if missing_authority:
            additions.append("authority: legacy-unverified")

        if kind == "section":
            insert = []
            if end > start and lines[end - 1].strip():
                insert.append("")
            insert.extend(f"- {item}" for item in additions)
            lines[end:end] = insert
        elif kind == "bullet":
            lines[end:end] = [f"  - {item}" for item in additions]
        else:
            index = end - 1
            while index >= start and not lines[index].strip():
                index -= 1
            if index < start:
                continue
            lines[index] = lines[index].rstrip() + " " + "; ".join(additions)
        changed += 1

    normalized = "\n".join(lines)
    if text.endswith("\n"):
        normalized += "\n"

    residual = _entry_provenance_errors(normalized, "legacy provenance")
    if residual:
        raise CapsuleModelError(
            "legacy provenance normalization could not safely attribute every durable entry: "
            + "; ".join(residual)
        )
    return normalized, changed


def legacy_provenance_changes(files: dict[str, str]) -> dict[str, str]:
    manifest = parse_json_text(files, ".context/manifest.json") or {}
    meta = parse_json_text(files, ".context/capsule.json") or {}
    if meta.get("version") != VERSION:
        raise CapsuleModelError(
            f"legacy provenance normalization requires Project Manager {VERSION}; "
            f"installed version is {meta.get('version')!r}"
        )

    sync = manifest.get("sync_policy")
    coherence_required = isinstance(sync, dict) and sync.get("manager_state_coherence_required") is True
    if coherence_required:
        integrity_errors = _manager_state_integrity_errors(files, manifest)
        if integrity_errors:
            raise CapsuleModelError(
                "legacy provenance normalization refuses incoherent manager state: "
                + "; ".join(integrity_errors)
            )

    manager = manifest.get("manager") if isinstance(manifest.get("manager"), dict) else {}
    memory = manifest.get("memory") if isinstance(manifest.get("memory"), dict) else {}
    paths = [
        manager.get("beliefs"),
        memory.get("semantic"),
        memory.get("procedural"),
    ]

    provisional = dict(files)
    changed_paths: set[str] = set()
    for path in paths:
        if not isinstance(path, str) or path not in provisional:
            continue
        normalized, changed = _normalize_legacy_provenance_text(provisional[path])
        if changed:
            provisional[path] = normalized
            changed_paths.add(path)

    coupled = set(manager_state_coupled_paths(manifest))
    if changed_paths & coupled:
        marker_path = manager.get("state_integrity")
        if not isinstance(marker_path, str) or not marker_path:
            raise CapsuleModelError(
                "legacy provenance normalization changed coupled manager state without a state-integrity marker"
            )
        previous = parse_json_text(files, marker_path)
        provisional[marker_path] = canonical_json(
            build_manager_state_integrity(provisional, manifest, existing=previous)
        )
        changed_paths.add(marker_path)

    return {
        path: provisional[path]
        for path in changed_paths
        if files.get(path) != provisional[path]
    }


def _core_binding_errors(
    files: dict[str, str],
    core_reference: dict[str, str] | None,
    *,
    require_core_binding: bool,
) -> list[str]:
    if core_reference is None:
        return ["Project Manager provenance binding reference is required"] if require_core_binding else []
    errors: list[str] = []
    for path in CORE_GOVERNING_PATHS:
        expected = core_reference.get(path)
        if expected is None:
            errors.append(f"Project Manager provenance reference missing governing file: {path}")
            continue
        actual = files.get(path)
        if actual is None:
            continue
        if actual != expected:
            errors.append(
                f"Project Manager provenance mismatch: {path} does not match the declared Project Manager commit"
            )
    return errors



def manager_state_coupled_paths(manifest: dict) -> list[str]:
    manager = manifest.get("manager") if isinstance(manifest.get("manager"), dict) else {}
    current = manifest.get("current") if isinstance(manifest.get("current"), dict) else {}
    paths = [
        manager.get("beliefs"),
        manager.get("goals"),
        manager.get("intentions"),
        manager.get("plans"),
        current.get("state"),
        current.get("blockers"),
        current.get("next"),
        manifest.get("latest_handoff"),
    ]
    result: list[str] = []
    for raw in paths:
        if isinstance(raw, str) and raw and raw not in result:
            result.append(raw)
    return result


def _git_blob_sha1(text: str) -> str:
    payload = text.encode("utf-8")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def build_manager_state_integrity(
    files: dict[str, str],
    manifest: dict,
    *,
    existing: dict | None = None,
) -> dict:
    coupled = manager_state_coupled_paths(manifest)
    if not coupled:
        raise CapsuleModelError("manager state integrity has no coupled paths")
    digests: dict[str, str] = {}
    for path in coupled:
        text = files.get(path)
        if text is None:
            raise CapsuleModelError(f"manager state integrity cannot seal missing path: {path}")
        digests[path] = "git-blob-sha1:" + _git_blob_sha1(text)

    previous_generation = 0
    previous_digests = None
    if isinstance(existing, dict):
        raw_generation = existing.get("generation")
        if isinstance(raw_generation, int) and raw_generation >= 1:
            previous_generation = raw_generation
        if isinstance(existing.get("digests"), dict):
            previous_digests = existing.get("digests")

    generation = previous_generation if previous_generation and previous_digests == digests else previous_generation + 1
    if generation < 1:
        generation = 1

    return {
        "schema": "context-capsule-manager-state-integrity",
        "schema_version": MANAGER_STATE_INTEGRITY_SCHEMA_VERSION,
        "generation": generation,
        "algorithm": "git-blob-sha1",
        "coupled_paths": coupled,
        "digests": digests,
    }


def _manager_state_integrity_errors(files: dict[str, str], manifest: dict) -> list[str]:
    sync = manifest.get("sync_policy")
    coherence_required = isinstance(sync, dict) and sync.get("manager_state_coherence_required") is True
    manager = manifest.get("manager") if isinstance(manifest.get("manager"), dict) else {}
    marker_path = manager.get("state_integrity")

    if not coherence_required:
        return []
    if not isinstance(marker_path, str) or not marker_path:
        return ["manager state coherence is required but manager.state_integrity is missing from manifest"]

    try:
        marker = parse_json_text(files, marker_path)
    except CapsuleModelError as exc:
        return [f"manager state integrity: {exc}"]
    if marker is None:
        return [
            f"manager state integrity marker is missing: {marker_path}; "
            "run explicit v2 repair/bootstrap before READY"
        ]
    errors: list[str] = []
    if marker.get("schema") != "context-capsule-manager-state-integrity":
        errors.append("manager state integrity: invalid schema")
    if marker.get("schema_version") != MANAGER_STATE_INTEGRITY_SCHEMA_VERSION:
        errors.append(
            f"manager state integrity: schema_version must be {MANAGER_STATE_INTEGRITY_SCHEMA_VERSION}"
        )
    generation = marker.get("generation")
    if not isinstance(generation, int) or generation < 1:
        errors.append("manager state integrity: generation must be a positive integer")
    if marker.get("algorithm") != "git-blob-sha1":
        errors.append("manager state integrity: algorithm must be git-blob-sha1")

    expected_paths = manager_state_coupled_paths(manifest)
    if marker.get("coupled_paths") != expected_paths:
        errors.append("manager state integrity: coupled_paths do not match the current manifest")
    digests = marker.get("digests")
    if not isinstance(digests, dict):
        errors.append("manager state integrity: digests must be an object")
        return errors

    for path in expected_paths:
        text = files.get(path)
        if text is None:
            errors.append(f"manager state integrity: missing coupled path: {path}")
            continue
        expected = "git-blob-sha1:" + _git_blob_sha1(text)
        actual = digests.get(path)
        if actual != expected:
            errors.append(
                f"manager state integrity mismatch: {path} does not belong to sealed generation {generation}"
            )
    extra = sorted(set(digests) - set(expected_paths))
    if extra:
        errors.append(
            "manager state integrity: digest set contains non-coupled path(s): " + ", ".join(extra)
        )
    return errors


def readiness_snapshot(
    files: dict[str, str],
    *,
    core_reference: dict[str, str] | None = None,
    require_core_binding: bool = False,
) -> tuple[bool, list[str]]:
    validation = validate_snapshot(
        files,
        core_reference=core_reference,
        require_core_binding=require_core_binding,
    )
    if validation:
        return False, [f"VALIDATION: {item}" for item in validation]

    manifest = parse_json_text(files, ".context/manifest.json") or {}
    missing: list[str] = []
    missing.extend(_manager_state_integrity_errors(files, manifest))

    required = {
        "project.identity": manifest["project"]["identity"],
        "project.goals": manifest["project"]["goals"],
        "project.architecture": manifest["project"]["architecture"],
        "project.constraints": manifest["project"]["constraints"],
        "manager.mandate": manifest["manager"]["mandate"],
        "manager.goals": manifest["manager"]["goals"],
        "manager.intentions": manifest["manager"]["intentions"],
        "manager.plans": manifest["manager"]["plans"],
        "current.state": manifest["current"]["state"],
        "current.next": manifest["current"]["next"],
    }
    for label, path in required.items():
        if not _is_substantive(files.get(path)):
            missing.append(f"{label} is empty or still a template")

    beliefs_path = manifest["manager"]["beliefs"]
    beliefs_text = files.get(beliefs_path)
    if not _is_substantive(beliefs_text):
        missing.append("manager.beliefs is empty or still a template")
    else:
        missing.extend(_entry_provenance_errors(beliefs_text, "manager.beliefs"))

    for memory_key in ("semantic", "procedural"):
        memory_path = manifest["memory"][memory_key]
        missing.extend(
            _entry_provenance_errors(files.get(memory_path), f"memory.{memory_key}")
        )

    rule_ready = any(_is_substantive(files.get(path)) for path in manifest.get("rules", []))
    decision_ready = any(_is_substantive(files.get(path)) for path in manifest.get("decisions", []))
    if not (rule_ready or decision_ready):
        missing.append("no substantive active rule or durable decision is available")

    return not missing, missing


def build_recovery_pack(
    files: dict[str, str],
    *,
    max_chars: int = 65536,
    core_reference: dict[str, str] | None = None,
    require_core_binding: bool = False,
    authoritative: bool = True,
) -> str:
    ready, reasons = readiness_snapshot(
        files,
        core_reference=core_reference,
        require_core_binding=require_core_binding,
    )
    if not ready:
        raise CapsuleModelError("capsule is not READY: " + "; ".join(reasons))
    manifest = parse_json_text(files, ".context/manifest.json") or {}
    identity = parse_json_text(files, manifest["manager"]["identity"]) or {}
    manager_id = identity.get("manager_id", "project-manager")

    mandatory: list[tuple[str, str]] = [
        ("MANAGER CONTRACT", manifest["manager"]["contract"]),
        ("MANAGER PROTOCOL", manifest["manager"]["protocol"]),
        ("MANAGER IDENTITY", manifest["manager"]["identity"]),
        ("MANAGER MANDATE", manifest["manager"]["mandate"]),
        ("PROJECT IDENTITY", manifest["project"]["identity"]),
        ("PROJECT GOALS", manifest["project"]["goals"]),
        ("PROJECT ARCHITECTURE", manifest["project"]["architecture"]),
        ("PROJECT CONSTRAINTS", manifest["project"]["constraints"]),
        ("MANAGER BELIEFS", manifest["manager"]["beliefs"]),
        ("MANAGER GOALS", manifest["manager"]["goals"]),
        ("MANAGER INTENTIONS", manifest["manager"]["intentions"]),
        ("MANAGER PLANS", manifest["manager"]["plans"]),
    ]
    for path in manifest.get("rules", []):
        mandatory.append(("ACTIVE RULE", path))

    optional: list[tuple[str, str]] = [
        ("WORKING VIEW — CURRENT STATE (NON-AUTHORITATIVE)", manifest["current"]["state"]),
        ("WORKING VIEW — CURRENT BLOCKERS (NON-AUTHORITATIVE)", manifest["current"]["blockers"]),
        ("WORKING VIEW — NEXT ACTIONS (NON-AUTHORITATIVE)", manifest["current"]["next"]),
        ("SEMANTIC MEMORY", manifest["memory"]["semantic"]),
        ("PROCEDURAL MEMORY", manifest["memory"]["procedural"]),
        ("EMERGENCY HANDOFF (NON-AUTHORITATIVE)", manifest["latest_handoff"]),
    ]
    for path in manifest["memory"].get("episodes", []):
        optional.append(("EPISODIC MEMORY", path))
    for path in manifest.get("decisions", []):
        optional.append(("DURABLE DECISION", path))

    title = (
        "# CONTEXT CAPSULE PROJECT MANAGER REINSTANTIATION PACK"
        if authoritative
        else "# CONTEXT CAPSULE NON-AUTHORITATIVE MAINTENANCE/AUDIT PACK"
    )
    mode_lines = (
        [
            "You are a new runtime instance of the existing Project Manager, not a new manager.",
            "Preserve manager identity, open intentions, and durable memory unless newer authoritative evidence invalidates them.",
        ]
        if authoritative
        else [
            "NON-AUTHORITATIVE MODE: this checkout is evidence for maintenance/audit only.",
            "Do not instantiate, resume, or continue the Project Manager from this pack.",
        ]
    )
    chunks = [
        title,
        "",
        f"Repository: {manifest.get('repository')}",
        f"Manager state authority branch: {manifest.get('authority', {}).get('manager_state_branch')}",
        f"Product authority branch: {manifest.get('authority', {}).get('product_branch')}",
        f"Manager ID: {manager_id}",
        *(
            [f"Manager state sealed generation: {(parse_json_text(files, manifest['manager']['state_integrity']) or {}).get('generation')}"]
            if isinstance(manifest.get("sync_policy"), dict)
            and manifest["sync_policy"].get("manager_state_coherence_required") is True
            else ["Manager state sealed generation: legacy-unsealed"]
        ),
        "",
        *mode_lines,
        "Runtime conversation/checkpoint state is not manager identity and must not override durable capsule state.",
        "current/* and handoff are non-authoritative working views. If they conflict with manager BDI state or newer live evidence, treat the view as stale, reconcile against authoritative evidence, and repair the view.",
        "",
    ]
    used = sum(len(x) + 1 for x in chunks)
    for label, path in mandatory:
        text = files.get(path)
        if text is None:
            continue
        chunk = f"## {label}: {path}\n\n{text.strip()}\n"
        if used + len(chunk) > max_chars:
            raise CapsuleModelError(
                f"recovery budget too small for mandatory manager state: {path}"
            )
        chunks.append(chunk)
        used += len(chunk)

    omitted: list[str] = []
    for label, path in optional:
        text = files.get(path)
        if text is None:
            continue
        chunk = f"## {label}: {path}\n\n{text.strip()}\n"
        if used + len(chunk) > max_chars:
            omitted.append(path)
            continue
        chunks.append(chunk)
        used += len(chunk)
    if omitted:
        chunks.append("## OMITTED DEEPER MEMORY\n\n" + "\n".join(f"- {p}" for p in omitted))
    return "\n".join(chunks).rstrip() + "\n"


def _seed_v2_structure(
    provisional: dict[str, str], template_root: Path, repository: str, *, overwrite_system: bool
) -> None:
    for rel in SYSTEM_TEXT_PATHS:
        if overwrite_system or rel not in provisional:
            provisional[rel] = _load_template(template_root, rel)
    for rel in PROJECT_SEED_PATHS:
        if rel not in provisional:
            provisional[rel] = _load_template(template_root, rel)
    existing_identity = None
    if MANAGER_IDENTITY_PATH in provisional:
        try:
            existing_identity = json.loads(provisional[MANAGER_IDENTITY_PATH])
        except Exception:
            existing_identity = None
    if MANAGER_IDENTITY_PATH not in provisional:
        provisional[MANAGER_IDENTITY_PATH] = canonical_json(build_manager_identity(repository))
    elif isinstance(existing_identity, dict):
        provisional[MANAGER_IDENTITY_PATH] = canonical_json(
            build_manager_identity(repository, existing=existing_identity)
        )


def clean_install_changes(
    files: dict[str, str],
    template_root: Path,
    repository: str,
    branch: str,
    core_commit: str,
    *,
    context_capsule_commit: str | None = None,
    semantic_overrides: dict[str, str] | None = None,
    discovery_branch: str | None = None,
    product_branch: str | None = None,
) -> dict[str, str]:
    if any(path == ".context" or path.startswith(".context/") for path in files):
        raise CapsuleModelError("clean install refused: existing .context content found")
    validate_core_commit(core_commit)
    provisional = dict(files)
    provisional.update(bootstrap_changes(files, template_root))
    _seed_v2_structure(provisional, template_root, repository, overwrite_system=True)

    if semantic_overrides:
        for raw_path, content in semantic_overrides.items():
            path = normalize_repo_path(raw_path)
            if not path.startswith(".context/"):
                raise CapsuleModelError(f"semantic override must be inside .context/: {path}")
            provisional[path] = content

    meta = build_capsule_metadata(repository, core_commit, context_capsule_commit=context_capsule_commit)
    provisional[".context/capsule.json"] = canonical_json(meta)
    redirect_topology = None
    if discovery_branch and discovery_branch != branch:
        redirect_topology = (branch, discovery_branch)
    manifest = build_manifest(
        provisional,
        repository,
        branch,
        redirect_topology=redirect_topology,
        product_branch=product_branch,
    )
    provisional[".context/manifest.json"] = canonical_json(manifest)
    previous_integrity = parse_json_text(files, MANAGER_STATE_INTEGRITY_PATH)
    provisional[MANAGER_STATE_INTEGRITY_PATH] = canonical_json(
        build_manager_state_integrity(provisional, manifest, existing=previous_integrity)
    )

    errors = validate_snapshot(provisional)
    if errors:
        raise CapsuleModelError("planned clean install is invalid: " + "; ".join(errors))
    return {path: provisional[path] for path in provisional if files.get(path) != provisional[path]}


def upgrade_changes(
    files: dict[str, str],
    template_root: Path,
    *,
    repository: str,
    branch: str,
    core_commit: str,
    context_capsule_commit: str | None = None,
    product_branch: str | None = None,
) -> dict[str, str]:
    existing_manifest = parse_json_text(files, ".context/manifest.json") or {}
    existing_meta = parse_json_text(files, ".context/capsule.json") or {}
    old_version = existing_meta.get("version")
    if not isinstance(old_version, str) or not old_version.startswith("1.3."):
        raise CapsuleModelError("v2 upgrade currently accepts only installed v1.3.x capsules")
    authoritative_branch = existing_manifest.get("authoritative_branch") or branch
    if authoritative_branch != branch:
        raise CapsuleModelError(
            f"upgrade must run against authoritative branch {authoritative_branch!r}, not {branch!r}"
        )
    validate_core_commit(core_commit)
    if context_capsule_commit is None:
        legacy_core_commit = existing_meta.get("core_commit")
        if isinstance(legacy_core_commit, str):
            context_capsule_commit = legacy_core_commit
    provisional = dict(files)
    provisional.update(bootstrap_changes(files, template_root))
    _seed_v2_structure(provisional, template_root, repository, overwrite_system=True)
    provisional[".context/capsule.json"] = canonical_json(
        build_capsule_metadata(
            repository,
            core_commit,
            context_capsule_commit=context_capsule_commit,
            existing=existing_meta,
        )
    )
    provisional[".context/manifest.json"] = canonical_json(
        build_manifest(
            provisional,
            repository,
            branch,
            existing=existing_manifest,
            product_branch=product_branch,
        )
    )
    upgraded_manifest = parse_json_text(provisional, ".context/manifest.json") or {}
    previous_integrity = parse_json_text(files, MANAGER_STATE_INTEGRITY_PATH)
    provisional[MANAGER_STATE_INTEGRITY_PATH] = canonical_json(
        build_manager_state_integrity(provisional, upgraded_manifest, existing=previous_integrity)
    )
    errors = validate_snapshot(provisional)
    if errors:
        raise CapsuleModelError("planned v2 upgrade is invalid: " + "; ".join(errors))
    return {path: provisional[path] for path in provisional if files.get(path) != provisional[path]}


def repair_changes(
    files: dict[str, str],
    template_root: Path,
    *,
    repository: str,
    branch: str,
    core_commit: str,
    context_capsule_commit: str | None = None,
) -> dict[str, str]:
    existing_manifest = parse_json_text(files, ".context/manifest.json") or {}
    existing_meta = parse_json_text(files, ".context/capsule.json") or {}
    if existing_meta.get("version") != VERSION:
        raise CapsuleModelError(
            f"repair never performs a major-version upgrade; installed version is {existing_meta.get('version')!r}, use upgrade"
        )
    authoritative_branch = existing_manifest.get("authoritative_branch")
    if isinstance(authoritative_branch, str) and authoritative_branch and authoritative_branch != branch:
        raise CapsuleModelError(
            f"repair must run against authoritative branch {authoritative_branch!r}, not {branch!r}"
        )
    if (
        isinstance(existing_manifest.get("sync_policy"), dict)
        and existing_manifest["sync_policy"].get("manager_state_coherence_required") is True
    ):
        integrity_errors = _manager_state_integrity_errors(files, existing_manifest)
        if integrity_errors:
            raise CapsuleModelError(
                "repair refuses to seal an incoherent manager state; reconcile the manager state first: "
                + "; ".join(integrity_errors)
            )

    provisional = dict(files)
    provisional.update(bootstrap_changes(files, template_root))
    _seed_v2_structure(provisional, template_root, repository, overwrite_system=True)
    provisional[".context/capsule.json"] = canonical_json(
        build_capsule_metadata(
            repository,
            core_commit,
            context_capsule_commit=context_capsule_commit,
            existing=existing_meta,
        )
    )
    provisional[".context/manifest.json"] = canonical_json(
        build_manifest(provisional, repository, branch, existing=existing_manifest)
    )
    repaired_manifest = parse_json_text(provisional, ".context/manifest.json") or {}
    previous_integrity = parse_json_text(files, MANAGER_STATE_INTEGRITY_PATH)
    provisional[MANAGER_STATE_INTEGRITY_PATH] = canonical_json(
        build_manager_state_integrity(provisional, repaired_manifest, existing=previous_integrity)
    )
    errors = validate_snapshot(provisional)
    if errors:
        raise CapsuleModelError("planned repair is invalid: " + "; ".join(errors))
    return {path: provisional[path] for path in provisional if files.get(path) != provisional[path]}
