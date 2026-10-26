"""Evidence verification for approved durable GitHub events.

Do not treat claims inside event JSON as proof of a merged PR, published
release, or successful CI run. Owner acceptance is a separate explicit action.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from installer.model import CapsuleModelError
from installer.state_health import _download_json, FreshnessError

def verify_event(event: dict, *, fetch=None, confirm_owner: bool = False, token: str | None = None) -> None:
    repo = event.get("product_repository")
    url = event.get("evidence_url")
    kind = event.get("kind")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise CapsuleModelError("invalid product evidence repository")
    if not isinstance(url, str):
        raise CapsuleModelError("event evidence must be a URL")
    if kind == "owner-acceptance":
        if not confirm_owner or event.get("owner_confirmed") is not True:
            raise CapsuleModelError("owner acceptance requires a direct, explicit confirmation")
        if not url.startswith("https://") or len(url) > 1024:
            raise CapsuleModelError("owner acceptance requires a durable evidence URL")
        return
    patterns = {
        "merge": rf"https://github\.com/{re.escape(repo)}/pull/([0-9]+)",
        "release": rf"https://github\.com/{re.escape(repo)}/releases/tag/([A-Za-z0-9._+-]+)",
        "verified-regression": rf"https://github\.com/{re.escape(repo)}/actions/runs/([0-9]+)",
    }
    if kind not in patterns:
        raise CapsuleModelError("unsupported event evidence kind")
    match = re.fullmatch(patterns[kind], url)
    if not match:
        raise CapsuleModelError("event evidence URL does not match the product and event kind")
    read = fetch or _download_json
    api = "https://api.github.com/repos/" + repo
    if kind == "merge":
        endpoint = "/pulls/" + match.group(1)
    elif kind == "release":
        endpoint = "/releases/tags/" + quote(match.group(1), safe="")
    else:
        endpoint = "/actions/runs/" + match.group(1)
    try:
        result = read(api + endpoint, token)
    except Exception as exc:
        raise CapsuleModelError("authoritative GitHub evidence unavailable: " + str(exc)) from exc
    if not isinstance(result, dict):
        raise CapsuleModelError("GitHub evidence response must be an object")
    if kind == "merge" and (result.get("merged_at") is None or result.get("state") != "closed"):
        raise CapsuleModelError("GitHub pull request is not merged")
    if kind == "release" and (result.get("draft") is not False or result.get("tag_name") != match.group(1)):
        raise CapsuleModelError("GitHub release is not a published matching release")
    if kind == "verified-regression" and (
        result.get("status") != "completed" or result.get("conclusion") != "success"
    ):
        raise CapsuleModelError("GitHub regression workflow has not succeeded")
