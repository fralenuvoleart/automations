#!/usr/bin/env python3
"""GA4 analysis for the SEO skills, classified with the site rules (``seo/rules.py``).

Input: a recorded ``ga4.landing_source`` response (landing page × source/medium; sessions,
engaged sessions, key events). With two ``date_ranges`` in one call, GA4 adds a ``dateRange``
dimension: ``date_range_0`` is read as current, ``date_range_1`` as previous.

Commands (all print JSON):
    breakdown --site D --ga4 F [--prev F] --by channel|page_tag|language [--organic]
    reconcile --site D --ga4 F --gsc-totals F [--ga4-prev F --gsc-totals-prev F]
        # Search Console clicks vs GA4 organic sessions + "(not set)" landing-page share
    top-pages --site D --ga4 F [--limit N]          # landing pages by sessions (absolute URLs)
    misses    --site D --ga4 F --gsc-pages F [--limit N]   # top organic pages with no sessions in the GA4 rows
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Heuristic flags (override per site in the profile `thresholds`).
DEFAULTS = {
    "reconcile_divergence_pts": 20.0,  # GSC clicks vs GA4 organic sessions change differs by > N points
    "not_set_share_max": 0.05,         # "(not set)" landing page above 5 % of organic sessions
}
METRICS = ("sessions", "engagedSessions", "keyEvents")
NOT_SET = "(not set)"


def _value(v, field: str) -> float | None:
    """A metric value as GA4 sent it: blank or absent → None (not reported), unreadable → error (A2)."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ValueError(f"GA4 row has an unreadable '{field}' value: {v!r}") from None


def parse_rows(payload) -> list[dict]:
    """GA4 run_report (camelCase or snake_case, MCP-wrapped or raw) → [{dimension: value, metric: float}]."""
    import gsc_metrics
    payload = gsc_metrics._unwrap(payload)
    if isinstance(payload, list):
        return [{k: (_value(v, k) if k in METRICS else v) for k, v in r.items()} for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        raise ValueError("unrecognised GA4 response shape")
    dh = payload.get("dimension_headers") or payload.get("dimensionHeaders") or []
    mh = payload.get("metric_headers") or payload.get("metricHeaders") or []
    dims, mets = [h.get("name") for h in dh], [h.get("name") for h in mh]
    out = []
    for r in payload.get("rows") or []:
        dv = r.get("dimension_values") or r.get("dimensionValues") or []
        mv = r.get("metric_values") or r.get("metricValues") or []
        row = {d: v.get("value") for d, v in zip(dims, dv)}
        row.update({m: _value(v.get("value"), m) for m, v in zip(mets, mv)})
        out.append(row)
    if out and not dims:
        raise ValueError("GA4 response has rows but no dimension headers")
    return out


def load_rows(path: str | Path) -> list[dict]:
    return parse_rows(json.loads(Path(path).read_text()))


def split_ranges(rows: list[dict]) -> tuple[list[dict], list[dict] | None]:
    """(current, previous) from one call with two date_ranges; (rows, None) otherwise."""
    if not rows or "dateRange" not in rows[0]:
        return rows, None
    return ([r for r in rows if r["dateRange"] == "date_range_0"],
            [r for r in rows if r["dateRange"] == "date_range_1"])


def _metric(r: dict, m: str) -> float | None:
    """A metric the row carries; None when absent — an absent metric is not a measured 0 (A2)."""
    v = r.get(m)
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _agg(rows: list[dict], keyf) -> dict:
    acc: dict = {}
    carried: dict = {}
    for r in rows:
        k = keyf(r)
        a = acc.setdefault(k, dict.fromkeys(METRICS, 0.0))
        c = carried.setdefault(k, dict.fromkeys(METRICS, False))
        for m in METRICS:
            v = _metric(r, m)
            if v is None:
                continue
            c[m] = True
            a[m] += v
    for k, a in acc.items():
        for m in METRICS:
            if not carried[k][m]:
                a[m] = None  # no row carried this metric: untracked, not a measured zero
        a["engagementRate"] = (round(a["engagedSessions"] / a["sessions"], 3)
                               if a["sessions"] and a["engagedSessions"] is not None else None)
    return acc


def _pct(new: float | None, old: float | None) -> float | None:
    return None if not old or new is None else round((new - old) / old * 100, 1)


def breakdown(rules, rows: list[dict], by: str, prev_rows: list[dict] | None = None,
              organic_only: bool = False) -> dict:
    """Sessions, engaged sessions, engagement rate and key events per channel, page type or language."""
    organic = rules.data["channels"]["organic_channel"]
    keep = (lambda r: rules.channel(r["sessionSourceMedium"]) == organic) if organic_only else (lambda r: True)
    keyf, order = {
        "channel": (lambda r: rules.channel(r["sessionSourceMedium"]),
                    [c["channel"] for c in rules.data["channels"]["rules"]] + [rules.data["channels"]["default"]]),
        "page_tag": (lambda r: rules.page_tag(r["landingPage"]), rules.sections()),
        "language": (lambda r: rules.page_language(r["landingPage"]), rules.languages()),
    }[by]
    cur = _agg([r for r in rows if keep(r)], keyf)
    prev = _agg([r for r in prev_rows if keep(r)], keyf) if prev_rows is not None else None
    names = [n for n in order if n in cur or (prev and n in prev)]
    names += sorted(n for n in set(cur) | set(prev or {}) if n not in names)

    # a metric is tracked when the response carries it; key events are *recorded* only when the property
    # logged at least one in either period — an all-zero column usually means none are set up in GA4
    every = list(rows) + list(prev_rows or [])
    tracked = {m: any(r.get(m) is not None for r in every) for m in METRICS}
    recorded = tracked["keyEvents"] and sum(r.get("keyEvents") or 0.0 for r in every) > 0

    def line(name, c, p):
        # a group with no rows had no sessions (GA4 omits empty rows): 0 where the metric is tracked
        c = c or {**{m: (0.0 if tracked[m] else None) for m in METRICS}, "engagementRate": None}
        row = {by: name, **{k: (round(v, 1) if isinstance(v, float) and k in METRICS else v) for k, v in c.items()}}
        if prev is not None:
            row["prev_sessions"] = (None if p["sessions"] is None else round(p["sessions"], 1)) if p else 0
            row["sessions_change_pct"] = _pct(c["sessions"], p["sessions"]) if p else None
            row["prev_engagementRate"] = p["engagementRate"] if p else None
        return row

    tot_c = _agg([r for r in rows if keep(r)], lambda r: "t").get("t")
    tot_p = _agg([r for r in prev_rows if keep(r)], lambda r: "t").get("t") if prev_rows is not None else None
    out_rows = [line(n, cur.get(n), (prev or {}).get(n)) for n in names]
    total_sessions = (tot_c or {}).get("sessions") or 0
    for row in out_rows:
        row["session_share"] = (round(row["sessions"] / total_sessions, 4)
                                if total_sessions and row["sessions"] is not None else None)
        row["key_event_rate"] = (round(row["keyEvents"] / row["sessions"], 4)
                                 if recorded and row.get("sessions") and row.get("keyEvents") is not None else None)
    out = {"by": by, "organic_only": organic_only, "rows": out_rows, "total": line("Total", tot_c, tot_p),
           "key_events_tracked": tracked["keyEvents"], "key_events_recorded": recorded}
    if not recorded:  # never a confident 0 %: say why there is no rate
        out["key_events_note"] = ("the report has no key-event metric" if not tracked["keyEvents"] else
                                  "no key event recorded in either period — check that key events are set up in GA4; "
                                  "key-event rates are not reported")
    if by == "channel":  # headline of the AI sections: AI sessions ÷ organic sessions (a lower bound)
        ai, org = rules.data["channels"]["ai_channel"], organic

        def share(agg):
            a = (agg or {}).get(ai, {}).get("sessions") or 0
            o = (agg or {}).get(org, {}).get("sessions") or 0
            return round(a / o, 4) if o else None
        out["ai_share_of_organic"] = {"current": share(cur), "previous": share(prev) if prev is not None else None,
                                      "label": "lower bound — some AI visits arrive as direct or unlisted referrers"}
    return out


def reconcile(rules, ga4_rows: list[dict], gsc_totals: list[dict], ga4_prev: list[dict] | None = None,
              gsc_prev: list[dict] | None = None, thr: dict | None = None) -> dict:
    """Search Console clicks vs GA4 organic sessions (compare trends, not totals) + "(not set)" landing share."""
    thr = {**DEFAULTS, **(thr or {})}
    organic = rules.data["channels"]["organic_channel"]

    def side(g4, gsc):
        org = [r for r in g4 if rules.channel(r["sessionSourceMedium"]) == organic]
        sess = sum(_metric(r, "sessions") or 0.0 for r in org)
        ns = [r for r in org if str(r.get("landingPage")) == NOT_SET]
        ns_sess = sum(_metric(r, "sessions") or 0.0 for r in ns)
        ns_eng = sum(_metric(r, "engagedSessions") or 0.0 for r in ns)
        clicks = sum(r["clicks"] for r in gsc)
        return {"gsc_clicks": round(clicks, 1), "ga4_organic_sessions": round(sess, 1),
                "clicks_per_session": round(clicks / sess, 2) if sess else None,
                "not_set_sessions": round(ns_sess, 1), "not_set_share": round(ns_sess / sess, 3) if sess else None,
                "not_set_engagement_rate": round(ns_eng / ns_sess, 3) if ns_sess else None}

    cur = side(ga4_rows, gsc_totals)
    out = {"current": cur, "flags": [], "thresholds": {k: thr[k] for k in DEFAULTS}, "label": "heuristic thresholds",
           "note": ("Search Console counts Google clicks only; GA4 counts sessions from every search engine and can "
                    "split one visit into two sessions, so totals never match — compare the trends.")}
    if (cur["not_set_share"] or 0) > thr["not_set_share_max"]:
        out["flags"].append(f"'(not set)' landing page is {cur['not_set_share']:.0%} of organic sessions "
                            f"(engagement {cur['not_set_engagement_rate']}) — check the GA4 tag (sessions without a page_view)")
    if ga4_prev is not None and gsc_prev is not None:
        prev = side(ga4_prev, gsc_prev)
        out["previous"] = prev
        gc, sc = _pct(cur["gsc_clicks"], prev["gsc_clicks"]), _pct(cur["ga4_organic_sessions"], prev["ga4_organic_sessions"])
        out["gsc_clicks_change_pct"], out["ga4_organic_sessions_change_pct"] = gc, sc
        if gc is not None and sc is not None and abs(gc - sc) > thr["reconcile_divergence_pts"]:
            out["flags"].append(f"trends diverge: Search Console clicks {gc:+.1f}% vs GA4 organic sessions {sc:+.1f}% — "
                                "check tracking/consent changes or a non-Google engine before reading either trend")
    return out


def _landing(r: dict) -> str | None:
    return r.get("landingPage") or r.get("landingPagePlusQueryString")


def top_pages(rules, rows: list[dict], limit: int = 3) -> list[dict]:
    """Landing pages by sessions (absolute, cleaned URLs; "(not set)" skipped)."""
    agg = _agg([r for r in rows if _landing(r) and _landing(r) != NOT_SET], lambda r: rules.clean(_landing(r)))
    return [{"page": p, "sessions": round(m["sessions"] or 0.0, 1),
             "keyEvents": None if m["keyEvents"] is None else round(m["keyEvents"], 1)}
            for p, m in sorted(agg.items(), key=lambda kv: (-(kv[1]["sessions"] or 0.0), kv[0]))[:limit]]


def misses(rules, ga4_rows: list[dict], gsc_page_rows: list[dict], limit: int = 5) -> list[dict]:
    """Pages with the most organic clicks that got no sessions in the GA4 rows (e.g. no AI referrals)."""
    import gsc_metrics
    seen = {rules.clean(_landing(r)) for r in ga4_rows if _landing(r) and (_metric(r, "sessions") or 0) > 0}
    tops = gsc_metrics.top_pages(gsc_page_rows, "clicks", 10 ** 6)
    return [p for p in tops if rules.clean(p["page"]) not in seen][:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["breakdown", "reconcile", "top-pages", "misses"])
    ap.add_argument("--gsc-pages", dest="gsc_pages")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--site", required=True)
    ap.add_argument("--ga4", required=True)
    ap.add_argument("--prev", "--ga4-prev", dest="prev")
    ap.add_argument("--by", choices=["channel", "page_tag", "language"])
    ap.add_argument("--organic", action="store_true", help="organic-search sessions only (rules' organic channel)")
    ap.add_argument("--gsc-totals", dest="gsc_totals")
    ap.add_argument("--gsc-totals-prev", dest="gsc_totals_prev")
    a = ap.parse_args(argv)
    try:
        import gsc_metrics
        import rules
        import site_profile
        r = rules.load(a.site)
        cur, prev = split_ranges(load_rows(a.ga4))
        if a.prev:
            prev = load_rows(a.prev)
        if a.command == "top-pages":
            res = {"pages": top_pages(r, cur, a.limit or 3)}
        elif a.command == "misses":
            if not a.gsc_pages:
                raise ValueError("--gsc-pages is required for misses")
            res = {"pages": misses(r, cur, gsc_metrics.load_rows(a.gsc_pages, ["page"]), a.limit or 5)}
        elif a.command == "breakdown":
            if not a.by:
                raise ValueError("--by is required for breakdown")
            res = breakdown(r, cur, a.by, prev, a.organic)
        else:
            if not a.gsc_totals:
                raise ValueError("--gsc-totals is required for reconcile (gsc.daily_totals rows)")
            gp = gsc_metrics.load_rows(a.gsc_totals_prev, ["date"]) if a.gsc_totals_prev else None
            res = reconcile(r, cur, gsc_metrics.load_rows(a.gsc_totals, ["date"]), prev if gp is not None else None,
                            gp, site_profile.thresholds(a.site))
    except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
