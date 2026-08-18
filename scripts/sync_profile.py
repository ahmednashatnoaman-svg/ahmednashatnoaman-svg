#!/usr/bin/env python3
"""
Profile sync engine.

Regenerates every marker-delimited block inside README.md from live GitHub data
plus the editorial content in profile.config.json.

Design notes
------------
* Zero third-party dependencies (stdlib urllib only) so CI needs no `pip install`.
* Every generated region is delimited by `<!-- KEY:START -->` / `<!-- KEY:END -->`.
  Prose outside those markers is hand-written and is never touched.
* The script is idempotent: it rewrites README.md only when the rendered output
  actually differs, so the scheduled job produces no empty commits.

Usage
-----
    python scripts/sync_profile.py            # rewrite README.md in place
    python scripts/sync_profile.py --check    # exit 1 if README.md is stale
"""

from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "profile.config.json"
README_PATH = ROOT / "README.md"
API = "https://api.github.com"

CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
USER = CFG["identity"]["username"]
THEME = CFG["theme"]


# --------------------------------------------------------------------------- #
# GitHub API
# --------------------------------------------------------------------------- #
def _token() -> str:
    """Prefer the CI-injected token; fall back to the local `gh` session."""
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


TOKEN = _token()


def api(path: str, params: dict | None = None) -> object:
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-profile-sync")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"  ! HTTP {exc.code} on {path}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - network is best-effort
        print(f"  ! {type(exc).__name__} on {path}: {exc}", file=sys.stderr)
    return [] if path.endswith(("repos", "events/public")) else {}


def api_paged(path: str, params: dict | None = None, cap: int = 300) -> list:
    """Walk GitHub's pagination until exhausted or `cap` items collected."""
    items: list = []
    page = 1
    while len(items) < cap:
        batch = api(path, {**(params or {}), "per_page": 100, "page": page})
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items[:cap]


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def enc(text: str) -> str:
    """Escape a string for a shields.io path segment."""
    return (
        str(text)
        .replace("-", "--")
        .replace("_", "__")
        .replace(" ", "_")
    )


def badge(label: str, message: str, color: str, logo: str = "",
          logo_color: str = "", label_color: str = "") -> str:
    url = f"https://img.shields.io/badge/{enc(label)}-{enc(message)}-{color}"
    query = ["style=for-the-badge"]
    if logo:
        query.append(f"logo={logo}")
    query.append(f"logoColor={logo_color or THEME['primary']}")
    query.append(f"labelColor={label_color or THEME['bg']}")
    return f'<img src="{url}?{"&".join(query)}" alt="{label} {message}" />'


def chip(label: str, logo: str = "", color: str = "", logo_color: str = "") -> str:
    """A single-segment pill used for the tech stack."""
    url = f"https://img.shields.io/badge/{enc(label)}-{color or THEME['surface']}"
    query = ["style=for-the-badge"]
    if logo:
        query.append(f"logo={logo}")
    query.append(f"logoColor={logo_color or 'white'}")
    return f'<img src="{url}?{"&".join(query)}" alt="{label}" />'


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def bytes_human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


# --------------------------------------------------------------------------- #
# Data collection
# --------------------------------------------------------------------------- #
def collect() -> dict:
    print("→ fetching profile")
    user = api(f"/users/{USER}") or {}

    print("→ fetching repositories")
    repos = api_paged(f"/users/{USER}/repos", {"sort": "updated"})
    owned = [r for r in repos if not r.get("fork") and not r.get("archived")]

    print(f"→ fetching language breakdown across {len(owned)} repos")
    overrides = CFG.get("language_overrides", {})
    languages: dict[str, int] = {}
    for repo in owned:
        data = api(f"/repos/{USER}/{repo['name']}/languages")
        if not isinstance(data, dict):
            continue
        for lang, size in data.items():
            languages[overrides.get(lang, lang)] = languages.get(overrides.get(lang, lang), 0) + size

    external = []
    for full_name in CFG.get("featured", {}).get("external", []):
        repo = api(f"/repos/{full_name}")
        if isinstance(repo, dict) and repo.get("name"):
            external.append(repo)
    if external:
        print(f"→ pulled {len(external)} external repo(s)")

    print("→ fetching public activity")
    events = api_paged(f"/users/{USER}/events/public", cap=100)

    stars = sum(r.get("stargazers_count", 0) for r in owned)
    forks = sum(r.get("forks_count", 0) for r in owned)
    watchers = sum(r.get("watchers_count", 0) for r in owned)

    return {
        "user": user,
        "repos": owned,
        "external": external,
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
        "events": events,
        "stars": stars,
        "forks": forks,
        "watchers": watchers,
    }


# --------------------------------------------------------------------------- #
# Block builders — each returns the inner markdown for one marker region
# --------------------------------------------------------------------------- #
def block_stats(d: dict) -> str:
    u, repos = d["user"], d["repos"]
    total_bytes = sum(d["languages"].values())
    rows = [
        ("Public Repos", human(len(repos)), THEME["primary"], "github"),
        ("Total Stars", human(d["stars"]), THEME["orange"], "star"),
        ("Followers", human(u.get("followers", 0)), THEME["secondary"], "githubsponsors"),
        ("Forks", human(d["forks"]), THEME["cyan"], "git"),
        ("Languages", human(len(d["languages"])), THEME["green"], "codeforces"),
        ("Code Shipped", bytes_human(total_bytes).replace(" ", "_"), THEME["red"], "files"),
    ]
    pills = "\n  ".join(
        badge(label, value, THEME["surface"], logo, color)
        for label, value, color, logo in rows
    )
    return f'<div align="center">\n  {pills}\n</div>'


def block_langbar(d: dict) -> str:
    langs = d["languages"]
    if not langs:
        return "_Language data unavailable._"
    total = sum(langs.values()) or 1
    top = list(langs.items())[:8]
    width = 24

    lines = ["```text"]
    for name, size in top:
        pct = size / total * 100
        filled = max(1, round(pct / 100 * width))
        bar = "█" * filled + "░" * (width - filled)
        lines.append(f"{name[:22]:<22} {bar}  {pct:5.2f}%")
    lines.append("```")
    return "\n".join(lines)


def block_tech(_: dict) -> str:
    out: list[str] = ['<div align="center">', ""]
    for group in CFG["stack"]:
        out.append(f'<h4>{group["title"]}</h4>')
        out.append("")
        if group.get("skillicons"):
            icons = ",".join(group["skillicons"])
            out.append(
                f'<a href="https://skillicons.dev">'
                f'<img src="https://skillicons.dev/icons?i={icons}&theme=dark&perline=12" '
                f'alt="{group["title"]}" /></a>'
            )
            out.append("")
        if group.get("badges"):
            pills = "\n".join(
                chip(b["label"], b.get("logo", ""), b.get("color", THEME["surface"]),
                     b.get("logoColor", "white"))
                for b in group["badges"]
            )
            out.append(pills)
            out.append("")
        out.append("<br/>")
        out.append("")
    out.append("</div>")
    return "\n".join(out)


def block_education(_: dict) -> str:
    pills = "\n  ".join(
        badge(e["badge_label"], e["badge_message"], THEME["surface"], e.get("logo", ""))
        for e in CFG["education"]
    )
    rows = "\n".join(
        f'| **{e["credential"]}** | {e["institution"]} | `{e["period"]}` |'
        for e in CFG["education"]
    )
    certs = "\n  ".join(
        badge(c["label"], c["message"], THEME["surface"], c.get("logo", ""), THEME["green"])
        for c in CFG["certifications"]
    )
    return (
        f'<div align="center">\n  {pills}\n</div>\n\n'
        "| Credential | Institution | Period |\n"
        "| :--- | :--- | :---: |\n"
        f"{rows}\n\n"
        f'<div align="center">\n\n<sub><b>Certifications & Professional Programs</b></sub>\n\n'
        f'  {certs}\n</div>'
    )


def block_focus(_: dict) -> str:
    f = CFG["focus"]
    icons = {
        "building": ("🚀", "Currently building"),
        "learning": ("🌱", "Currently learning"),
        "collaborating_on": ("🤝", "Open to collaborate on"),
        "asking_about": ("💬", "Ask me about"),
        "fun_fact": ("⚡", "Fun fact"),
    }
    rows = "\n".join(
        f'| {icons[k][0]} | **{icons[k][1]}** | {f[k]} |'
        for k in icons if f.get(k)
    )
    return "| | | |\n| :---: | :--- | :--- |\n" + rows


def block_projects(d: dict) -> str:
    cfg = CFG["featured"]
    by_name: dict[str, dict] = {}
    for repo in d["repos"] + d.get("external", []):
        by_name[repo["full_name"]] = repo
        by_name.setdefault(repo["name"], repo)
    exclude = set(cfg.get("exclude", []))

    ordered: list[dict] = []
    seen_ids: set[int] = set()

    def take(repo: dict) -> None:
        if repo["id"] not in seen_ids:
            seen_ids.add(repo["id"])
            ordered.append(repo)

    for name in cfg.get("pinned", []):
        repo = by_name.get(name)
        if repo and repo["name"] not in exclude:
            take(repo)
    rest = sorted(
        (r for r in d["repos"] if r["name"] not in exclude),
        key=lambda r: (-r.get("stargazers_count", 0), r.get("updated_at", "")),
    )
    for repo in rest:
        take(repo)
    ordered = ordered[: cfg.get("table_limit", 8)]
    if not ordered:
        return "_No public repositories found._"

    # Repo cards for the top N, then a table for the remainder.
    card_count = min(cfg.get("card_count", 4), len(ordered))
    cards: list[str] = []
    for repo in ordered[:card_count]:
        cards.append(
            f'  <a href="{repo["html_url"]}">\n'
            f'    <img width="49%" '
            f'src="https://github-readme-stats.vercel.app/api/pin/'
            f'?username={repo.get("owner", {}).get("login", USER)}'
            f'&repo={repo["name"]}&theme={THEME["card_theme"]}'
            f'&hide_border=true&bg_color={THEME["bg"]}&title_color={THEME["primary"]}'
            f'&icon_color={THEME["secondary"]}&text_color={THEME["text"]}" '
            f'alt="{repo["name"]}" />\n'
            f'  </a>'
        )

    overrides = CFG.get("repo_overrides", {})
    rows = []
    for repo in ordered:
        override = overrides.get(repo["name"], {})
        raw_desc = repo.get("description") or override.get("description") or "—"
        desc = raw_desc.replace("|", "\\|").strip()
        if len(desc) > 118:
            desc = desc[:115].rstrip() + "…"
        lang = repo.get("language") or "—"
        lang = CFG.get("language_overrides", {}).get(lang, lang)
        stars = repo.get("stargazers_count", 0)
        star_cell = f"⭐ {stars}" if stars else "—"
        topics = repo.get("topics") or override.get("topics") or []
        topic_cell = " ".join(f"`{t}`" for t in topics[:3]) if topics else f"`{lang}`"
        owner = repo.get("owner", {}).get("login", "")
        title = repo["name"]
        if owner and owner.lower() != USER.lower():
            title = f'{repo["name"]}<br/><sub>@{owner}</sub>'
        rows.append(
            f'| **[{title}]({repo["html_url"]})** | {desc} | {topic_cell} | {star_cell} |'
        )

    return (
        f'<div align="center">\n{chr(10).join(cards)}\n</div>\n\n'
        "<details>\n<summary><b>📚 Browse the full project index</b></summary>\n<br/>\n\n"
        "| Project | What it does | Stack | Stars |\n"
        "| :--- | :--- | :--- | :---: |\n"
        + "\n".join(rows)
        + "\n\n</details>"
    )


VERB = {
    "PushEvent": "pushed to",
    "CreateEvent": "created",
    "WatchEvent": "starred",
    "ForkEvent": "forked",
    "IssuesEvent": "opened an issue in",
    "IssueCommentEvent": "commented in",
    "PullRequestEvent": "opened a PR in",
    "ReleaseEvent": "released",
    "PublicEvent": "open-sourced",
    "DeleteEvent": "cleaned up",
}


def block_activity(d: dict) -> str:
    act = CFG.get("activity", {})
    limit = act.get("max_events", 6)
    muted = {r.lower() for r in act.get("exclude_repos", [])}
    owned_only = act.get("owned_only", True)
    lines: list[str] = []
    seen: set[tuple] = set()

    for ev in d["events"]:
        kind = ev.get("type", "")
        if kind not in VERB:
            continue
        repo = ev.get("repo", {}).get("name", "")
        if not repo or repo.lower() in muted:
            continue
        if owned_only and not repo.lower().startswith(f"{USER.lower()}/"):
            continue
        key = (kind, repo)
        if key in seen:
            continue
        seen.add(key)

        detail = ""
        payload = ev.get("payload", {})
        if kind == "PushEvent":
            # `size` is absent on some event payloads; only annotate when real.
            n = payload.get("size") or payload.get("distinct_size") or 0
            if n:
                detail = f" ({n} commit{'s' if n != 1 else ''})"
        elif kind == "CreateEvent":
            detail = f' {payload.get("ref_type", "")}'.rstrip()
        elif kind == "ReleaseEvent":
            detail = f' `{payload.get("release", {}).get("tag_name", "")}`'

        when = ev.get("created_at", "")
        try:
            stamp = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")
        except ValueError:
            stamp = "—"

        short = repo.split("/")[-1]
        lines.append(
            f'- `{stamp}` &nbsp; **{VERB[kind]}**{detail} '
            f'[{short}](https://github.com/{repo})'
        )
        if len(lines) >= limit:
            break

    if not lines:
        return "_No recent public activity._"
    return "\n".join(lines)


def block_updated(_: dict) -> str:
    now = datetime.now(timezone.utc)
    return (
        f'<div align="center">\n  <sub>Rebuilt automatically · '
        f'<b>{now.strftime("%d %B %Y, %H:%M")} UTC</b> · '
        f'<a href="https://github.com/{USER}/{USER}/actions">view the pipeline</a></sub>\n</div>'
    )


BUILDERS = {
    "STATS": block_stats,
    "LANGBAR": block_langbar,
    "TECH": block_tech,
    "EDUCATION": block_education,
    "FOCUS": block_focus,
    "PROJECTS": block_projects,
    "ACTIVITY": block_activity,
    "UPDATED": block_updated,
}


# --------------------------------------------------------------------------- #
# Marker replacement
# --------------------------------------------------------------------------- #
def splice(markdown: str, key: str, body: str) -> str:
    start, end = f"<!-- {key}:START -->", f"<!-- {key}:END -->"
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end), re.DOTALL
    )
    if not pattern.search(markdown):
        print(f"  ! marker {key} not found in README.md", file=sys.stderr)
        return markdown
    return pattern.sub(f"{start}\n{body}\n{end}", markdown)


def main() -> int:
    check_only = "--check" in sys.argv
    data = collect()

    readme = README_PATH.read_text(encoding="utf-8")
    original = readme
    for key, builder in BUILDERS.items():
        try:
            readme = splice(readme, key, builder(data))
            print(f"  ✓ {key}")
        except Exception as exc:  # noqa: BLE001 - one bad block must not kill the run
            print(f"  ✗ {key}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if readme == original:
        print("README.md already current — nothing to write.")
        return 0

    if check_only:
        print("README.md is stale.", file=sys.stderr)
        return 1

    README_PATH.write_text(readme, encoding="utf-8")
    print(f"README.md updated ({len(readme):,} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
