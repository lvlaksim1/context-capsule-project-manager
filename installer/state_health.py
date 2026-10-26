"""GitHub-backed product freshness gate for durable Project Manager capsules.

This is deliberately separate from structural capsule integrity: Git object
digests establish coherence, not correspondence with the live product.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASELINE_PATH = ".context/current/product-baseline.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class FreshnessError(ValueError):
    """Missing, invalid, or unavailable authoritative evidence."""


@dataclass(frozen=True)
class ProductEvidence:
    repository: str
    branch: str
    head_sha: str
    release_tag: str | None
    release_sha: str | None

    @classmethod
    def parse(cls, value: object) -> "ProductEvidence":
        if not isinstance(value, dict):
            raise FreshnessError("product evidence must be an object")
        fields = ("repository", "branch", "head_sha", "release_tag", "release_sha")
        if any(field not in value for field in fields):
            raise FreshnessError("product evidence is missing mandatory fields")
        data = {field: value[field] for field in fields}
        if not isinstance(data["repository"], str) or not REPO.fullmatch(data["repository"]):
            raise FreshnessError("invalid repository in product evidence")
        if not isinstance(data["branch"], str) or not data["branch"] or len(data["branch"]) > 255:
            raise FreshnessError("invalid product branch")
        if not isinstance(data["head_sha"], str) or not SHA.fullmatch(data["head_sha"]):
            raise FreshnessError("invalid product head SHA")
        for field in ("release_tag", "release_sha"):
            if data[field] is not None and not isinstance(data[field], str):
                raise FreshnessError("invalid " + field)
        if (data["release_tag"] is None) != (data["release_sha"] is None):
            raise FreshnessError("release tag and SHA must both be set, or both null")
        if data["release_tag"] is not None:
            if not data["release_tag"] or len(data["release_tag"]) > 255:
                raise FreshnessError("invalid release tag")
            if not SHA.fullmatch(data["release_sha"]):
                raise FreshnessError("invalid release commit SHA")
        return cls(**data)


def _manifest(target: Path) -> tuple[str, str]:
    path = target / ".context/manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FreshnessError("cannot read valid capsule manifest") from exc
    if not isinstance(manifest, dict):
        raise FreshnessError("capsule manifest must be an object")
    repo = manifest.get("repository")
    authority = manifest.get("authority")
    branch = authority.get("product_branch") if isinstance(authority, dict) else None
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise FreshnessError("manifest has no valid repository")
    if not isinstance(branch, str) or not branch or len(branch) > 255:
        raise FreshnessError("manifest has no valid authority.product_branch")
    return repo, branch


def _download_json(url: str, token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "context-capsule-project-manager-freshness",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers)
    with urlopen(request, timeout=12) as response:
        parsed = json.load(response)
    if not isinstance(parsed, dict):
        raise FreshnessError("GitHub API returned a non-object")
    return parsed


def observe_product(
    repository: str,
    branch: str,
    *,
    fetch=None,
    token: str | None = None,
) -> ProductEvidence:
    """Read live GitHub branch head and latest published release.

    An absent latest release is distinct from an API failure; 404 is accepted
    only at the releases/latest endpoint.
    """
    if not REPO.fullmatch(repository) or not branch:
        raise FreshnessError("invalid product GitHub coordinates")
    read = fetch or _download_json
    prefix = "https://api.github.com/repos/" + repository
    try:
        branch_data = read(prefix + "/branches/" + quote(branch, safe=""), token)
        head = branch_data["commit"]["sha"]
        try:
            release = read(prefix + "/releases/latest", token)
        except HTTPError as exc:
            if exc.code != 404:
                raise
            release = None
        tag = release.get("tag_name") if isinstance(release, dict) else None
        release_sha = None
        if tag is not None:
            if not isinstance(tag, str) or not tag:
                raise FreshnessError("latest GitHub release has no valid tag")
            release_sha = read(prefix + "/commits/" + quote(tag, safe=""), token)["sha"]
        return ProductEvidence.parse({
            "repository": repository,
            "branch": branch,
            "head_sha": head,
            "release_tag": tag,
            "release_sha": release_sha,
        })
    except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, FreshnessError):
            raise
        raise FreshnessError("live GitHub product evidence unavailable or malformed: " + str(exc)) from exc


def load_baseline(target: Path) -> ProductEvidence | None:
    path = target / BASELINE_PATH
    if not path.exists():
        return None
    if path.is_symlink():
        raise FreshnessError("baseline may not be a symbolic link")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != "pm-product-baseline-v1":
            raise FreshnessError("invalid product baseline schema")
        return ProductEvidence.parse(data.get("product"))
    except (OSError, ValueError) as exc:
        raise FreshnessError("invalid product baseline: " + str(exc)) from exc


def compare_product(
    repository: str, branch: str, baseline: ProductEvidence | None, live: ProductEvidence
) -> tuple[str, list[str]]:
    if live.repository != repository or live.branch != branch:
        return "UNKNOWN", ["live evidence does not match authoritative product coordinates"]
    if baseline is None:
        return "UNKNOWN", ["no reconciled product baseline recorded"]
    if baseline.repository != repository or baseline.branch != branch:
        return "UNKNOWN", ["baseline belongs to different product authority"]
    reasons = []
    if baseline.release_tag != live.release_tag or baseline.release_sha != live.release_sha:
        reasons.append("published release differs from the reconciled baseline")
    if reasons:
        return "STALE", reasons
    if baseline.head_sha != live.head_sha:
        return "DRIFT", [
            "product branch head changed; may include code OR context-only commits",
            "reconcile the diff before recording a new baseline",
        ]
    return "FRESH", []


def inspect(target: Path, *, fetch=None) -> tuple[str, list[str], ProductEvidence | None]:
    repository, branch = _manifest(target)
    baseline = load_baseline(target)
    try:
        live = observe_product(repository, branch, fetch=fetch, token=os.environ.get("GITHUB_TOKEN"))
    except FreshnessError as exc:
        return "UNKNOWN", [str(exc)], None
    status, reasons = compare_product(repository, branch, baseline, live)
    return status, reasons, live


def format_result(status: str, reasons: list[str], live: ProductEvidence | None) -> str:
    lines = ["Product freshness: " + status]
    if live:
        lines.append("  live: " + live.repository + " " + live.branch + "@" + live.head_sha)
        lines.append("  latest release: " + (live.release_tag or "(none)"))
    lines.extend("  - " + reason for reason in reasons)
    return "\n".join(lines)


def write_baseline(target: Path, live: ProductEvidence) -> Path:
    from installer.safety import confined_local_path

    path = confined_local_path(target, BASELINE_PATH)
    if path.is_symlink():
        raise FreshnessError("baseline may not be a symbolic link")
    record = {
        "schema": "pm-product-baseline-v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "reconciliation": "operator-confirmed",
        "product": asdict(live),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Project Manager product freshness against live GitHub")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check current baseline against live product")
    check.add_argument("--target", required=True)
    capture = sub.add_parser("capture", help="record reconciled live product baseline")
    capture.add_argument("--target", required=True)
    capture.add_argument("--confirm-reconciled", action="store_true", help="affirm product changes and open obligations were reviewed")
    args = parser.parse_args(argv)
    target = Path(args.target).expanduser().resolve()
    try:
        if args.command == "capture":
            if not args.confirm_reconciled:
                raise FreshnessError("capture requires --confirm-reconciled after reviewing product changes and outstanding commitments")
            repository, branch = _manifest(target)
            live = observe_product(repository, branch, token=os.environ.get("GITHUB_TOKEN"))
            output = write_baseline(target, live)
            print("Product baseline captured: " + str(output))
            print("  capture is not a substitute for reviewing and updating manager BDI state")
            return 0
        status, reasons, live = inspect(target)
        print(format_result(status, reasons, live))
        return {"FRESH": 0, "STALE": 1, "DRIFT": 1, "UNKNOWN": 2}[status]
    except FreshnessError as exc:
        print("Product freshness: UNKNOWN\n  - " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
