#!/usr/bin/env python3
"""Run folders: one fixed, configurable location outside git for every SEO run.

Layout (``run_root`` from ``seo/config/settings.json``):
    <run_root>/<site>/README.md                  plain-language guide to this folder
    <run_root>/<site>/<as_of>/<skill>[-<tag>]/   one run (.run_state.json, context.json, data/, findings.json, report.md)
    <run_root>/<site>/spreadsheets/<date>/       CSV copies of the history, for Excel / Google Sheets
    <run_root>/<site>/_cache/<capability>/       saved tool answers reused by later runs (seo/record.py)

Usage:
    python3 seo/runs.py root
    python3 seo/runs.py list --site pbservices.ge [--skill seo-audit]
    python3 seo/runs.py latest --site pbservices.ge --skill seo-audit [--max-age-days 45]
    python3 seo/runs.py prune [--older-than 180] [--dry-run]      # runs and cache entries
    python3 seo/runs.py export --site pbservices.ge [--out DIR] [--tables runs,totals,pages,queries,actions]
Exit codes: 0 = ok, 1 = error / nothing found.
"""
from __future__ import annotations

import argparse
import csv
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
EXPORT_DIR = "spreadsheets"

# Plain-language guide written into every site folder, so the data explains itself.
SITE_README = """# What is in this folder

One folder per site. Everything below is data collected for this site by the SEO reports.

- `<date>/<report>/` — one report, run on that date:
  - `report.md` — the report itself. Open or send this one.
  - `findings.json` — the same report as data.
  - `data/` — what each tool answered, saved exactly as it arrived.
    - `<name>.rows.json` — the same answer as plain rows, written when the answer is a table.
      Open this one when you want the numbers.
  - `computed/` — the figures calculated from those answers.
  - `pipeline.json` — what ran, what was skipped, and why.
- `spreadsheets/<date>/` — the history as CSV files, one line per item. Open with Excel or
  Google Sheets (File > Import). The folder has its own README listing each file.
- `_cache/` — answers the tools already gave, reused by later reports. Do not edit or delete by hand;
  `python3 seo/runs.py prune` clears what has expired.

Nothing here is in the repository: the folder lives outside it on purpose.
"""

SPREADSHEET_README = """# Spreadsheet files

One line per item, ready for Excel or Google Sheets (File > Import > CSV).

- `runs.csv` — one line per report: date, report, status, the period it covers, tool calls made.
- `totals.csv` — clicks, impressions, click rate and average position per period.
- `pages.csv` — one line per page, for every period the report pulled (current, comparison and each week).
- `queries.csv` — one line per search query, same coverage.
- `totals.csv` — also carries the weekly brief's Monday–Sunday weeks (`period` = week).
- `actions.csv` — every recommended action, with impact, effort, page, keyword and the reason.

Dates are written as YYYY-MM-DD so both spreadsheets read them the same way.
If your spreadsheet puts everything in one column, import with comma as the separator."""

TABLES = ("runs", "totals", "pages", "queries", "actions")
COLUMNS = {
    "runs": ["date", "report", "status", "period_start", "period_end", "compared_with", "tool_calls",
             "seconds", "sources_missing", "report_file"],
    "totals": ["date", "report", "period", "period_start", "period_end", "clicks", "impressions",
               "click_rate_percent", "average_position"],
    "pages": ["date", "report", "period_start", "period_end", "page", "clicks", "impressions",
              "click_rate_percent", "average_position"],
    "queries": ["date", "report", "period_start", "period_end", "query", "clicks", "impressions",
                "click_rate_percent", "average_position"],
    "actions": ["date", "report", "action", "impact", "effort", "page", "keyword", "why", "estimated_clicks"],
}


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


# --------------------------------------------------------------- exporting ---
def ensure_readme(site: str) -> Path:
    """Write the plain-language guide into the site folder once (never overwrites)."""
    p = run_root() / _name(site, "site") / "README.md"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(SITE_README)
    return p


def plain_rows(obj):
    """The rows inside a saved tool answer, whatever shape it was stored in (as received, or plain rows)."""
    for _ in range(3):  # "as received" wraps the real answer in content[].text, sometimes twice
        if isinstance(obj, list):
            return [r for r in obj if isinstance(r, dict)]
        if not isinstance(obj, dict):
            return []
        if isinstance(obj.get("rows"), list):
            return [r for r in obj["rows"] if isinstance(r, dict)]
        wrapped = None
        for part in obj.get("content") or []:
            text = part.get("text") if isinstance(part, dict) else None
            if isinstance(text, str) and text.strip().startswith(("{", "[")):
                wrapped = text
                break
        if wrapped is None:
            return []
        try:
            obj = json.loads(wrapped)
        except json.JSONDecodeError:
            return []
    return []


def _read(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _first_key(row: dict) -> str:
    keys = row.get("keys")
    if isinstance(keys, list) and keys:
        return str(keys[0])
    for name in ("page", "url", "query"):
        if name in row:
            return str(row[name])
    return ""


def _rate(value):
    """A 0-1 rate as a percentage; a value already expressed in percent is left alone (as gsc_metrics does)."""
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return ""
    return round(rate if abs(rate) > 1 else rate * 100, 2)


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else ""


def _period_rows(run_dir: Path, window: dict) -> dict:
    """(label -> (totals block, period start, period end)) for the window and its comparison."""
    totals = _read(run_dir / "computed" / "totals.json") or {}
    out = {}
    for label, start_key, end_key in (("current", "startDate", "endDate"),
                                      ("previous", "compareStartDate", "compareEndDate")):
        block = totals.get(label) if isinstance(totals, dict) else None
        if isinstance(block, dict):
            out[label] = (block, window.get(start_key, ""), window.get(end_key, ""))
    return out


def _call_rows(run_dir: Path, cap: str, value_name: str, run_date: str, report: str) -> list[dict]:
    """Rows of every pull made with ``cap`` — current, comparison and per-week pulls alike.

    The call's own dates become the period, so a weekly run keeps its weeks and a comparison keeps its
    window; calls recorded as an explicit off-window exception are skipped (they are not part of the report).
    """
    calls = _read(run_dir / "context.json") or {}
    out = []
    for call in calls.get("calls") or []:
        if not isinstance(call, dict) or call.get("cap") != cap or call.get("window_exception"):
            continue
        source = run_dir / call.get("rows_file", "") if call.get("rows_file") else None
        if not source or not source.exists():
            source = run_dir / (call.get("file") or "")
        payload = _read(source) if source else None
        args = call.get("args") or {}
        ranges = args.get("date_ranges") or [{}]
        start = args.get("startDate") or (ranges[0] or {}).get("start_date", "")
        end = args.get("endDate") or (ranges[0] or {}).get("end_date", "")
        for row in plain_rows(payload) if payload is not None else []:
            out.append({"date": run_date, "report": report, "period_start": start, "period_end": end,
                        value_name: _first_key(row), "clicks": _number(row.get("clicks")),
                        "impressions": _number(row.get("impressions")),
                        "click_rate_percent": _rate(row.get("ctr")),
                        "average_position": _number(row.get("position"))})
    return out


def export(site: str, out_dir=None, tables=None, as_of: dt.date | None = None) -> list[Path]:
    """Write the whole history as CSV files a spreadsheet can open (one line per item)."""
    _name(site, "site")
    wanted = list(tables or TABLES)
    if not wanted:
        raise ValueError(f"no tables selected (choose from {', '.join(TABLES)})")
    unknown = sorted(set(wanted) - set(TABLES))
    if unknown:
        raise ValueError(f"unknown table(s) {unknown} (choose from {', '.join(TABLES)})")
    dest = Path(out_dir) if out_dir else run_root() / site / EXPORT_DIR / (as_of or dt.date.today()).isoformat()
    rows = {t: [] for t in wanted}
    for r in sorted(runs(site), key=lambda x: (x["as_of"] or "", x["created"] or "")):  # oldest first
        run_dir, run_date = Path(r["path"]), r["as_of"] or ""
        state = _read(run_dir / ".run_state.json") or {}
        window = {**state.get("window", {}), "skill": r["skill"]}
        pipeline = _read(run_dir / "pipeline.json") or {}
        findings = _read(run_dir / "findings.json") or {}
        if "runs" in rows:
            seconds = sum(step.get("seconds") or 0 for step in pipeline.get("steps") or [])
            rows["runs"].append({
                "date": run_date, "report": r["skill"], "status": pipeline.get("status", ""),
                "period_start": window.get("startDate", ""), "period_end": window.get("endDate", ""),
                "compared_with": (f"{window['compareStartDate']} to {window['compareEndDate']}"
                                  if window.get("compareStartDate") else ""),
                "tool_calls": sum(step.get("calls") or 1 for step in pipeline.get("steps") or []
                                  if step.get("cap") and step.get("status") in ("ok", "cached")),
                "seconds": round(seconds, 1) if seconds else "",
                "sources_missing": len(pipeline.get("unavailable") or []),
                "report_file": "report.md" if (run_dir / "report.md").exists() else ""})
        if "totals" in rows:
            brief = _read(run_dir / "computed" / "brief.json") or {}
            for week in brief.get("kpis") or []:  # the weekly brief: one row per Monday–Sunday week
                rows["totals"].append({"date": run_date, "report": r["skill"], "period": "week",
                                       "period_start": week.get("week", ""), "period_end": "",
                                       "clicks": _number(week.get("clicks")),
                                       "impressions": _number(week.get("impressions")),
                                       "click_rate_percent": _number(week.get("ctr")),
                                       "average_position": _number(week.get("position"))})
            for label, (block, start, end) in _period_rows(run_dir, window).items():
                rows["totals"].append({"date": run_date, "report": r["skill"], "period": label,
                                       "period_start": start, "period_end": end,
                                       "clicks": _number(block.get("clicks")),
                                       "impressions": _number(block.get("impressions")),
                                       "click_rate_percent": _rate(block.get("ctr")),
                                       "average_position": _number(block.get("position"))})
        if "pages" in rows:
            rows["pages"] += _call_rows(run_dir, "gsc.page", "page", run_date, r["skill"])
        if "queries" in rows:
            rows["queries"] += _call_rows(run_dir, "gsc.query", "query", run_date, r["skill"])
        if "actions" in rows:
            for raw in findings.get("actions") or []:
                a = raw if isinstance(raw, dict) else {"action": str(raw)}
                rows["actions"].append({
                    "date": run_date, "report": r["skill"], "action": a.get("action", ""),
                    "impact": a.get("impact", ""), "effort": a.get("effort", ""), "page": a.get("page", ""),
                    "keyword": a.get("keyword", ""), "why": a.get("why", ""),
                    "estimated_clicks": _number(a.get("est_clicks"))})
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for table in wanted:
        f = dest / f"{table}.csv"
        with f.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM: Excel reads UTF-8 correctly
            w = csv.DictWriter(fh, fieldnames=COLUMNS[table], extrasaction="ignore")
            w.writeheader()
            w.writerows(rows[table])
        written.append(f)
    (dest / "README.md").write_text(SPREADSHEET_README)
    ensure_readme(site)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["root", "list", "latest", "prune", "export"])
    ap.add_argument("--site")
    ap.add_argument("--skill")
    ap.add_argument("--max-age-days", dest="max_age", type=int, default=None)
    ap.add_argument("--older-than", dest="older", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", help="folder for the CSV files (default: <site>/spreadsheets/<today>)")
    ap.add_argument("--tables", help=f"comma-separated subset of {', '.join(TABLES)} (default: all)")
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
        if a.command == "export":
            tables = [t.strip() for t in a.tables.split(",")] if a.tables else None
            written = export(a.site, a.out, tables)
            print(f"wrote {len(written)} file(s) to {Path(written[0]).parent}")
            for f in written:
                print(f"  {f.name:<14} {sum(1 for _ in f.open(encoding='utf-8-sig')) - 1} rows")
            return 0
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
