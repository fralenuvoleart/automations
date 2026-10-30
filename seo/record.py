#!/usr/bin/env python3
"""Record a raw tool response as run evidence (feeds the hallucination check).

Every number or URL in a report must trace back to a recorded response. Call this
right after each MCP/tool call: it stores the raw response in
``{run_dir}/data/<name>.json`` and appends provenance (capability, full call
args incl. the registry's fixed args, timestamp) to ``{run_dir}/context.json``.
``validate_report.py --data {run_dir}/context.json`` then checks every URL in the
findings against these files.

Guards: the capability must exist; supplied args must be runtime args of that
capability; ``startDate``/``endDate`` must equal the run window (or its comparison
window) from ``.run_state.json`` unless ``--allow-window`` documents an exception.

Usage:
    python3 seo/record.py --run-dir D --cap gsc.page --name page_cur \\
        --args '{"siteUrl": "sc-domain:example.com", "startDate": "2026-07-29", "endDate": "2026-10-26"}' \\
        --response-file resp.json            # or '-' for stdin
    python3 seo/record.py --run-dir D --source site_crawl --name crawl --response-file crawl.json
Exit codes: 0 = recorded, 1 = rejected.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resolve  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _parse_response(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"text": raw}


def _window_ok(args: dict, state: dict) -> str | None:
    """GSC startDate/endDate and GA4 date_ranges must match the run window, its comparison or one of its weeks."""
    win = state.get("window") or {}
    if win.get("source") == "snapshot":
        return None
    allowed = [(win.get("startDate"), win.get("endDate"))]
    if win.get("compareStartDate"):
        allowed.append((win.get("compareStartDate"), win.get("compareEndDate")))
    allowed += [(w.get("startDate"), w.get("endDate")) for w in win.get("weeks") or [] if isinstance(w, dict)]
    pairs = []
    if "startDate" in args or "endDate" in args:
        pairs.append((args.get("startDate"), args.get("endDate")))
    for r in args.get("date_ranges") or []:
        if isinstance(r, dict):
            pairs.append((r.get("start_date"), r.get("end_date")))
    bad = [p for p in pairs if p not in allowed]
    if bad:
        return f"window {bad} matches neither the run window, its comparison window nor its weeks {allowed}"
    return None


def record(run_dir: Path, name: str, raw: str, cap: str | None = None, source: str | None = None,
           args: dict | None = None, allow_window: str | None = None) -> Path:
    if not NAME_RE.match(name):
        raise ValueError(f"--name must match {NAME_RE.pattern}")
    if bool(cap) == bool(source):
        raise ValueError("pass exactly one of --cap or --source")
    args = args or {}
    entry: dict = {"name": name, "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if cap:
        _, caps, _, _ = resolve.load()
        if cap not in caps:
            raise ValueError(f"unknown capability '{cap}'")
        c = caps[cap]
        extra = sorted(set(args) - set(c.get("runtime") or []))
        if extra:
            raise ValueError(f"{cap}: {extra} are not runtime args (fixed args come from the registry; runtime = {c.get('runtime')})")
        state_p = run_dir / ".run_state.json"
        if state_p.exists():
            problem = _window_ok(args, json.loads(state_p.read_text()))
            if problem and not allow_window:
                raise ValueError(f"{cap}: {problem} (pass --allow-window '<reason>' to document an exception)")
            if problem:
                entry["window_exception"] = allow_window
        entry.update({"cap": cap, "server": c["server"], "tool": c["tool"], "args": {**(c.get("args") or {}), **args}})
    else:
        entry.update({"source": source, "args": args})

    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / f"{name}.json"
    out.write_text(json.dumps(_parse_response(raw), ensure_ascii=False, indent=1) + "\n")
    entry["file"] = f"data/{name}.json"

    ctx_p = run_dir / "context.json"
    ctx = json.loads(ctx_p.read_text()) if ctx_p.exists() else {}
    if not isinstance(ctx, dict):
        ctx = {}
    calls = [c for c in ctx.get("calls", []) if c.get("name") != name]  # re-recording replaces
    calls.append(entry)
    ctx["calls"] = calls
    ctx_p.write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--name", required=True, help="short id, e.g. page_cur, query_prev, crawl")
    ap.add_argument("--cap", help="capability ID (the <!--cap:ID--> next to the call in the skill)")
    ap.add_argument("--source", help="non-MCP source label, e.g. site_crawl, site_profile, user")
    ap.add_argument("--args", default="{}", help="JSON object of the runtime args you supplied")
    ap.add_argument("--response-file", required=True, help="file with the raw response, or '-' for stdin")
    ap.add_argument("--allow-window", default=None, help="reason for a deliberate off-window call")
    a = ap.parse_args(argv)
    try:
        raw = sys.stdin.read() if a.response_file == "-" else Path(a.response_file).read_text()
        out = record(Path(a.run_dir), a.name, raw, a.cap, a.source, json.loads(a.args), a.allow_window)
    except (ValueError, OSError) as e:  # JSONDecodeError is a ValueError
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(f"recorded {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
