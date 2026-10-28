#!/usr/bin/env python3
"""Check numeric stable versions and enforce increments on product changes."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NUMERIC = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")

def parse(text: str, historical: bool = False) -> tuple[int, int, int]:
    match = NUMERIC.fullmatch(text)
    if match:
        return tuple(int(x) for x in match.groups())
    if historical and text == "2.0.0-dev":
        return (2, 0, 0)
    raise ValueError(f"non-numeric version: {text}")

def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True,
                          capture_output=True, check=True).stdout

def check() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    current = parse(version)
    from installer.model import PROJECT_MANAGER_VERSION
    if version != PROJECT_MANAGER_VERSION:
        raise ValueError(f"VERSION differs from model constant: {version} vs {PROJECT_MANAGER_VERSION}")
    for path, keys in (
        ("schemas/capsule.schema.json", ("version", "project_manager_version")),
        ("schemas/manifest.schema.json", ("context_version", "project_manager_version")),
    ):
        schema = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for key in keys:
            field = schema["properties"][key]
            if version not in field.get("enum", [field.get("const")]):
                raise ValueError(f"{path}: {key} missing version {version}")
    base = os.environ.get("BASE_SHA", "").strip()
    if not base or base == "0" * 40:
        return
    previous = git("show", f"{base}:VERSION").strip()
    old = parse(previous, historical=True)
    files = git("diff", "--name-only", base, "HEAD", "--",
                "installer/", "schemas/", "templates/").splitlines()
    if current < old:
        raise ValueError(f"version regression: {previous} -> {version}")
    if files and current == old:
        raise ValueError(f"product files changed without version increment: {', '.join(files[:12])}")

if __name__ == "__main__":
    try:
        check()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"VERSION CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("VERSION CHECK PASSED")
