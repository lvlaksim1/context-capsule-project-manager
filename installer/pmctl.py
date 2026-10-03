#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from installer.model import (
    CapsuleModelError,
    VERSION,
    build_recovery_pack,
    clean_install_changes,
    discovery_redirect_changes,
    readiness_snapshot,
    repair_changes,
    upgrade_changes,
    validate_snapshot,
)
from installer.safety import CapsuleSafetyError, confined_local_path, validate_core_commit
from installer.runtime_guard import (
    LifecycleGuardError,
    load_core_reference,
    manager_checkout_status,
    snapshot_core_commit,
)
CORE_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = CORE_ROOT / "templates"


def target_root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"target does not exist or is not a directory: {path}")
    return path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"Context Capsule expected UTF-8 text at {path}") from exc


def load_snapshot(target: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in ("AI_CONTEXT.md", "AGENTS.md"):
        path = target / rel
        if path.exists():
            if path.is_symlink():
                confined_local_path(target, rel)
            if path.is_file():
                files[rel] = _read_text(path)

    context = target / ".context"
    if context.exists():
        if context.is_symlink():
            confined_local_path(target, ".context")
        if not context.is_dir():
            raise SystemExit(".context exists but is not a directory")
        for path in sorted(context.rglob("*")):
            if path.is_symlink():
                rel = path.relative_to(target).as_posix()
                confined_local_path(target, rel)
            if path.is_file():
                rel = path.relative_to(target).as_posix()
                files[rel] = _read_text(path)

    manifest_text = files.get(".context/manifest.json")
    if manifest_text:
        try:
            manifest = json.loads(manifest_text)
        except Exception:
            manifest = None
        if isinstance(manifest, dict):
            candidates: list[str] = []
            for key in ("entrypoint", "protocol", "latest_handoff", "current_state", "capsule_metadata"):
                value = manifest.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            for section in ("project", "current", "manager"):
                value = manifest.get(section)
                if isinstance(value, dict):
                    candidates.extend(v for v in value.values() if isinstance(v, str))
            memory = manifest.get("memory")
            if isinstance(memory, dict):
                for key in ("index", "semantic", "procedural"):
                    value = memory.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
                episodes = memory.get("episodes")
                if isinstance(episodes, list):
                    candidates.extend(v for v in episodes if isinstance(v, str))
            for section in ("rules", "decisions", "dialogues", "history"):
                value = manifest.get(section)
                if isinstance(value, list):
                    candidates.extend(v for v in value if isinstance(v, str))
            for rel in candidates:
                if rel in files:
                    continue
                try:
                    path = confined_local_path(target, rel)
                except CapsuleSafetyError as exc:
                    raise SystemExit(str(exc)) from exc
                if path.exists() and path.is_file():
                    files[rel] = _read_text(path)
    return files


def apply_local_changes(target: Path, changes: dict[str, str | None]) -> None:
    for rel, content in changes.items():
        path = confined_local_path(target, rel)
        if path.exists() and path.is_symlink():
            confined_local_path(target, rel)
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".context-capsule.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)


def infer_core_commit(explicit: str | None) -> str:
    if explicit:
        return validate_core_commit(explicit)
    try:
        sha = subprocess.run(
            ["git", "-C", str(CORE_ROOT), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        return validate_core_commit(sha)
    except Exception as exc:
        raise SystemExit("--core-commit is required when Core is not running from a Git checkout") from exc


def infer_bound_core_commit(explicit: str | None) -> str:
    core_commit = infer_core_commit(explicit)
    try:
        load_core_reference(CORE_ROOT, core_commit)
    except LifecycleGuardError as exc:
        raise SystemExit(str(exc)) from exc
    return core_commit


def actual_branch(target: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(target), "branch", "--show-current"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip() or None
    except Exception:
        return None


def ensure_branch(target: Path, requested: str) -> None:
    actual = actual_branch(target)
    if actual and actual != requested:
        raise SystemExit(f"target checkout branch mismatch: requested {requested!r}, actual {actual!r}")


def _apply_planned(target: Path, label: str, planner) -> int:
    try:
        changes = planner()
    except (CapsuleModelError, CapsuleSafetyError) as exc:
        print(f"Context Capsule {label}: FAIL\n  - {exc}")
        return 2
    apply_local_changes(target, changes)
    print(f"Context Capsule {label} applied locally ({len(changes)} changed files).")
    return cmd_validate(argparse.Namespace(target=str(target)))


def cmd_install(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    ensure_branch(target, args.branch)
    files = load_snapshot(target)
    core_commit = infer_bound_core_commit(args.core_commit)
    return _apply_planned(
        target,
        "install",
        lambda: clean_install_changes(
            files,
            TEMPLATES,
            args.repository,
            args.branch,
            core_commit,
            discovery_branch=args.discovery_branch,
            product_branch=args.product_branch,
        ),
    )


def cmd_upgrade(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    ensure_branch(target, args.branch)
    files = load_snapshot(target)
    core_commit = infer_bound_core_commit(args.core_commit)
    return _apply_planned(
        target,
        "upgrade",
        lambda: upgrade_changes(
            files,
            TEMPLATES,
            repository=args.repository,
            branch=args.branch,
            core_commit=core_commit,
            product_branch=args.product_branch,
        ),
    )


def cmd_repair(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    ensure_branch(target, args.branch)
    files = load_snapshot(target)
    core_commit = infer_bound_core_commit(args.core_commit)
    return _apply_planned(
        target,
        "repair",
        lambda: repair_changes(
            files,
            TEMPLATES,
            repository=args.repository,
            branch=args.branch,
            core_commit=core_commit,
        ),
    )


def cmd_discovery(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    ensure_branch(target, args.discovery_branch)
    files = load_snapshot(target)
    try:
        changes = discovery_redirect_changes(
            files,
            TEMPLATES,
            authoritative_branch=args.authoritative_branch,
            discovery_branch=args.discovery_branch,
        )
    except (CapsuleModelError, CapsuleSafetyError) as exc:
        print(f"Context Capsule discovery: FAIL\n  - {exc}")
        return 2
    apply_local_changes(target, changes)
    print(f"Context Capsule discovery redirect prepared: {args.discovery_branch} -> {args.authoritative_branch}")
    return 0


def _bound_core_reference(files: dict[str, str]) -> dict[str, str]:
    return load_core_reference(CORE_ROOT, snapshot_core_commit(files))


def cmd_validate(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    try:
        files = load_snapshot(target)
        core_reference = _bound_core_reference(files)
        errors = validate_snapshot(
            files,
            core_reference=core_reference,
            require_core_binding=True,
        )
    except (CapsuleModelError, CapsuleSafetyError, LifecycleGuardError, SystemExit) as exc:
        print(f"Context Capsule validation: FAIL\n  - {exc}")
        return 1
    if errors:
        print("Context Capsule validation: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Context Capsule validation: VALID (CORE PROVENANCE BOUND)")
    return 0


def cmd_ready(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    try:
        files = load_snapshot(target)
        authoritative, branch, head = manager_checkout_status(
            target,
            files,
            expected_ref=args.expected_manager_ref,
            non_authoritative=args.non_authoritative,
        )
        core_reference = _bound_core_reference(files)
        ready, reasons = readiness_snapshot(
            files,
            core_reference=core_reference,
            require_core_binding=True,
        )
    except (CapsuleModelError, CapsuleSafetyError, LifecycleGuardError, SystemExit) as exc:
        print(f"Context Capsule readiness: NOT READY\n  - {exc}")
        return 1
    if not ready:
        print("Context Capsule readiness: NOT READY")
        for reason in reasons:
            print(f"  - {reason}")
        return 1
    if authoritative:
        print(
            "Context Capsule readiness: READY (PROJECT MANAGER REINSTANTIABLE; "
            f"authoritative checkout {branch}@{head})"
        )
    else:
        print(
            "Context Capsule readiness: READY FOR NON-AUTHORITATIVE MAINTENANCE/AUDIT "
            f"(NOT PROJECT MANAGER REINSTATIATION; checkout {branch or 'detached/unknown'}@{head or 'unknown'})"
        )
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    target = target_root(args.target)
    try:
        files = load_snapshot(target)
        authoritative, _branch, _head = manager_checkout_status(
            target,
            files,
            expected_ref=args.expected_manager_ref,
            non_authoritative=args.non_authoritative,
        )
        core_reference = _bound_core_reference(files)
        pack = build_recovery_pack(
            files,
            max_chars=args.max_chars,
            core_reference=core_reference,
            require_core_binding=True,
            authoritative=authoritative,
        )
    except (CapsuleModelError, CapsuleSafetyError, LifecycleGuardError, SystemExit) as exc:
        print(f"Context Capsule recovery: FAIL\n  - {exc}")
        return 1
    sys.stdout.write(pack)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmctl", description="Context Capsule Project Manager lifecycle helper")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="clean-install a v2 Project Manager capsule")
    install.add_argument("--target", required=True)
    install.add_argument("--repository", required=True)
    install.add_argument("--branch", default="main")
    install.add_argument("--core-commit")
    install.add_argument("--discovery-branch")
    install.add_argument("--product-branch", help="product baseline branch; defaults to manager-state authority (or discovery branch in redirect mode)")
    install.set_defaults(func=cmd_install)

    upgrade = sub.add_parser("upgrade", help="explicitly upgrade an installed v1.3.x capsule to v2")
    upgrade.add_argument("--target", required=True)
    upgrade.add_argument("--repository", required=True)
    upgrade.add_argument("--branch", required=True)
    upgrade.add_argument("--core-commit")
    upgrade.add_argument("--product-branch", help="product baseline branch; inferred from existing topology when omitted")
    upgrade.set_defaults(func=cmd_upgrade)

    discovery = sub.add_parser("discovery", help="prepare a discovery-only branch redirect")
    discovery.add_argument("--target", required=True)
    discovery.add_argument("--authoritative-branch", required=True)
    discovery.add_argument("--discovery-branch", default="main")
    discovery.set_defaults(func=cmd_discovery)

    repair = sub.add_parser("repair", help="repair the installed v2 capsule without major-version upgrade")
    repair.add_argument("--target", required=True)
    repair.add_argument("--repository", required=True)
    repair.add_argument("--branch", required=True)
    repair.add_argument("--core-commit")
    repair.set_defaults(func=cmd_repair)

    validate = sub.add_parser("validate", help="check structural validity")
    validate.add_argument("--target", required=True)
    validate.set_defaults(func=cmd_validate)

    ready = sub.add_parser("ready", help="check Project Manager reinstantiation readiness")
    ready.add_argument("--target", required=True)
    ready.add_argument("--expected-manager-ref", help="optional commit/ref pin for deterministic authority verification")
    ready.add_argument(
        "--non-authoritative",
        action="store_true",
        help="allow maintenance/audit inspection from a non-authoritative checkout; never declares PM reinstantiable",
    )
    ready.set_defaults(func=cmd_ready)

    recover = sub.add_parser("recover", help="emit a deterministic Project Manager reinstantiation pack")
    recover.add_argument("--target", required=True)
    recover.add_argument("--max-chars", type=int, default=65536)
    recover.add_argument("--expected-manager-ref", help="optional commit/ref pin for deterministic authority verification")
    recover.add_argument(
        "--non-authoritative",
        action="store_true",
        help="emit an explicitly non-authoritative maintenance/audit pack from a divergent checkout",
    )
    recover.set_defaults(func=cmd_recover)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
