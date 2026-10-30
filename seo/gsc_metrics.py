#!/usr/bin/env python3
"""Deterministic Search Console analytics for the SEO skills.

The skills pull raw rows with explicit windows (``gsc.query``, ``gsc.page``,
``gsc.page_query``, ``gsc.daily_totals`` — recorded with ``seo/record.py``) and
compute every finding here, so the numbers are reproducible and the thresholds
are explicit. Replaces the opaque ``seo_audit`` tool (which ignores the window).

Brand and page language come from the site's rules (``seo/rules.py``).
Rules baked in (see ``seo/references/domain-knowledge.md``):
- page metrics come from ``page`` rows (they include anonymized-query clicks);
  query metrics from ``query`` rows; ``query × page`` only for attribution;
- positions are aggregated impression-weighted; CTR = clicks / impressions;
- a pull that returned exactly the row limit is **truncated**: "new"/"lost"
  findings are then reported as "beyond the row cutoff", not as movements.

Commands (all print JSON; thresholds come from the site profile when --site is given):
    truncation  --file F
    anonymized  --totals F --rows F
    curve       --query F [--curve-query F12] [--site D]   # F12 = the site's last 12 months of query rows
    benchmark   [--check]                        # the fallback CTR benchmark's source and age (exit 2 = stale)
    movers      --cur F --prev F [--site D]
    striking    --query F [--site D]
    low-ctr     --query F [--curve-query F12] [--site D]
    cannibalization --page-query F [--site D]
    decay       --cur F --prev F [--site D]
    brand-split --cur F [--prev F] [--totals-cur F --totals-prev F] --site D
    value       --planner F --query F [--curve-query F12] [--target N] [--site D]
    topic       --page-query F | --query F  --terms "term1,term2"
    unseen      --page F --urls F [--limit N]    # listed URLs (e.g. sitemap) with zero impressions in page rows
    top-pages   --page F [--by clicks|impressions] [--limit N]
    inspection  --inspect F [F …]                # URL Inspection results → counts and shares per coverage state
    totals      --cur F [--prev F]               # period totals (clicks, impressions, CTR, position) and change
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROW_LIMIT = 25000
METRICS = ("clicks", "impressions", "ctr", "position")
DEFAULTS = {
    "min_impressions": 50,          # a row must have this many impressions to be judged
    "mover_min_delta": 2.0,         # positions moved to count as a winner/loser
    "striking_min": 8.0,
    "striking_max": 20.0,
    "low_ctr_max_position": 5.0,
    "low_ctr_ratio": 0.5,           # flag CTR below 50% of the expected CTR for its position
    "cannibal_min_share": 0.10,     # each competing page holds ≥10% of the query's impressions
    "decay_pct": 30.0,              # clicks down ≥30% => declining page
    "pos_drop": 1.0,                # avg position worse by ≥1.0 => ranking loss
    "imp_drop_pct": 20.0,           # impressions down ≥20% (position held) => demand drop
    "value_target_position": 3,
    "curve_min_impressions": 500,   # a site CTR bucket needs this many impressions to be trusted
}
# Expected CTR by position, in order: the site's own non-brand data for this run's window → its own
# last 12 months (--curve-query) → a dated post-AI-Overviews benchmark (config/ctr-benchmark.json).
BENCHMARK_FILE = HERE / "config" / "ctr-benchmark.json"


def load_benchmark(path: Path | None = None) -> dict:
    b = json.loads((path or BENCHMARK_FILE).read_text())
    for k in ("source", "published", "max_age_months", "positions"):
        if k not in b:
            raise ValueError(f"ctr-benchmark.json: missing '{k}'")
    for pos, v in b["positions"].items():
        if not (pos.isdigit() and isinstance(v, (int, float)) and 0 < v < 1):
            raise ValueError(f"ctr-benchmark.json: bad position entry {pos}: {v}")
    return b


def benchmark_status(b: dict, today=None) -> dict:
    """Source, age in months since publication and whether it is past max_age_months (stale)."""
    import datetime as dt
    today = today or dt.datetime.now(dt.timezone.utc).date()
    y, m = (int(x) for x in b["published"].split("-")[:2])
    age = (today.year - y) * 12 + today.month - m
    return {"source": b["source"], "published": b["published"], "age_months": age,
            "stale": age > int(b["max_age_months"]), "max_age_months": b["max_age_months"]}


# ------------------------------------------------------------------ parsing ---
def _unwrap(payload):
    """Accept raw API JSON, MCP content wrappers, FastMCP {"result": X}, or text-wrapped JSON."""
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return _unwrap(payload["result"])
    if isinstance(payload, dict) and isinstance(payload.get("content"), list):
        texts = [c.get("text", "") for c in payload["content"] if isinstance(c, dict)]
        try:
            return _unwrap(json.loads("".join(texts)))
        except json.JSONDecodeError:
            return payload
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        try:
            return _unwrap(json.loads(payload["text"]))
        except json.JSONDecodeError:
            return payload
    return payload


def _num(v) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if s.endswith("%"):
            return float(s[:-1]) / 100.0
        return float(s)
    return float(v)


def parse_rows(payload, dims: list[str]) -> list[dict]:
    """Normalise a GSC response into [{<dim>: value, clicks, impressions, ctr, position}]."""
    payload = _unwrap(payload)
    rows = None
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("rows", "data", "results", "items"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        if rows is None and not payload:
            rows = []
    if rows is None:
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        raise ValueError(f"unrecognised GSC response shape (top-level: {keys})")
    out = []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError(f"unrecognised GSC row: {r!r}")
        row = {}
        if isinstance(r.get("keys"), list):
            if len(r["keys"]) != len(dims):
                raise ValueError(f"row has {len(r['keys'])} keys but dims are {dims}")
            row.update(dict(zip(dims, r["keys"])))
        else:
            for d in dims:
                if d not in r:
                    raise ValueError(f"row lacks dimension '{d}': {sorted(r)}")
                row[d] = r[d]
        clicks, imps = _num(r.get("clicks")), _num(r.get("impressions"))
        ctr = r.get("ctr")
        ctr = (clicks / imps if imps else 0.0) if ctr in (None, "") else _num(ctr)
        if ctr > 1:
            ctr /= 100.0
        row.update({"clicks": clicks, "impressions": imps, "ctr": ctr, "position": _num(r.get("position"))})
        out.append(row)
    return out


def load_rows(path: str | Path, default_dims: list[str]) -> list[dict]:
    """Load a recorded response; dimensions come from context.json when recorded with record.py."""
    p = Path(path)
    dims = default_dims
    ctx = p.parent.parent / "context.json"
    if ctx.exists():
        try:
            for c in json.loads(ctx.read_text()).get("calls", []):
                if c.get("file") == f"{p.parent.name}/{p.name}" and c.get("args", {}).get("dimensions"):
                    dims = c["args"]["dimensions"]
        except (json.JSONDecodeError, AttributeError):
            pass
    return parse_rows(json.loads(p.read_text()), dims)


def is_truncated(rows: list[dict], limit: int = ROW_LIMIT) -> bool:
    return len(rows) >= limit


# -------------------------------------------------------------- aggregation ---
def aggregate(rows: list[dict], key) -> dict:
    """Sum clicks/impressions per key; impression-weighted position; CTR recomputed."""
    acc: dict = {}
    for r in rows:
        k = key(r)
        a = acc.setdefault(k, {"clicks": 0.0, "impressions": 0.0, "_pos": 0.0})
        a["clicks"] += r["clicks"]
        a["impressions"] += r["impressions"]
        a["_pos"] += r["position"] * r["impressions"]
    for a in acc.values():
        imp = a["impressions"]
        a["ctr"] = a["clicks"] / imp if imp else 0.0
        a["position"] = a.pop("_pos") / imp if imp else 0.0
    return acc


def _pct(new: float, old: float) -> float | None:
    return None if old == 0 else round((new - old) / old * 100.0, 1)


def _r(m: dict) -> dict:
    return {"clicks": round(m["clicks"], 1), "impressions": round(m["impressions"], 1),
            "ctr": round(m["ctr"], 4), "position": round(m["position"], 2)}


# ---------------------------------------------------------------- normalise ---
def norm_text(s: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", str(s).casefold()).split())


# ----------------------------------------------------------------- analyses ---
def ctr_curve(query_rows: list[dict], is_brand=None, thr: dict | None = None,
              longer_rows: list[dict] | None = None, benchmark: dict | None = None) -> dict:
    """Expected non-brand CTR per position bucket (``is_brand``: rules predicate).

    Each bucket comes from the first source with ≥ ``curve_min_impressions``: this run's rows
    (``site``), the site's own last 12 months (``site_12m``, ``longer_rows``), else the dated benchmark
    (``benchmark``, positions it covers). Buckets none of them fill are left out ("insufficient data").
    """
    thr = {**DEFAULTS, **(thr or {})}

    def bucket(r):
        p = r["position"]
        return str(max(1, round(p))) if p < 10.5 else ("11-20" if p <= 20.5 else "21+")

    curve = {}
    for label, rows in (("site", query_rows), ("site_12m", longer_rows or [])):
        rows = [r for r in rows if not (is_brand and is_brand(r["query"]))]
        for b, m in aggregate(rows, bucket).items():
            if b not in curve and m["impressions"] >= thr["curve_min_impressions"]:
                curve[b] = {"ctr": round(m["ctr"], 4), "impressions": round(m["impressions"]), "source": label}
    if benchmark is None:
        try:
            benchmark = load_benchmark()
        except (OSError, ValueError):
            benchmark = {"positions": {}}
    for pos, ctr in (benchmark.get("positions") or {}).items():
        curve.setdefault(str(pos), {"ctr": ctr, "impressions": 0, "source": "benchmark"})
    order = {"11-20": 11, "21+": 21}
    return dict(sorted(curve.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else order[kv[0]]))


def curve_basis(curve: dict, benchmark: dict | None = None, longer: bool = False) -> dict:
    """Which source each bucket came from, plus the benchmark's provenance when it was used."""
    used = sorted({e["source"] for e in curve.values()})
    out = {"sources": used, "buckets_by_source": {s: [b for b, e in curve.items() if e["source"] == s] for s in used},
           "site_12m_supplied": longer}
    if "benchmark" in used:
        try:
            st = benchmark_status(benchmark or load_benchmark())
        except (OSError, ValueError, KeyError):
            st = {"source": "unknown"}
        out["benchmark"] = {**st, "label": "heuristic — external post-AI-Overviews study, not this site's data"}
    return out


def expected_ctr(position: float, curve: dict) -> tuple[float | None, str]:
    b = str(max(1, round(position))) if position < 10.5 else ("11-20" if position <= 20.5 else "21+")
    e = curve.get(b)
    return (e["ctr"], e["source"]) if e else (None, "insufficient data")


def movers(cur_rows: list[dict], prev_rows: list[dict], thr: dict | None = None) -> dict:
    thr = {**DEFAULTS, **(thr or {})}
    cur = aggregate(cur_rows, lambda r: r["query"])
    prev = aggregate(prev_rows, lambda r: r["query"])
    cur_trunc, prev_trunc = is_truncated(cur_rows), is_truncated(prev_rows)
    out = {"winners": [], "losers": [], "new": [], "lost": [], "beyond_row_cutoff": []}
    for q in sorted(set(cur) | set(prev)):
        c, p = cur.get(q), prev.get(q)
        if c and p:
            if max(c["impressions"], p["impressions"]) < thr["min_impressions"]:
                continue
            d = p["position"] - c["position"]  # positive = improved
            row = {"query": q, "position_before": round(p["position"], 2), "position_after": round(c["position"], 2),
                   "position_delta": round(d, 2), "clicks_before": p["clicks"], "clicks_after": c["clicks"],
                   "clicks_delta": c["clicks"] - p["clicks"], "impressions_after": c["impressions"]}
            if d >= thr["mover_min_delta"]:
                out["winners"].append(row)
            elif -d >= thr["mover_min_delta"]:
                out["losers"].append(row)
        elif c and c["impressions"] >= thr["min_impressions"]:
            (out["beyond_row_cutoff"] if prev_trunc else out["new"]).append({"query": q, **_r(c)})
        elif p and p["impressions"] >= thr["min_impressions"]:
            (out["beyond_row_cutoff"] if cur_trunc else out["lost"]).append({"query": q, **_r(p)})
    out["winners"].sort(key=lambda r: -r["clicks_delta"])
    out["losers"].sort(key=lambda r: r["clicks_delta"])  # most clicks lost first
    out["new"].sort(key=lambda r: -r["impressions"])
    out["lost"].sort(key=lambda r: -r["impressions"])
    out["meta"] = {"truncated": {"current": cur_trunc, "previous": prev_trunc}, "thresholds": {
        k: thr[k] for k in ("min_impressions", "mover_min_delta")}}
    return out


def striking(query_rows: list[dict], thr: dict | None = None) -> list[dict]:
    thr = {**DEFAULTS, **(thr or {})}
    agg = aggregate(query_rows, lambda r: r["query"])
    rows = [{"query": q, **_r(m)} for q, m in agg.items()
            if thr["striking_min"] <= m["position"] <= thr["striking_max"] and m["impressions"] >= thr["min_impressions"]]
    return sorted(rows, key=lambda r: -r["impressions"])


def low_ctr(query_rows: list[dict], curve: dict, thr: dict | None = None) -> list[dict]:
    thr = {**DEFAULTS, **(thr or {})}
    out = []
    for q, m in aggregate(query_rows, lambda r: r["query"]).items():
        if m["position"] > thr["low_ctr_max_position"] or m["impressions"] < thr["min_impressions"]:
            continue
        exp, src = expected_ctr(m["position"], curve)
        if exp and m["ctr"] < thr["low_ctr_ratio"] * exp:
            out.append({"query": q, **_r(m), "expected_ctr": exp, "expected_source": src,
                        "missed_clicks_est": round(m["impressions"] * exp - m["clicks"], 1)})
    return sorted(out, key=lambda r: -r["missed_clicks_est"])


def cannibalization(page_query_rows: list[dict], thr: dict | None = None) -> list[dict]:
    thr = {**DEFAULTS, **(thr or {})}
    by_q: dict = {}
    for r in page_query_rows:
        by_q.setdefault(r["query"], []).append(r)
    out = []
    for q, rows in by_q.items():
        total = sum(r["impressions"] for r in rows)
        if total < thr["min_impressions"]:
            continue
        pages = sorted(({"page": r["page"], **_r(r), "share": round(r["impressions"] / total, 3)}
                        for r in rows if r["impressions"] / total >= thr["cannibal_min_share"]),
                       key=lambda p: -p["clicks"])
        if len(pages) >= 2:
            out.append({"query": q, "impressions": total, "pages": pages})
    return sorted(out, key=lambda r: -r["impressions"])


DECAY_ACTIONS = {
    "ranking_loss": "refresh content (competitors overtook it): update facts, depth, internal links",
    "demand_drop": "check seasonality/market; consolidate or retire only if GA4 key events and backlinks are also negligible",
    "ctr_loss": "rewrite title/meta; check new SERP features (AI Overview, snippets) taking clicks",
    "vanished": "inspect the URL (indexing, redirects, canonical) before anything else",
}


def classify_decline(prev: dict, cur: dict | None, thr: dict) -> str:
    """Mutually exclusive decline class; precedence ranking_loss > demand_drop > ctr_loss."""
    if not cur or cur["impressions"] == 0:
        return "vanished"
    if cur["position"] - prev["position"] >= thr["pos_drop"]:
        return "ranking_loss"
    if (_pct(cur["impressions"], prev["impressions"]) or 0) <= -thr["imp_drop_pct"]:
        return "demand_drop"
    return "ctr_loss"


def decay(cur_rows: list[dict], prev_rows: list[dict], thr: dict | None = None) -> dict:
    thr = {**DEFAULTS, **(thr or {})}
    cur = aggregate(cur_rows, lambda r: r["page"])
    prev = aggregate(prev_rows, lambda r: r["page"])
    cur_trunc = is_truncated(cur_rows)
    out, cutoff = [], []
    for page, p in prev.items():
        if p["impressions"] < thr["min_impressions"] or p["clicks"] == 0:
            continue
        c = cur.get(page)
        clicks_now = c["clicks"] if c else 0.0
        change = _pct(clicks_now, p["clicks"])
        if change is None or change > -thr["decay_pct"]:
            continue
        if not c and cur_trunc:
            cutoff.append(page)
            continue
        cls = classify_decline(p, c, thr)
        out.append({"page": page, "class": cls, "action": DECAY_ACTIONS[cls],
                    "clicks_before": p["clicks"], "clicks_after": clicks_now, "clicks_change_pct": change,
                    "impressions_change_pct": _pct(c["impressions"], p["impressions"]) if c else -100.0,
                    "position_before": round(p["position"], 2), "position_after": round(c["position"], 2) if c else None,
                    "clicks_lost": p["clicks"] - clicks_now})
    out.sort(key=lambda r: -r["clicks_lost"])
    return {"pages": out, "beyond_row_cutoff": cutoff,
            "meta": {"truncated": {"current": cur_trunc, "previous": is_truncated(prev_rows)},
                     "thresholds": {k: thr[k] for k in ("decay_pct", "pos_drop", "imp_drop_pct", "min_impressions")}}}


def brand_split(page_query_rows: list[dict], is_brand, lang_of, totals: dict | None = None) -> dict:
    """Brand vs non-brand per page language; ``is_brand``/``lang_of`` are the site-rules classifiers."""
    def kind(r):
        return "brand" if is_brand(r["query"]) else "non_brand"

    agg = aggregate(page_query_rows, lambda r: (lang_of(r["page"]), kind(r)))
    by_lang: dict = {}
    for (lang, k), m in sorted(agg.items()):
        by_lang.setdefault(lang, {})[k] = _r(m)
    overall = {k: _r(m) for k, m in aggregate(page_query_rows, kind).items()}
    nb = aggregate([r for r in page_query_rows if not is_brand(r["query"])], lambda r: r["query"])
    top_nb = sorted(({"query": q, **_r(m)} for q, m in nb.items()), key=lambda r: -r["clicks"])[:20]
    out = {"by_language": by_lang, "overall": overall, "top_non_brand": top_nb}
    if totals:
        attributed = sum(r["clicks"] for r in page_query_rows)
        attributed_imp = sum(r["impressions"] for r in page_query_rows)
        out["unattributed"] = {"clicks": round(totals["clicks"] - attributed, 1),
                               "impressions": round(totals["impressions"] - attributed_imp, 1),
                               "clicks_share": round((totals["clicks"] - attributed) / totals["clicks"], 3) if totals["clicks"] else None,
                               "note": "anonymized queries: counted in site totals, not classifiable as brand/non-brand"}
    return out


def topic(rows: list[dict], terms: list[str]) -> list[dict]:
    """Query (× page) rows whose query contains every term (normalised), aggregated."""
    want = [norm_text(t) for t in terms if norm_text(t)]

    def has(q: str, t: str) -> bool:  # phrase: whole-word match; single word: word prefix (handles inflection)
        return f" {t} " in f" {q} " if " " in t else any(w.startswith(t) for w in q.split())

    hits = [r for r in rows if all(has(norm_text(r["query"]), t) for t in want)]
    key = (lambda r: (r["query"], r["page"])) if hits and "page" in hits[0] else (lambda r: (r["query"], ""))
    out = [{"query": q, **({"page": p} if p else {}), **_r(m)} for (q, p), m in aggregate(hits, key).items()]
    return sorted(out, key=lambda r: -r["impressions"])


def _page_key(u: str) -> str:
    return str(u).split("#", 1)[0].rstrip("/")


def unseen(page_rows: list[dict], urls: list[str], limit: int = 150) -> list[str]:
    """URLs (in list order) that never got an impression in the page rows — likeliest non-indexed."""
    seen = {_page_key(r["page"]) for r in page_rows if r["impressions"] > 0}
    return [u for u in urls if _page_key(u) not in seen][:limit]


def top_pages(page_rows: list[dict], by: str = "clicks", limit: int = 20) -> list[dict]:
    """Pages (jump-link variants merged) ranked by clicks or impressions."""
    agg = aggregate(page_rows, lambda r: str(r["page"]).split("#", 1)[0])
    return [{"page": p, **_r(m)} for p, m in sorted(agg.items(), key=lambda kv: (-kv[1][by], kv[0]))[:limit]]


def totals_of(rows: list[dict]) -> dict:
    return {"clicks": sum(r["clicks"] for r in rows), "impressions": sum(r["impressions"] for r in rows)}


def value_model(planner_items: list[dict], query_rows: list[dict], curve: dict, target: int = 3) -> list[dict]:
    """Estimated monthly click gain and value of moving each keyword to `target` (labelled estimate).

    clicks_gain = volume × (expected CTR at target − current CTR); value = clicks_gain × CPC,
    CPC = midpoint of the planner's low/high top-of-page bids (account currency).
    """
    gsc = {norm_text(q): m for q, m in aggregate(query_rows, lambda r: r["query"]).items()}
    exp_t, src_t = expected_ctr(float(target), curve)
    out = []
    for it in planner_items:
        kw = it.get("keyword") or it.get("text")
        vol = it.get("avg_monthly_searches") or 0
        lo, hi = it.get("low_top_of_page_bid") or 0, it.get("high_top_of_page_bid") or 0
        cpc = round((lo + hi) / 2, 2) if (lo or hi) else None
        cur = gsc.get(norm_text(kw))
        cur_ctr = cur["ctr"] if cur else 0.0
        row = {"keyword": kw, "avg_monthly_searches": vol, "cpc_mid": cpc,
               "current_position": round(cur["position"], 2) if cur else None, "current_ctr": round(cur_ctr, 4),
               "target_position": target, "target_ctr": exp_t, "target_ctr_source": src_t, "label": "estimate"}
        if exp_t is None or not vol:
            row.update({"est_monthly_clicks_gain": None, "est_monthly_value": None})
        else:
            gain = max(0.0, vol * (exp_t - cur_ctr))
            row.update({"est_monthly_clicks_gain": round(gain, 1),
                        "est_monthly_value": round(gain * cpc, 2) if cpc is not None else None})
        out.append(row)
    return sorted(out, key=lambda r: -(r["est_monthly_value"] or 0))


def period_totals(rows: list[dict]) -> dict:
    """Clicks, impressions, CTR and impression-weighted position of a set of rows (daily totals or query rows)."""
    clicks, impr = sum(r["clicks"] for r in rows), sum(r["impressions"] for r in rows)
    pos = sum(r["position"] * r["impressions"] for r in rows) / impr if impr else None
    return {"clicks": round(clicks, 2), "impressions": round(impr, 2), "ctr": round(clicks / impr, 4) if impr else None,
            "position": round(pos, 2) if pos is not None else None, "rows": len(rows)}


def totals_change(cur: dict, prev: dict) -> dict:
    def pct(a, b):
        return round((a - b) / b * 100, 1) if b else None
    return {"clicks_delta": round(cur["clicks"] - prev["clicks"], 2), "clicks_change_pct": pct(cur["clicks"], prev["clicks"]),
            "impressions_delta": round(cur["impressions"] - prev["impressions"], 2),
            "impressions_change_pct": pct(cur["impressions"], prev["impressions"]),
            "ctr_delta_pts": round((cur["ctr"] - prev["ctr"]) * 100, 2) if cur["ctr"] is not None and prev["ctr"] is not None else None,
            "position_delta": round(cur["position"] - prev["position"], 2)
            if cur["position"] is not None and prev["position"] is not None else None}


def _inspections(obj, url=None, out=None) -> list[dict]:
    """Every URL Inspection index-status result in a response, with the URL it belongs to (any wrapper shape)."""
    out = [] if out is None else out
    obj = _unwrap(obj)
    if isinstance(obj, dict):
        url = obj.get("inspectionUrl") or obj.get("url") or obj.get("inspection_url") or url
        if "coverageState" in obj or ("verdict" in obj and "indexingState" in obj):
            out.append({"url": url, **obj})
            return out
        for v in obj.values():
            _inspections(v, url, out)
    elif isinstance(obj, list):
        for v in obj:
            _inspections(v, url, out)
    return out


def inspection_summary(results: list[dict]) -> dict:
    """Counts and shares per coverage state and verdict, canonical mismatches, URLs not indexed."""
    seen, rows = set(), []
    for r in results:
        key = r.get("url") or id(r)
        if key not in seen:
            seen.add(key)
            rows.append(r)
    n = len(rows)

    def tally(field):
        counts: dict[str, int] = {}
        for r in rows:
            counts[str(r.get(field) or "unknown")] = counts.get(str(r.get(field) or "unknown"), 0) + 1
        return [{field: k, "urls": v, "share": round(v / n, 3)} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]

    mismatch = [{"url": r.get("url"), "google_canonical": r.get("googleCanonical"),
                 "declared_canonical": r.get("userCanonical")} for r in rows
                if r.get("googleCanonical") and r.get("userCanonical")
                and r["googleCanonical"].rstrip("/") != r["userCanonical"].rstrip("/")]
    not_indexed = [{"url": r.get("url"), "coverage_state": r.get("coverageState")} for r in rows
                   if str(r.get("verdict") or "").upper() != "PASS"]
    return {"inspected": n, "by_coverage_state": tally("coverageState"), "by_verdict": tally("verdict"),
            "not_indexed": not_indexed, "not_indexed_share": round(len(not_indexed) / n, 3) if n else None,
            "canonical_mismatch": mismatch}


# --------------------------------------------------------------------- CLI ---
def _site(site: str | None):
    """(thresholds, rules) for --site; defaults and no rules without it."""
    if not site:
        return dict(DEFAULTS), None
    import rules
    import site_profile
    try:
        site_rules = rules.load(site)
    except FileNotFoundError:
        site_rules = None  # brand exclusion / brand-split unavailable; other analyses still run
    return site_profile.thresholds(site), site_rules


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["truncation", "anonymized", "curve", "movers", "striking", "low-ctr",
                                        "cannibalization", "decay", "brand-split", "value", "topic", "unseen",
                                        "top-pages", "inspection", "totals", "benchmark"])
    for opt in ("file", "totals", "rows", "query", "cur", "prev", "page-query", "totals-cur", "totals-prev",
                "planner", "site", "terms", "page", "urls"):
        ap.add_argument(f"--{opt}")
    ap.add_argument("--inspect", nargs="+", default=None, help="recorded gsc.inspect responses")
    ap.add_argument("--curve-query", dest="curve_query", default=None,
                    help="the site's last 12 months of query rows: fills CTR buckets the run window cannot")
    ap.add_argument("--check", action="store_true", help="benchmark: exit 2 when stale")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--by", choices=["clicks", "impressions"], default="clicks")
    ap.add_argument("--target", type=int, default=None)
    a = ap.parse_args(argv)
    try:
        thr, site_rules = _site(a.site)
        brand = site_rules.is_brand if site_rules else None
        longer = load_rows(a.curve_query, ["query"]) if a.curve_query else None
        if a.command == "truncation":
            rows = load_rows(a.file, ["query"])
            res = {"rows": len(rows), "truncated": is_truncated(rows), "row_limit": ROW_LIMIT}
        elif a.command == "anonymized":
            t, r = totals_of(load_rows(a.totals, ["date"])), totals_of(load_rows(a.rows, ["query"]))
            res = {"total_clicks": t["clicks"], "attributed_clicks": r["clicks"],
                   "anonymized_clicks_share": round(1 - r["clicks"] / t["clicks"], 3) if t["clicks"] else None}
        elif a.command == "benchmark":
            st = benchmark_status(load_benchmark())
            print(json.dumps(st, ensure_ascii=False, indent=2))
            return 2 if a.check and st["stale"] else 0
        elif a.command == "curve":
            curve = ctr_curve(load_rows(a.query, ["query"]), brand, thr, longer)
            res = {"curve": curve, "basis": curve_basis(curve, longer=bool(longer))}
        elif a.command == "movers":
            res = movers(load_rows(a.cur, ["query"]), load_rows(a.prev, ["query"]), thr)
        elif a.command == "striking":
            res = {"striking_distance": striking(load_rows(a.query, ["query"]), thr),
                   "thresholds": {k: thr[k] for k in ("striking_min", "striking_max", "min_impressions")}}
        elif a.command == "low-ctr":
            q = load_rows(a.query, ["query"])
            curve = ctr_curve(q, brand, thr, longer)
            res = {"low_ctr": low_ctr(q, curve, thr), "curve": curve, "basis": curve_basis(curve, longer=bool(longer))}
        elif a.command == "topic":
            terms = [t.strip() for t in (a.terms or "").split(",") if t.strip()]
            if not terms:
                raise ValueError("--terms is required (comma-separated)")
            src = a.page_query or a.query or a.file
            rows = load_rows(src, ["query", "page"] if a.page_query else ["query"])
            res = {"terms": terms, "rows": topic(rows, terms), "truncated": is_truncated(rows)}
        elif a.command == "unseen":
            listed = _unwrap(json.loads(Path(a.urls).read_text()))
            listed = listed.get("urls", []) if isinstance(listed, dict) else listed
            res = {"urls": unseen(load_rows(a.page, ["page"]), listed, a.limit or 150)}
        elif a.command == "top-pages":
            rows = load_rows(a.page, ["page"])
            res = {"pages": top_pages(rows, a.by, a.limit or 20), "truncated": is_truncated(rows)}
        elif a.command == "totals":
            cur_rows = load_rows(a.cur, ["date"])
            res = {"current": period_totals(cur_rows), "truncated": is_truncated(cur_rows)}
            if a.prev:
                res["previous"] = period_totals(load_rows(a.prev, ["date"]))
                res["change"] = totals_change(res["current"], res["previous"])
        elif a.command == "inspection":
            if not a.inspect:
                raise ValueError("--inspect is required")
            found: list[dict] = []
            for f in a.inspect:
                _inspections(json.loads(Path(f).read_text()), out=found)
            res = inspection_summary(found)
        elif a.command == "cannibalization":
            res = {"cannibalization": cannibalization(load_rows(a.page_query, ["query", "page"]), thr)}
        elif a.command == "decay":
            res = decay(load_rows(a.cur, ["page"]), load_rows(a.prev, ["page"]), thr)
        elif a.command == "brand-split":
            if not site_rules:
                raise ValueError("brand-split needs --site (brand and language come from the site's rules)")
            lang = site_rules.page_language
            res = {"current": brand_split(load_rows(a.cur, ["query", "page"]), brand, lang,
                                          totals_of(load_rows(a.totals_cur, ["date"])) if a.totals_cur else None)}
            if a.prev:
                res["previous"] = brand_split(load_rows(a.prev, ["query", "page"]), brand, lang,
                                              totals_of(load_rows(a.totals_prev, ["date"])) if a.totals_prev else None)
        else:  # value
            q = load_rows(a.query, ["query"])
            items = json.loads(Path(a.planner).read_text())
            items = _unwrap(items)
            if isinstance(items, dict):
                items = items.get("results") or items.get("ideas") or items.get("keywords") or []
            target = a.target or int(thr["value_target_position"])
            curve = ctr_curve(q, brand, thr, longer)
            res = {"value": value_model(items, q, curve, target),
                   "method": "volume × (CTR at target − current CTR) × mid CPC; estimate",
                   "basis": curve_basis(curve, longer=bool(longer))}
    except (ValueError, FileNotFoundError, KeyError, TypeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
