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

Shared cache (runs seeded with ``--site``): every recorded response that is cacheable is
also stored under ``<run_root>/<site>/_cache/`` keyed by capability + full args. Responses for
a dated window (GSC startDate/endDate, GA4 date_ranges) never change, so they are kept; live
capabilities are kept for their ``policy.cache_ttl_days``; anything else is not cached.
``--from-cache`` records a cached response instead of calling the tool (exit 3 = miss).

Usage:
    python3 seo/record.py --run-dir D --cap gsc.page --name page_cur \\
        --args '{"siteUrl": "sc-domain:example.com", "startDate": "2026-07-29", "endDate": "2026-10-26"}' \\
        --response-file resp.json            # or '-' for stdin
    python3 seo/record.py --run-dir D --cap gsc.page --name page_cur --args '{…}' --from-cache   # reuse, no call
    python3 seo/record.py --run-dir D --source site_crawl --name crawl --response-file crawl.json
Exit codes: 0 = recorded, 1 = rejected, 3 = cache miss (make the call, then record it).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import resolve  # noqa: E402
import runs  # noqa: E402
import window  # noqa: E402

CACHE_MISS = 3

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


# ------------------------------------------------------------------- cache ---
SERVER_LAG = {"search-console": window.DEFAULT_LAGS["gsc"], "analytics": window.DEFAULT_LAGS["ga4"]}


def _final_window(cap_entry: dict, full_args: dict, today: dt.date | None = None) -> bool:
    """Every date is ISO and ends at least the source's lag ago, so the data can no longer change."""
    ends = [full_args.get("endDate"), full_args.get("compareEndDate")]
    starts = [full_args.get("startDate"), full_args.get("compareStartDate")]
    for r in full_args.get("date_ranges") or []:
        ends.append((r or {}).get("end_date"))
        starts.append((r or {}).get("start_date"))
    try:
        dates = [dt.date.fromisoformat(d) for d in starts + ends if d is not None]
        last = max(dt.date.fromisoformat(d) for d in ends if d is not None)
    except (TypeError, ValueError):
        return False  # relative dates ("28daysAgo") or garbage: never cache as immutable
    today = today or dt.datetime.now(dt.timezone.utc).date()
    return bool(dates) and last <= today - dt.timedelta(days=SERVER_LAG.get(cap_entry.get("server"), 3))


def _ttl_days(cap_entry: dict, full_args: dict) -> float | None:
    """Days a response stays valid: final dated windows forever, live tools per policy, else not cacheable (None)."""
    ttl = (cap_entry.get("policy") or {}).get("cache_ttl_days")
    if ttl is not None:
        return float(ttl) if ttl > 0 else None
    if ((full_args.get("startDate") and full_args.get("endDate")) or full_args.get("date_ranges")) \
            and _final_window(cap_entry, full_args):
        return float("inf")
    return None


def _cacheable_response(parsed) -> bool:
    """Never cache errors or non-JSON text."""
    if not isinstance(parsed, (dict, list)):
        return False
    if isinstance(parsed, dict):
        if parsed.get("isError") or "error" in parsed or set(parsed) == {"text"}:
            return False
    return True


def _cache_path(run_dir: Path, cap: str, full_args: dict) -> Path | None:
    state_p = run_dir / ".run_state.json"
    if not state_p.exists() or not runs.settings().get("cache", True):
        return None
    site = json.loads(state_p.read_text()).get("site")
    if not site:
        return None
    key = hashlib.sha256(json.dumps({"cap": cap, "args": full_args}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
    return runs.cache_dir(site) / cap / f"{key}.json"


def cached(run_dir: Path, cap: str, args: dict, now: dt.datetime | None = None) -> dict | None:
    """The cached entry for this exact call if present and still valid."""
    _, caps, _, _ = resolve.load()
    if cap not in caps:
        raise ValueError(f"unknown capability '{cap}'")
    full = {**(caps[cap].get("args") or {}), **args}
    ttl, path = _ttl_days(caps[cap], full), _cache_path(run_dir, cap, full)
    if ttl is None or path is None or not path.exists():
        return None
    entry = json.loads(path.read_text())
    age = (now or dt.datetime.now(dt.timezone.utc)) - dt.datetime.fromisoformat(entry["stored_at"])
    return entry if age.total_seconds() <= ttl * 86400 else None


def _store(run_dir: Path, cap: str, cap_entry: dict, full_args: dict, parsed) -> None:
    if _ttl_days(cap_entry, full_args) is None or not _cacheable_response(parsed):
        return
    path = _cache_path(run_dir, cap, full_args)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cap": cap, "args": full_args, "response": parsed,
                                "stored_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
                               ensure_ascii=False) + "\n")


def record_from_cache(run_dir: Path, name: str, cap: str, args: dict | None = None,
                      allow_window: str | None = None) -> Path | None:
    """Record the cached response for this call (same guards as a live call); None on a miss."""
    args = args or {}
    hit = cached(run_dir, cap, args)
    if hit is None:
        record(run_dir, name, "{}", cap, args=args, allow_window=allow_window, dry_run=True)  # still enforce the guards
        return None
    return record(run_dir, name, json.dumps(hit["response"], ensure_ascii=False), cap, args=args,
                  allow_window=allow_window, _cached_from=hit["stored_at"])


def record(run_dir: Path, name: str, raw: str, cap: str | None = None, source: str | None = None,
           args: dict | None = None, allow_window: str | None = None, dry_run: bool = False,
           _cached_from: str | None = None) -> Path | None:
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
        if _cached_from:
            entry["cached_from"] = _cached_from
    else:
        entry.update({"source": source, "args": args})
    if dry_run:
        return None

    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / f"{name}.json"
    parsed = _parse_response(raw)
    out.write_text(json.dumps(parsed, ensure_ascii=False, indent=1) + "\n")
    if cap and not _cached_from and "window_exception" not in entry:
        _store(run_dir, cap, c, entry["args"], parsed)
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
    ap.add_argument("--response-file", help="file with the raw response, or '-' for stdin")
    ap.add_argument("--from-cache", action="store_true", help="record the cached response for this call (exit 3 = miss)")
    ap.add_argument("--allow-window", default=None, help="reason for a deliberate off-window call")
    a = ap.parse_args(argv)
    try:
        if a.from_cache:
            if not a.cap:
                raise ValueError("--from-cache needs --cap")
            out = record_from_cache(Path(a.run_dir), a.name, a.cap, json.loads(a.args), a.allow_window)
            if out is None:
                print(f"cache miss for {a.cap} — make the call, then record it with --response-file")
                return CACHE_MISS
            print(f"recorded {out} (from cache)")
            return 0
        if not a.response_file:
            raise ValueError("--response-file is required (or --from-cache)")
        raw = sys.stdin.read() if a.response_file == "-" else Path(a.response_file).read_text()
        out = record(Path(a.run_dir), a.name, raw, a.cap, a.source, json.loads(a.args), a.allow_window)
    except (ValueError, OSError) as e:  # JSONDecodeError is a ValueError
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(f"recorded {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
