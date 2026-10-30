#!/usr/bin/env python3
"""Run folders: one fixed, configurable location outside git for every SEO run.

Layout (``run_root`` from ``seo/config/settings.json``):
    <run_root>/<site>/<as_of>/<skill>[-<tag>]/   one run (.run_state.json, context.json, data/, findings.json, report.md)
    <run_root>/<site>/_cache/<capability>/       shared data cache (seo/record.py)

Usage:
    python3 seo/runs.py root
    python3 seo/runs.py list --site pbservices.ge [--skill seo-audit]
    python3 seo/runs.py latest --site pbservices.ge --skill seo-audit [--max-age-days 45]
    python3 seo/runs.py prune [--older-than 180] [--dry-run]      # runs and cache entries
Exit codes: 0 = ok, 1 = error / nothing found.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SETTINGS = HERE / "config" / "settings.json"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")  # site, skill and tag names (no path tricks)
CACHE_DIR = "_cache"


def settings() -> dict:
    return json.loads(SETTINGS.read_text())


def run_root() -> Path:
    root = Path(settings()["run_root"]).expanduser()
    return root if root.is_absolute() else REPO / root


def _name(value: str, what: str) -> str:
    if not isinstance(value, str) or not NAME_RE.match(value) or ".." in value:
        raise ValueError(f"invalid {what} {value!r} (lowercase letters, digits, '.', '-')")
    return value


def ignore_problem(root: Path | None = None) -> str | None:
    """Why ``root`` could be committed by accident (None = safe: outside the repo or git-ignored)."""
    root = (root or run_root()).resolve()
    try:
        root.relative_to(REPO.resolve())
    except ValueError:
        return None
    try:
        res = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", str(root / "probe")],
                             capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None  # no git: nothing can be committed from here
    if res.returncode == 1:
        return f"run_root {root} is inside the repo but not in .gitignore — site data could be committed"
    return None


def run_dir(site: str, as_of: str, skill: str, tag: str | None = None) -> Path:
    name = _name(skill, "skill") + (f"-{_name(tag, 'tag')}" if tag else "")
    dt.date.fromisoformat(as_of)
    return run_root() / _name(site, "site") / as_of / name


def cache_dir(site: str) -> Path:
    return run_root() / _name(site, "site") / CACHE_DIR


def runs(site: str, skill: str | None = None) -> list[dict]:
    """Every run of a site (newest first): skill, tag, as_of, path, completed (findings with a verdict)."""
    base = run_root() / _name(site, "site")
    out = []
    for state in base.glob("*/*/.run_state.json") if base.exists() else []:
        if state.parent.parent.name == CACHE_DIR:
            continue
        try:
            st = json.loads(state.read_text())
        except json.JSONDecodeError:
            continue
        if skill and st.get("skill") != skill:
            continue
        f = state.parent / "findings.json"
        try:
            done = bool(json.loads(f.read_text()).get("verdict", "").strip()) if f.exists() else False
        except json.JSONDecodeError:
            done = False
        out.append({"skill": st.get("skill"), "tag": st.get("tag"), "as_of": st.get("window", {}).get("as_of"),
                    "created": st.get("created", ""), "path": str(state.parent), "completed": done,
                    "report": (state.parent / "report.md").exists()})
    return sorted(out, key=lambda r: (r["as_of"] or "", r["created"]), reverse=True)


def latest(site: str, skill: str, max_age_days: int | None = None, as_of: dt.date | None = None,
           tag: str | None = None) -> dict | None:
    """Newest completed run of ``skill`` (optionally only within ``max_age_days`` of ``as_of``)."""
    today = as_of or dt.datetime.now(dt.timezone.utc).date()
    for r in runs(site, skill):
        if not r["completed"] or (tag is not None and r["tag"] != tag):
            continue
        if max_age_days is not None and (today - dt.date.fromisoformat(r["as_of"])).days > max_age_days:
            continue
        return r
    return None


def prune(older_than_days: int | None = None, dry_run: bool = False, as_of: dt.date | None = None) -> list[str]:
    """Delete runs (by as_of folder) and cache entries (by mtime) older than the retention period."""
    days = older_than_days if older_than_days is not None else int(settings()["retention_days"])
    today = as_of or dt.datetime.now(dt.timezone.utc).date()
    cutoff = today - dt.timedelta(days=days)
    root, removed = run_root(), []
    for site_dir in (p for p in root.glob("*") if p.is_dir()) if root.exists() else []:
        for d in site_dir.iterdir():
            if d.name == CACHE_DIR:
                for f in d.rglob("*.json"):
                    if dt.date.fromtimestamp(f.stat().st_mtime) < cutoff:
                        removed.append(str(f))
                        if not dry_run:
                            f.unlink()
                continue
            try:
                when = dt.date.fromisoformat(d.name)
            except ValueError:
                continue
            if when < cutoff:
                removed.append(str(d))
                if not dry_run:
                    shutil.rmtree(d)
    return removed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["root", "list", "latest", "prune"])
    ap.add_argument("--site")
    ap.add_argument("--skill")
    ap.add_argument("--max-age-days", dest="max_age", type=int, default=None)
    ap.add_argument("--older-than", dest="older", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.command == "root":
            print(run_root())
            problem = ignore_problem()
            if problem:
                print(f"WARNING {problem}", file=sys.stderr)
            return 0
        if a.command == "prune":
            for p in prune(a.older, a.dry_run):
                print(("would remove " if a.dry_run else "removed ") + p)
            return 0
        if not a.site:
            ap.error("--site is required")
        if a.command == "list":
            print(json.dumps(runs(a.site, a.skill), indent=2))
            return 0
        if not a.skill:
            ap.error("--skill is required for latest")
        r = latest(a.site, a.skill, a.max_age)
        if not r:
            print(f"no completed {a.skill} run for {a.site}", file=sys.stderr)
            return 1
        print(json.dumps(r, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
