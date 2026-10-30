#!/usr/bin/env python3
"""Site classification rules — the single source shared by the SEO skills and the SEO sheet.

Rules live in ``seo/config/rules/<domain>.json`` (ported from the "PBS - SEO Rankings"
sheet): query categories, page tags, page languages, GA4 channels, tracked keywords and
the automatic keyword-selection settings. In every rule list the first match wins.

Usage (all print JSON):
    python3 seo/rules.py --site pbservices.ge validate
    python3 seo/rules.py --site pbservices.ge classify --query "внж грузии по ип"
    python3 seo/rules.py --site pbservices.ge classify --page /ru/blog/x
    python3 seo/rules.py --site pbservices.ge classify --channel "chatgpt.com / referral"
    python3 seo/rules.py --site pbservices.ge breakdown --by category --cur F [--prev F]       # query rows
    python3 seo/rules.py --site pbservices.ge breakdown --by page_tag|language --cur F [--prev F]  # page rows
    python3 seo/rules.py --site pbservices.ge keywords --query F [--prev F] [--countries F]  # tracked set (+ status, top countries)
    python3 seo/rules.py --site pbservices.ge targets --page-query F   # tracked keyword ranking with its target page?
    python3 seo/rules.py --site pbservices.ge trend --by category|page_tag|language|keyword --rows W1 W2 …  # one file per week
Exit codes: 0 = ok, 1 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RULES_DIR = HERE / "config" / "rules"

BRAND, GENERIC = "Brand", "Generic"
TRACKED_TYPES = ("Core", "Brand")
LISTS = {"query_categories": "category", "page_tags": "tag", "page_languages": "language", "channels": "channel"}
METRIC_KEYS = {"clicks", "impressions", "ctr", "position"}
UNPORTABLE = re.compile(r"\(\?(?!:)|\\[1-9]")  # only (?:…) allowed: lookarounds, flags, backrefs aren't RE2/JS-portable
SCRIPT_LANG = (("ru", re.compile(r"[Ѐ-ӿ]")), ("ar", re.compile(r"[؀-ۿ]")),
               ("zh", re.compile(r"[一-鿿]")))


def rules_path(domain: str) -> Path:
    return RULES_DIR / f"{domain}.json"


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def clean_url(url: str, domain: str) -> str:
    """Sheet's "Page (clean)": drop #fragment; path-only (GA4) → absolute; add the trailing slash."""
    u = str(url).strip()
    if not u or u.startswith("("):  # "(not set)", "(other)"
        return u
    u = u.split("#", 1)[0]
    if u.startswith("/"):
        u = f"https://{domain}{u}"
    p = urlsplit(u)
    path = p.path or "/"
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return urlunsplit((p.scheme, p.netloc, path, p.query, ""))


def query_language(query: str) -> str:
    """Keyword language from its script (Cyrillic → ru, Arabic → ar, Han → zh, else en)."""
    for code, rx in SCRIPT_LANG:
        if rx.search(query):
            return code
    return "en"


# -------------------------------------------------------------- validation ---
def _regex_issue(where: str, rx) -> str | None:
    if not isinstance(rx, str) or not rx:
        return f"{where}: regex must be a non-empty string"
    if UNPORTABLE.search(rx):
        return f"{where}: lookarounds, named groups and backreferences are not portable to the sheet"
    try:
        re.compile(rx)
    except re.error as e:
        return f"{where}: invalid regex ({e})"
    return None


def validate(data: dict, domain: str | None = None) -> list[str]:
    """Human-readable issues (empty == valid)."""
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["rules file must be a JSON object"]
    if domain and data.get("domain") != domain:
        issues.append(f"domain: expected '{domain}', got {data.get('domain')!r}")
    for section, name_key in LISTS.items():
        sec = data.get(section)
        if not isinstance(sec, dict):
            issues.append(f"missing section: {section}")
            continue
        if not isinstance(sec.get("default"), str) or not sec["default"]:
            issues.append(f"{section}.default: required string")
        for i, r in enumerate(sec.get("rules") if isinstance(sec.get("rules"), list) else []):
            if not isinstance(r, dict) or not isinstance(r.get(name_key), str) or not r[name_key]:
                issues.append(f"{section}.rules[{i}]: needs a '{name_key}' name")
                continue
            if (msg := _regex_issue(f"{section}.rules[{i}] ({r[name_key]})", r.get("regex"))):
                issues.append(msg)
        if not isinstance(sec.get("rules"), list):
            issues.append(f"{section}.rules: required list")
    if issues:
        return issues

    qc = data["query_categories"]
    categories = {r["category"] for r in qc["rules"]} | {qc["default"]}
    if BRAND not in categories or GENERIC not in categories:
        issues.append(f"query_categories: must define '{BRAND}' and '{GENERIC}'")
    ch = data["channels"]
    for key in ("ai_channel", "organic_channel"):
        if ch.get(key) not in {r["channel"] for r in ch["rules"]}:
            issues.append(f"channels.{key}: must name one of the channel rules")

    kw = data.get("keywords")
    if not isinstance(kw, dict) or not isinstance(kw.get("tracked"), list) or not isinstance(kw.get("auto"), dict):
        return issues + ["keywords: needs 'tracked' (list) and 'auto' (object)"]
    r = Rules(data, check=False)
    seen: dict[str, str] = {}
    for i, t in enumerate(kw["tracked"]):
        if not isinstance(t, dict) or not isinstance(t.get("keyword"), str) or not t["keyword"].strip():
            issues.append(f"keywords.tracked[{i}]: needs a keyword")
            continue
        k = t["keyword"]
        if t.get("type") not in TRACKED_TYPES:
            issues.append(f"keywords.tracked[{i}] ({k}): type must be one of {TRACKED_TYPES}")
        if t.get("category") not in categories:
            issues.append(f"keywords.tracked[{i}] ({k}): unknown category {t.get('category')!r}")
        if (t.get("type") == BRAND) != (t.get("category") == BRAND):
            issues.append(f"keywords.tracked[{i}] ({k}): type Brand ⇔ category Brand")
        key = r.keyword_key(k)
        if key in seen:
            issues.append(f"keywords.tracked[{i}] ({k}): duplicate of '{seen[key]}' (same key '{key}')")
        seen[key] = k
        tp = t.get("target_page")
        if tp is not None and (not isinstance(tp, str) or not tp.startswith(f"https://{data.get('domain')}/")):
            issues.append(f"keywords.tracked[{i}] ({k}): target_page must be an absolute https://{data.get('domain')}/ URL")
    auto = kw["auto"]
    for path in ("lookback_days", "max_words", "proven.slots", "proven.min_clicks", "opportunity.slots",
                 "opportunity.min_impressions", "opportunity.position_from", "opportunity.position_to", "generic.slots"):
        v = auto
        for part in path.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            issues.append(f"keywords.auto.{path}: required non-negative number")
    if auto.get("exclude_regex") and (msg := _regex_issue("keywords.auto.exclude_regex", auto["exclude_regex"])):
        issues.append(msg)
    if not all(isinstance(w, str) for w in auto.get("ignored_words", [])):
        issues.append("keywords.auto.ignored_words: list of strings")
    caps = auto.get("category_caps")
    if not isinstance(caps, dict):
        issues.append("keywords.auto.category_caps: required object")
    else:
        for c, n in caps.items():
            if c not in categories or c in (BRAND, GENERIC):
                issues.append(f"keywords.auto.category_caps.{c}: must be a service category")
            if not isinstance(n, int) or isinstance(n, bool) or n < 0:
                issues.append(f"keywords.auto.category_caps.{c}: non-negative integer")
    return issues


# -------------------------------------------------------------- classifier ---
class Rules:
    def __init__(self, data: dict, check: bool = True):
        if check and (issues := validate(data)):
            raise ValueError("invalid rules: " + "; ".join(issues))
        self.data = data
        self.domain = data["domain"]
        comp = lambda sec, k: [(r[k], re.compile(r["regex"])) for r in data[sec]["rules"]]  # noqa: E731
        self._q, self._tags = comp("query_categories", "category"), comp("page_tags", "tag")
        self._langs, self._chan = comp("page_languages", "language"), comp("channels", "channel")
        kw = data.get("keywords") or {}
        self.tracked = {_norm(t["keyword"]): t for t in kw.get("tracked", []) if isinstance(t, dict) and t.get("keyword")}
        self.auto = kw.get("auto") or {}
        ex = self.auto.get("exclude_regex")
        self._exclude = re.compile(ex) if ex else None
        self._ignored = {w.lower() for w in self.auto.get("ignored_words", []) if isinstance(w, str)}

    @staticmethod
    def _first(pairs, text: str, default: str) -> str:
        for name, rx in pairs:
            if rx.search(text):
                return name
        return default

    # queries
    def rule_category(self, query: str) -> str | None:
        """Category from the rules alone (None = unclassified)."""
        q = _norm(query)
        return next((c for c, rx in self._q if rx.search(q)), None)

    def query_category(self, query: str) -> str:
        """Tracked keywords keep their own category; else first matching rule; else the default."""
        t = self.tracked.get(_norm(query))
        if t:
            return t["category"]
        return self.rule_category(query) or self.data["query_categories"]["default"]

    def is_brand(self, query: str) -> bool:
        return self.query_category(query) == BRAND

    def keyword_key(self, query: str) -> str:
        """Duplicate key: ignored words dropped, words cut to 5 letters, de-duplicated and sorted."""
        return " ".join(sorted({w[:5] for w in _norm(query).split() if w not in self._ignored}))

    # pages and channels
    def clean(self, url: str) -> str:
        return clean_url(url, self.domain)

    def page_tag(self, url: str) -> str:
        return self._first(self._tags, self.clean(url), self.data["page_tags"]["default"])

    def page_language(self, url: str) -> str:
        return self._first(self._langs, self.clean(url), self.data["page_languages"]["default"])

    def channel(self, source_medium: str) -> str:
        return self._first(self._chan, _norm(source_medium), self.data["channels"]["default"])

    def ai_regex(self) -> str:
        name = self.data["channels"]["ai_channel"]
        return next(r["regex"] for r in self.data["channels"]["rules"] if r["channel"] == name)

    def collapse_fragments(self, rows: list[dict]) -> list[dict]:
        """Jump-link (#) variants of a URL show in the same result: clicks summed, impressions/position from the largest."""
        if not rows or "page" not in rows[0]:
            return rows
        groups: dict = {}
        for r in rows:
            k = tuple(sorted((d, v) for d, v in r.items() if d not in METRIC_KEYS and d != "page"))
            groups.setdefault((k, str(r["page"]).split("#", 1)[0]), []).append(r)
        out = []
        for (k, base), rs in groups.items():
            top = max(rs, key=lambda r: r["impressions"])
            clicks = sum(r["clicks"] for r in rs)
            imp = top["impressions"]
            out.append({**dict(k), "page": base, "clicks": clicks, "impressions": imp,
                        "ctr": clicks / imp if imp else 0.0, "position": top["position"]})
        return out

    def targets(self, page_query_rows: list[dict]) -> dict:
        """Does each tracked keyword with a target page rank with that page? (query × page rows)."""
        import gsc_metrics as G
        rows = [r for r in self.collapse_fragments(page_query_rows) if _norm(r["query"]) in self.tracked]
        agg = G.aggregate(rows, lambda r: (_norm(r["query"]), self.clean(r["page"])))
        by_q: dict = {}
        for (q, page), m in agg.items():
            by_q.setdefault(q, {})[page] = m
        out = []
        for k, t in self.tracked.items():
            if not t.get("target_page"):
                continue
            target, pages = self.clean(t["target_page"]), by_q.get(k, {})
            ranked = sorted(pages.items(), key=lambda kv: (-kv[1]["impressions"], -kv[1]["clicks"], kv[0]))
            total = sum(m["impressions"] for m in pages.values())
            tm = pages.get(target)
            status = ("no impressions" if not ranked else "ok" if ranked[0][0] == target
                      else "wrong page" if tm else "target not ranking")
            row = {"keyword": t["keyword"], "type": t["type"], "category": t["category"], "target_page": target,
                   "status": status, "pages_ranking": len(ranked),
                   "target": ({**G._r(tm), "share": round(tm["impressions"] / total, 3)} if tm else None)}
            if ranked and ranked[0][0] != target:
                row["top_page"] = {"page": ranked[0][0], **G._r(ranked[0][1]),
                                   "share": round(ranked[0][1]["impressions"] / total, 3)}
            out.append(row)
        order = {"wrong page": 0, "target not ranking": 1, "ok": 2, "no impressions": 3}
        out.sort(key=lambda r: (order[r["status"]], -((r.get("top_page") or r.get("target") or {}).get("impressions", 0))))
        return {"targets": out, "truncated": G.is_truncated(page_query_rows),
                "basis": "query × page rows (named queries); jump-link (#) variants merged into their page"}

    def trend(self, weeks: list[tuple[str, list[dict]]], by: str, min_impressions: float = 0) -> dict:
        """Week-by-week clicks / impressions / position per segment (one row set per Mon–Sun week)."""
        import gsc_metrics as G
        if by == "keyword":
            picked = self.select_keywords([r for _, rows in weeks for r in rows])["keywords"]
            kind = {_norm(k["keyword"]): k["type"] for k in picked}
            keyf, order = (lambda r: _norm(r["query"]) if _norm(r["query"]) in kind else None), list(kind)
        else:
            keyf, order = {
                "category": (lambda r: self.query_category(r["query"]), self.services() + [BRAND, GENERIC]),
                "page_tag": (lambda r: self.page_tag(r["page"]), self.sections()),
                "language": (lambda r: self.page_language(r["page"]), self.languages()),
            }[by]
        per_week, totals = [], []
        for _, rows in weeks:
            rows = self.collapse_fragments(rows)
            agg = G.aggregate(rows, keyf)
            agg.pop(None, None)
            per_week.append(agg)
            tot = G.aggregate(rows, lambda r: "t" if keyf(r) is not None else None).get("t")
            totals.append(tot)
        names = [n for n in order if any(n in w for w in per_week)]
        names += sorted({n for w in per_week for n in w} - set(names))

        def series(ms, name):
            return {by: name, "clicks": [round(m["clicks"], 1) if m else 0 for m in ms],
                    "impressions": [round(m["impressions"], 1) if m else 0 for m in ms],
                    "position": [round(m["position"], 1) if m and m["impressions"] else None for m in ms],
                    "low_volume": [(m or {}).get("impressions", 0) < min_impressions for m in ms]}

        rows_out = [series([w.get(n) for w in per_week], n) for n in names]
        if by == "keyword":
            for r in rows_out:
                r["type"] = kind[r["keyword"]]
        total_name = "Tracked keywords" if by == "keyword" else "Total"
        return {"by": by, "weeks": [lbl for lbl, _ in weeks], "rows": rows_out, "total": series(totals, total_name),
                "truncated_weeks": [lbl for lbl, rows in weeks if G.is_truncated(rows)],
                "low_volume_below_impressions": min_impressions,
                "basis": ("named queries only (anonymized queries excluded)" if by in ("category", "keyword")
                          else "page rows (include anonymized-query traffic); jump-link (#) variants merged")}

    # derived profile values
    def services(self) -> list[str]:
        caps = list((self.auto.get("category_caps") or {}).keys())
        rest = [c for c, _ in self._q if c not in caps and c not in (BRAND, GENERIC)]
        return list(dict.fromkeys(caps + rest))

    def sections(self) -> list[str]:
        return [t for t, _ in self._tags] + [self.data["page_tags"]["default"]]

    def languages(self) -> list[str]:
        return list(dict.fromkeys([self.data["page_languages"]["default"]] + [lg for lg, _ in self._langs]))

    def priority_keywords(self) -> dict[str, list[str]]:
        """Core tracked keywords grouped by language (lowercase codes)."""
        out: dict[str, list[str]] = {lg.lower(): [] for lg in self.languages()}
        for t in self.tracked.values():
            if t.get("type") == "Core":
                out.setdefault(query_language(t["keyword"]), []).append(t["keyword"])
        return out

    # analyses
    def breakdown(self, rows: list[dict], by: str, prev_rows: list[dict] | None = None,
                  min_impressions: float = 0) -> dict:
        import gsc_metrics as G
        keyf, order = {
            "category": (lambda r: self.query_category(r["query"]), self.services() + [BRAND, GENERIC]),
            "page_tag": (lambda r: self.page_tag(r["page"]), self.sections()),
            "language": (lambda r: self.page_language(r["page"]), self.languages()),
        }[by]
        rows = self.collapse_fragments(rows)
        prev_rows = self.collapse_fragments(prev_rows) if prev_rows is not None else None
        cur = G.aggregate(rows, keyf)
        prev = G.aggregate(prev_rows, keyf) if prev_rows is not None else None
        names = [n for n in order if n in cur or (prev and n in prev)]
        names += sorted(n for n in set(cur) | set(prev or {}) if n not in names)

        def line(name, c, p):
            row = {by: name, **G._r(c)} if c else {by: name, "clicks": 0, "impressions": 0, "ctr": 0.0, "position": None}
            row["low_volume"] = (c or {}).get("impressions", 0) < min_impressions
            if prev is not None:
                row["prev"] = G._r(p) if p else None
                row["clicks_change_pct"] = G._pct((c or {}).get("clicks", 0), p["clicks"]) if p else None
                row["position_change"] = (round(p["position"] - c["position"], 2) if p and c else None)  # + = improved
            return row

        out = [line(n, cur.get(n), (prev or {}).get(n)) for n in names]
        tot_c = G.aggregate(rows, lambda r: "t").get("t")
        tot_p = G.aggregate(prev_rows, lambda r: "t").get("t") if prev_rows is not None else None
        basis = ("named queries only (anonymized queries excluded)" if by == "category"
                 else "page rows (include anonymized-query traffic); jump-link (#) variants merged")
        return {"by": by, "rows": out, "total": line("Total", tot_c, tot_p), "basis": basis,
                "low_volume_below_impressions": min_impressions, "truncated": G.is_truncated(rows)}

    def select_keywords(self, query_rows: list[dict], prev_rows: list[dict] | None = None,
                        country_rows: list[dict] | None = None) -> dict:
        """Tracked set as the sheet builds it: Core + Brand (manual), then Proven, Opportunity, Generic (auto).

        With ``prev_rows``: previous metrics and the sheet's status (New / Lost / No impressions);
        a truncated pull never yields New/Lost (status "beyond row cutoff"). With ``country_rows``
        (country × query): each keyword's top 3 countries by impressions, as in the sheet."""
        import gsc_metrics as G
        a = self.auto
        pool = []
        for q, m in G.aggregate(query_rows, lambda r: _norm(r["query"])).items():
            pool.append({"keyword": q, "category": self.query_category(q), "unclassified": q not in self.tracked
                         and self.rule_category(q) is None, "clicks": m["clicks"], "impressions": m["impressions"],
                         "position": m["position"], "words": len(q.split()), "key": self.keyword_key(q)})
        by_kw = {p["keyword"]: p for p in pool}

        def pick(p, typ):
            return {"keyword": p["keyword"], "category": p["category"], "type": typ,
                    "language": query_language(p["keyword"]), "clicks": round(p["clicks"], 1),
                    "impressions": round(p["impressions"], 1),
                    "position": round(p["position"], 1) if p["impressions"] else None}

        out, used = [], set()
        for k, t in self.tracked.items():
            p = by_kw.get(k) or {"keyword": t["keyword"], "category": t["category"], "clicks": 0, "impressions": 0, "position": 0}
            row = pick({**p, "category": t["category"]}, t["type"])
            if t.get("target_page"):
                row["target_page"] = t["target_page"]
            out.append(row)
            used.add(self.keyword_key(k))
        caps, counts = a.get("category_caps") or {}, {}

        def eligible(p):
            return (p["category"] in caps and not p["unclassified"] and counts.get(p["category"], 0) < caps[p["category"]]
                    and p["words"] <= a["max_words"] and p["key"] not in used
                    and not (self._exclude and self._exclude.search(p["keyword"])))

        def take(cands, typ, slots, ok):
            n = 0
            for p in cands:
                if n >= slots:
                    break
                if ok(p):
                    out.append(pick(p, typ))
                    used.add(p["key"])
                    counts[p["category"]] = counts.get(p["category"], 0) + 1
                    n += 1

        pr, op, ge = a["proven"], a["opportunity"], a["generic"]
        by_clicks = sorted(pool, key=lambda p: (-p["clicks"], -p["impressions"], p["keyword"]))
        take(by_clicks, "Proven", pr["slots"], lambda p: p["clicks"] >= pr["min_clicks"] and eligible(p))
        take(sorted(pool, key=lambda p: (-p["impressions"], -p["clicks"], p["keyword"])), "Opportunity", op["slots"],
             lambda p: (p["impressions"] >= op["min_impressions"]
                        and op["position_from"] <= p["position"] <= op["position_to"] and eligible(p)))
        take(by_clicks, "Generic", ge["slots"],
             lambda p: (p["category"] == GENERIC and not p["unclassified"] and p["clicks"] > 0
                        and p["words"] <= a["max_words"] and p["key"] not in used))
        if prev_rows is not None:
            prev = G.aggregate(prev_rows, lambda r: _norm(r["query"]))
            cut = G.is_truncated(query_rows) or G.is_truncated(prev_rows)
            for k in out:
                pm = prev.get(_norm(k["keyword"]))
                k["prev"] = ({"clicks": round(pm["clicks"], 1), "impressions": round(pm["impressions"], 1),
                              "position": round(pm["position"], 1) if pm["impressions"] else None} if pm else None)
                now, before = k["impressions"] > 0, bool(pm and pm["impressions"] > 0)
                k["position_change"] = (round(k["prev"]["position"] - k["position"], 1) if now and before else None)
                k["status"] = ("" if now and before else "No impressions" if not now and not before
                               else "beyond row cutoff" if cut else "New" if now else "Lost")
        if country_rows is not None:
            by_q: dict = {}
            for r in country_rows:
                d = by_q.setdefault(_norm(r["query"]), {})
                d[str(r["country"]).upper()] = d.get(str(r["country"]).upper(), 0.0) + r["impressions"]
            for k in out:
                c = by_q.get(_norm(k["keyword"]), {})
                tot = sum(c.values())
                top = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
                k["countries"] = [{"country": cc, "share": round(v / tot, 3)} for cc, v in top] if tot else []
                k["countries_text"] = (", ".join(f"{cc} {'<1' if v / tot < 0.005 else round(v / tot * 100)}%"
                                                 for cc, v in top) if tot else "No data")
        unclassified = [{k: (round(p[k], 1) if isinstance(p[k], float) else p[k])
                         for k in ("keyword", "clicks", "impressions", "position")}
                        for p in by_clicks if p["unclassified"]][:50]
        res = {"keywords": out, "unclassified_to_review": unclassified, "truncated": G.is_truncated(query_rows),
                "lookback_days": a["lookback_days"],
                "note": "auto picks are only as complete as the query pull: use a lookback_days window"}
        if country_rows is not None:
            res["countries_truncated"] = G.is_truncated(country_rows)
        return res


def _week_label(path: str) -> str:
    """Week start from the recorded call's startDate (context.json), else the file name."""
    p = Path(path)
    ctx = p.parent.parent / "context.json"
    if ctx.exists():
        try:
            for c in json.loads(ctx.read_text()).get("calls", []):
                if c.get("file") == f"{p.parent.name}/{p.name}" and (c.get("args") or {}).get("startDate"):
                    return c["args"]["startDate"]
        except (json.JSONDecodeError, AttributeError):
            pass
    return p.stem


def load(domain: str) -> Rules:
    p = rules_path(domain)
    if not p.exists():
        raise FileNotFoundError(f"no rules for '{domain}' ({p})")
    data = json.loads(p.read_text())
    issues = validate(data, domain)
    if issues:
        raise ValueError(f"invalid rules for '{domain}': " + "; ".join(issues))
    return Rules(data, check=False)


# --------------------------------------------------------------------- CLI ---
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="domain, e.g. pbservices.ge")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    c = sub.add_parser("classify")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--query")
    g.add_argument("--page")
    g.add_argument("--channel", help="GA4 'source / medium'")
    b = sub.add_parser("breakdown")
    b.add_argument("--by", choices=["category", "page_tag", "language"], required=True)
    b.add_argument("--cur", required=True)
    b.add_argument("--prev")
    k = sub.add_parser("keywords")
    k.add_argument("--query", required=True)
    k.add_argument("--prev", help="previous-period query rows: adds prev metrics and New/Lost status")
    k.add_argument("--countries", help="country × query rows (gsc.geo_query): top 3 countries per keyword")
    t = sub.add_parser("targets")
    t.add_argument("--page-query", dest="page_query", required=True)
    tr = sub.add_parser("trend")
    tr.add_argument("--by", choices=["category", "page_tag", "language", "keyword"], required=True)
    tr.add_argument("--rows", nargs="+", required=True, help="one recorded file per week, oldest first")
    a = ap.parse_args(argv)
    try:
        if a.command == "validate":
            p = rules_path(a.site)
            if not p.exists():
                raise FileNotFoundError(f"no rules for '{a.site}' ({p})")
            issues = validate(json.loads(p.read_text()), a.site)
            for i in issues:
                print(f"ERROR {i}")
            print("OK — rules valid" if not issues else f"{len(issues)} issue(s)")
            return 1 if issues else 0
        r = load(a.site)
        import gsc_metrics as G
        if a.command == "classify":
            if a.query is not None:
                res = {"query": a.query, "category": r.query_category(a.query),
                       "tracked": (r.tracked.get(_norm(a.query)) or {}).get("type"),
                       "unclassified": _norm(a.query) not in r.tracked and r.rule_category(a.query) is None,
                       "language": query_language(a.query), "key": r.keyword_key(a.query)}
            elif a.page is not None:
                res = {"page": a.page, "clean": r.clean(a.page), "tag": r.page_tag(a.page),
                       "language": r.page_language(a.page)}
            else:
                res = {"source_medium": a.channel, "channel": r.channel(a.channel)}
        elif a.command == "breakdown":
            dims = ["query"] if a.by == "category" else ["page"]
            import site_profile
            thr = site_profile.thresholds(a.site)
            res = r.breakdown(G.load_rows(a.cur, dims), a.by, G.load_rows(a.prev, dims) if a.prev else None,
                              min_impressions=thr["min_impressions"])
        elif a.command == "keywords":
            res = r.select_keywords(G.load_rows(a.query, ["query"]), G.load_rows(a.prev, ["query"]) if a.prev else None,
                                    G.load_rows(a.countries, ["country", "query"]) if a.countries else None)
        elif a.command == "targets":
            res = r.targets(G.load_rows(a.page_query, ["query", "page"]))
        else:
            import site_profile
            dims = ["query"] if a.by in ("category", "keyword") else ["page"]
            weeks = [(_week_label(f), G.load_rows(f, dims)) for f in a.rows]
            res = r.trend(weeks, a.by, min_impressions=site_profile.thresholds(a.site)["min_impressions"])
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
