#!/usr/bin/env python3
"""Deterministic paid-vs-organic overlap (Google Ads search terms × GSC queries).

Buckets (domain-knowledge.md → Paid vs organic):
- double_paying     — paid spend on a term ranking ≤ 3 organically
- defend_check      — double_paying terms where our ad's absolute-top share is < 50%:
                      competitors may be bidding; needs a manual SERP check before cutting
- paid_only_winners — terms converting in Ads with no organic ranking ≤ 20 (content roadmap)
- organic_only      — organic terms (≥ min clicks) with no paid coverage (scale candidates)
Money is in the account currency (cost_micros / 1,000,000). Savings are an **estimate**.

Usage:
    python3 seo/ads_metrics.py overlap --ads F --query F [--currency GEL] [--retention 0.5-0.7]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gsc_metrics  # noqa: E402


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def ads_rows(payload) -> list[dict]:
    """Normalise google-ads search rows (nested or dotted keys) to term/cost/clicks/conversions/top%."""
    payload = gsc_metrics._unwrap(payload)
    rows = payload if isinstance(payload, list) else (payload.get("results") or payload.get("rows") or payload.get("result") or []) if isinstance(payload, dict) else []
    out = []
    for r in rows:
        f = _flatten(r) if isinstance(r, dict) else {}
        pick = lambda *names: next((f[n] for n in names if n in f), None)  # noqa: E731
        term = pick("search_term_view.search_term", "searchTermView.searchTerm", "search_term")
        if term is None:
            continue
        cost = pick("metrics.cost_micros", "metrics.costMicros", "cost_micros")
        out.append({"term": str(term),
                    "cost": round(gsc_metrics._num(cost) / 1_000_000, 2),
                    "clicks": gsc_metrics._num(pick("metrics.clicks", "clicks")),
                    "conversions": gsc_metrics._num(pick("metrics.conversions", "conversions")),
                    "abs_top_share": gsc_metrics._num(pick("metrics.absolute_top_impression_percentage",
                                                           "metrics.absoluteTopImpressionPercentage"))})
    return out


def overlap(ads: list[dict], query_rows: list[dict], retention: tuple[float, float] = (0.5, 0.7),
            min_organic_clicks: float = 10) -> dict:
    org = {gsc_metrics.norm_text(q): m for q, m in gsc_metrics.aggregate(query_rows, lambda r: r["query"]).items()}
    paid: dict[str, dict] = {}
    for a in ads:
        p = paid.setdefault(gsc_metrics.norm_text(a["term"]), {"term": a["term"], "cost": 0.0, "clicks": 0.0, "conversions": 0.0, "_top": []})
        p["cost"] += a["cost"]
        p["clicks"] += a["clicks"]
        p["conversions"] += a["conversions"]
        p["_top"].append(a["abs_top_share"])
    out = {"double_paying": [], "defend_check": [], "paid_only_winners": [], "organic_only": []}
    for k, p in paid.items():
        top = max(p.pop("_top") or [0])
        o = org.get(k)
        row = {**{x: round(p[x], 2) for x in ("cost", "clicks", "conversions")}, "term": p["term"],
               "organic_position": round(o["position"], 2) if o else None, "organic_clicks": o["clicks"] if o else 0,
               "ad_abs_top_share": top}
        if o and o["position"] <= 3 and p["cost"] > 0:
            out["double_paying"].append(row)
            if top < 0.5:
                out["defend_check"].append(row)
        elif p["conversions"] > 0 and (not o or o["position"] > 20):
            out["paid_only_winners"].append(row)
    for k, o in org.items():
        if k not in paid and o["clicks"] >= min_organic_clicks:
            out["organic_only"].append({"term": k, "organic_position": round(o["position"], 2), "organic_clicks": o["clicks"]})
    for b in out.values():
        b.sort(key=lambda r: -(r.get("cost") or r.get("organic_clicks") or 0))
    spend = round(sum(r["cost"] for r in out["double_paying"]), 2)
    lost = [round(sum(r["clicks"] for r in out["double_paying"]) * (1 - x), 1) for x in retention]
    out["summary"] = {"double_paying_spend": spend,
                      "est_paid_clicks_not_recaptured": {"if_retention_" + str(retention[1]): lost[1],
                                                         "if_retention_" + str(retention[0]): lost[0]},
                      "label": "estimate — confirm with a holdout/pause test before cutting spend",
                      "retention_assumption": "heuristic share of paid clicks organic would recapture"}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["overlap"])
    ap.add_argument("--ads", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--currency", default=None, help="account currency code (from customer.currency_code)")
    ap.add_argument("--retention", default="0.5-0.7", help="heuristic recapture range, e.g. 0.5-0.7")
    a = ap.parse_args(argv)
    try:
        lo, hi = (float(x) for x in a.retention.split("-"))
        res = overlap(ads_rows(json.loads(Path(a.ads).read_text())), gsc_metrics.load_rows(a.query, ["query"]), (lo, hi))
        res["summary"]["currency"] = a.currency or "account currency (pass --currency)"
    except (ValueError, FileNotFoundError, KeyError, TypeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
