#!/usr/bin/env python3
"""
Verify that every GitHub Action is pinned to a commit SHA, and that the version
comment beside each pin tells the truth.

Two failures this catches
-------------------------
1. A `uses:` line pinned to a mutable tag (`@v4`). Tags can be repointed by
   whoever owns the action, and both workflows here hold `contents: write`.
2. A SHA whose trailing `# vX.Y.Z` comment no longer matches the tag that SHA
   actually carries. A stale comment is worse than none — it is the only thing
   a reviewer reads before approving a bump.

Run:  python scripts/verify_pins.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*uses:\s*(?P<action>[\w.-]+/[\w.-]+)@(?P<ref>\S+)(?:\s+#\s*(?P<tag>\S+))?")
SHA = re.compile(r"^[0-9a-f]{40}$")


def api(path: str) -> object:
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "pin-verifier")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"    (HTTP {exc.code} querying {path})", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"    ({type(exc).__name__} querying {path})", file=sys.stderr)
    return []


def tags_for(action: str, sha: str) -> list[str]:
    """Every tag pointing at `sha`, dereferencing annotated tag objects."""
    names: list[str] = []
    for page in (1, 2):
        batch = api(f"/repos/{action}/tags?per_page=100&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        names += [t["name"] for t in batch if t.get("commit", {}).get("sha") == sha]
        if len(batch) < 100:
            break
    return names


def main() -> int:
    problems = 0
    checked = 0

    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for lineno, line in enumerate(wf.read_text().splitlines(), 1):
            m = USES.match(line)
            if not m:
                continue
            action, ref, tag = m["action"], m["ref"], m["tag"]
            checked += 1
            rel = wf.relative_to(ROOT).as_posix()
            where = f"{wf.name}:{lineno}"

            if not SHA.match(ref):
                print(f"::error file={rel},line={lineno}::{action} is pinned to "
                      f"mutable ref '{ref}'; use a 40-character commit SHA")
                problems += 1
                continue

            if not tag:
                print(f"::warning file={rel},line={lineno}::{action} has no "
                      f"'# vX.Y.Z' comment; add one so bumps are reviewable")
                continue

            names = tags_for(action, ref)
            if not names:
                print(f"::warning file={rel},line={lineno}::{action}@{ref[:8]} "
                      f"matches no released tag (claims {tag})")
            elif tag.lstrip("#").strip() not in names:
                print(f"::error file={rel},line={lineno}::{action} comment claims "
                      f"{tag} but that SHA is {', '.join(names)}")
                problems += 1
            else:
                print(f"  ok  {where:<28} {action} {tag}")

    print(f"\n{checked} pin(s) checked, {problems} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
