#!/usr/bin/env python3
"""Weekly SEO brief (seo-brief): one page from the latest report of every SEO skill.

Builds ``{run_dir}/findings.json`` deterministically:
- **KPIs** — clicks, impressions, CTR and position per Monday–Sunday week, from the
  ``gsc.daily_totals`` response recorded in the brief run (property totals, incl. anonymized queries);
- **Top actions** — the structured actions of every skill's latest completed report (within
  ``brief_max_age_days``), de-duplicated, minus actions logged ``[done]`` in the site history,
  ranked by impact ÷ effort; each marked new or open since the brief that first showed it;
- **Reports** — each skill's latest report and verdict, and which ones are due (``cadence_days``).
Each included report is recorded into the brief run as evidence (source ``skill_run``).

Usage:
    python3 seo/digest.py --site pbservices.ge --run-dir {run_dir} [--top 7]
Exit codes: 0 = findings written, 1 = error.
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
import gsc_metrics  # noqa: E402
import record  # noqa: E402
import runs  # noqa: E402
import site_profile  # noqa: E402

BRIEF = "seo-brief"
STATE = "brief_state.json"
PLANS = HERE / "data-plans"
IMPACT = {"high": 3, "medium": 2, "low": 1}
EFFORT = {"low": 3, "medium": 2, "high": 1}


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(s).lower()).split())


def as_action(a) -> dict:
    return {"action": a, "impact": "medium", "effort": "medium"} if isinstance(a, str) else dict(a)


def action_key(a: dict) -> str:
    return f"{(a.get('page') or '').split('#')[0].rstrip('/')}|{_norm(a.get('keyword') or '')}|{_norm(a['action'])}"


def score(a: dict) -> int:
    return IMPACT.get(a.get("impact"), 2) * EFFORT.get(a.get("effort"), 2)


# ------------------------------------------------------------------- KPIs ---
def weekly_kpis(daily_rows: list[dict], weeks: list[dict]) -> list[dict]:
    """Per Monday–Sunday week: clicks, impressions, CTR, impression-weighted position."""
    out = []
    for w in weeks:
        rows = [r for r in daily_rows if w["startDate"] <= str(r.get("date", ""))[:10] <= w["endDate"]]
        m = gsc_metrics.aggregate(rows, lambda r: "t").get("t")
        out.append({"week": w["startDate"], "days": len(rows),
                    "clicks": round(m["clicks"]) if m else 0, "impressions": round(m["impressions"]) if m else 0,
                    "ctr": round(m["ctr"] * 100, 2) if m else None,
                    "position": round(m["position"], 1) if m and m["impressions"] else None})
    return out


def _pct(new, old):
    return None if not old else round((new - old) / old * 100, 1)


# ---------------------------------------------------------------- collect ---
def _blocked(skill: str, ok) -> list[str]:
    """Servers the skill's plan insists on but that are not configured: such a report can never run, so it is
    'blocked', not merely 'due' (`plan.requires_servers` is the same rule the pipeline enforces)."""
    p = PLANS / f"{skill}.json"
    if not p.exists():
        return []
    try:
        need = json.loads(p.read_text()).get("requires_servers") or {}
    except json.JSONDecodeError:
        return []
    return [srv for srv in need if not ok(srv)]


def latest_reports(site: str, as_of: dt.date, max_age: int, cadence: dict) -> tuple[list[dict], list[dict]]:
    """(reports to include, status of every skill incl. due and blocked ones)."""
    included, status = [], []
    skills = (set(cadence) | {r["skill"] for r in runs.runs(site) if r.get("skill")}) - {BRIEF}
    import pipeline  # local import: one rule for "is this server usable", no cycle at module load
    clients = pipeline.MCPClients()
    try:
        for skill in sorted(skills):
            every = cadence.get(skill)  # None = on demand (never due)
            last = runs.latest(site, skill, as_of=as_of)
            age = (as_of - dt.date.fromisoformat(last["as_of"])).days if last else None
            blocked = _blocked(skill, lambda srv, c=clients: pipeline.server_ok(c, srv))
            if every is not None:
                status.append({"skill": skill, "last_run": last["as_of"] if last else None, "age_days": age,
                               "cadence_days": every, "due": (last is None or age > every) and not blocked,
                               "blocked": blocked})
            if last and age <= max_age:
                f = json.loads((Path(last["path"]) / "findings.json").read_text())
                included.append({"skill": skill, "as_of": last["as_of"], "path": last["path"], "findings": f})
    finally:
        clients.close()
    return included, status


def previous_state(site: str, current: Path) -> dict:
    for r in runs.runs(site, BRIEF):
        p = Path(r["path"])
        if p.resolve() != current.resolve() and (p / STATE).exists():
            return json.loads((p / STATE).read_text())
    return {"first_seen": {}, "top": []}


def done_texts(site: str) -> list[str]:
    return [_norm(m.group(3)) for ln in site_profile.read_history(site, "done").splitlines()
            if (m := site_profile.HISTORY_LINE_RE.match(ln))]


def rank_actions(reports: list[dict], done: list[str]) -> list[dict]:
    merged: dict = {}
    for rep in sorted(reports, key=lambda r: r["as_of"], reverse=True):  # newest wording wins
        for raw in rep["findings"].get("actions") or []:
            a = as_action(raw)
            if not a.get("action", "").strip():
                continue
            n = _norm(a["action"])
            if any(n == d or (len(n) > 15 and n in d) for d in done):
                continue
            k = action_key(a)
            m = merged.setdefault(k, {**a, "sources": []})
            m["sources"].append(f"{rep['skill']} {rep['as_of']}")
    return sorted(merged.values(), key=lambda a: (-score(a), -(a.get("est_clicks") or 0), -len(a["sources"]), a["action"]))


# ------------------------------------------------------------------ build ---
def build(site: str, run_dir: Path, top: int = 7) -> dict:
    state = json.loads((run_dir / ".run_state.json").read_text())
    win = state["window"]
    as_of = dt.date.fromisoformat(win["as_of"])
    cfg = runs.settings()
    unavailable, sections = [], []
    changes = {}

    calls = json.loads((run_dir / "context.json").read_text()).get("calls", [])
    totals = next((c for c in calls if c.get("cap") == "gsc.daily_totals"), None)
    kpis = []
    if totals and win.get("weeks"):
        kpis = weekly_kpis(gsc_metrics.load_rows(run_dir / totals["file"], ["date"]), win["weeks"])
        last, prev = kpis[-1], kpis[-2] if len(kpis) > 1 else None
        if prev:
            changes = {"clicks_pct": _pct(last["clicks"], prev["clicks"]),
                       "impressions_pct": _pct(last["impressions"], prev["impressions"])}
        body = "Search Console property totals (all searches, incl. anonymized), Monday–Sunday weeks; latest week last."
        if prev:
            body += (f" Latest week vs previous: clicks {_pct(last['clicks'], prev['clicks']):+.1f}%, "
                     f"impressions {_pct(last['impressions'], prev['impressions']):+.1f}%."
                     if prev["clicks"] and prev["impressions"] else "")
        sections.append({"heading": "KPIs (last 8 weeks)", "body": body, "table": kpis})
    else:
        unavailable.append({"source": "search-console (gsc.daily_totals)", "affects": "weekly KPIs"})

    reports, status = latest_reports(site, as_of, int(cfg.get("brief_max_age_days", 45)), cfg.get("cadence_days", {}))
    for rep in reports:
        record.record(run_dir, f"run_{rep['skill'].replace('-', '_')}", json.dumps(rep["findings"], ensure_ascii=False),
                      source="skill_run", args={"path": rep["path"], "as_of": rep["as_of"]})

    ranked = rank_actions(reports, done_texts(site))
    prev_state = previous_state(site, run_dir)
    open_keys = [action_key(a) for a in ranked]
    seen = prev_state.get("first_seen", {})
    first_seen = {k: seen.get(k, win["as_of"]) for k in open_keys}  # closed actions drop out
    rows = []
    for i, a in enumerate(ranked[:top], 1):
        since = first_seen[action_key(a)]
        rows.append({"#": i, "action": a["action"], "impact": a["impact"], "effort": a["effort"],
                     "about": a.get("page") or a.get("keyword") or "", "from": ", ".join(a["sources"]),
                     "status": "new" if since == win["as_of"] else f"open since {since}"})
    top_keys = [action_key(a) for a in ranked[:top]]
    closed = [k for k in prev_state.get("top", []) if k not in set(open_keys)]
    if rows:
        sections.append({"heading": "Top actions", "table": rows,
                         "body": (f"{len(ranked)} open actions across {len(reports)} reports, ranked by impact ÷ effort; "
                                  f"top {len(rows)} shown. {sum(r['status'] == 'new' for r in rows)} new since the last brief"
                                  + (f"; {len(closed)} from the last brief no longer flagged (done or resolved)." if closed else "."))})
    else:
        sections.append({"heading": "Top actions", "body": "No open actions in the reports of the last "
                         f"{cfg.get('brief_max_age_days', 45)} days."})

    due = [s for s in status if s["due"]]
    blocked = [s for s in status if s["blocked"]]
    rep_rows = [{"report": r["skill"], "date": r["as_of"],
                 "verdict": (r["findings"].get("verdict", "")[:160] + ("…" if len(r["findings"].get("verdict", "")) > 160 else ""))}
                for r in reports]
    sections.append({"heading": "Reports", "window": {"note": "each report keeps its own window; see its date"},
                     "body": (f"{len(reports)} reports included. Due now: "
                              + (", ".join(f"{s['skill']} ({'never run' if s['last_run'] is None else str(s['age_days']) + ' days old'})"
                                           for s in due) if due else "none") + "."
                              + (" Cannot run (missing source): "
                                 + ", ".join(f"{s['skill']} (needs {', '.join(s['blocked'])})" for s in blocked)
                                 + " — connect the source or drop the report from the cadence." if blocked else "")),
                     **({"table": rep_rows} if rep_rows else {})})
    if not reports:
        unavailable.append({"source": "SEO reports", "affects": "actions (no completed report in the last "
                                                                f"{cfg.get('brief_max_age_days', 45)} days)"})

    parts = []
    if kpis:
        last, prev = kpis[-1], (kpis[-2] if len(kpis) > 1 else None)
        line = f"Week of {last['week']}: {last['clicks']} clicks"
        if prev and prev["clicks"]:
            line += f" ({_pct(last['clicks'], prev['clicks']):+.1f}% vs previous week)"
        parts.append(line)
    parts.append(f"{len(ranked)} open actions ({sum(r['status'] == 'new' for r in rows)} new in the top {len(rows)})")
    if due:
        parts.append(f"{len(due)} reports due")
    if blocked:
        parts.append(f"{len(blocked)} cannot run (missing source)")
    verdict = "; ".join(parts) + "."
    findings = {"skill": BRIEF, "as_of": win["as_of"], "window": win, "verdict": verdict, "sections": sections,
                "actions": [{x: a[x] for x in ("action", "impact", "effort", "page", "keyword", "category", "why", "est_clicks")
                             if x in a} for a in ranked[:top]]}
    if unavailable:
        findings["unavailable"] = unavailable
    numbers = {  # everything the brief states, so seo/report/number_check.py can trace it
        "kpis": kpis, "latest_week_change_pct": changes,
        "actions": {"open": len(ranked), "in_top": len(rows),
                    "new_in_top": sum(r["status"] == "new" for r in rows), "closed_since_last": len(closed)},
        "reports": {"included": len(reports),
                    "due": [{"skill": s_["skill"], "age_days": s_["age_days"]} for s_ in due],
                    "blocked": [{"skill": s_["skill"], "needs": s_["blocked"]} for s_ in blocked]},
    }
    computed = run_dir / "computed"
    computed.mkdir(exist_ok=True)
    (computed / "brief.json").write_text(json.dumps(numbers, ensure_ascii=False, indent=1) + "\n")
    (run_dir / STATE).write_text(json.dumps({"first_seen": first_seen, "top": top_keys}, ensure_ascii=False, indent=1) + "\n")
    (run_dir / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--top", type=int, default=7)
    ap.add_argument("--json", action="store_true", help="print the brief's numbers as JSON (pipeline computed output)")
    a = ap.parse_args(argv)
    try:
        f = build(a.site, Path(a.run_dir), a.top)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    if a.json:  # the pipeline stores this as computed/brief.json — identical to what build() wrote
        print((Path(a.run_dir) / "computed" / "brief.json").read_text(), end="")
    else:
        print(f"wrote {a.run_dir}/findings.json — {f['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
