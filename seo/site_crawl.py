#!/usr/bin/env python3
"""Stdlib site crawler for the SEO skills: link graph, hreflang, canonicals, robots, page facts.

No third-party service and no API key: it fetches public pages directly (polite
delay, identifying User-Agent, robots.txt respected for every fetch — disallowed URLs are
listed under ``skipped_by_robots``, never fetched) so internal-link, hreflang and AI-crawler
findings rest on observed HTML instead of approximations.

Commands (all print JSON):
    robots   --site https://example.com [--url U …]       # robots.txt verdict per search/AI crawler, homepage + U
    sitemap  --site https://example.com [--limit 5000]    # URLs from robots.txt Sitemap: / sitemap.xml
    crawl    --site https://example.com [--limit 300] [--delay 0.5] [--profile example.com]
             # BFS from the homepage: inlinks, click depth, orphans vs sitemap,
             # hreflang reciprocity/self/x-default, cross-language canonicals
    facts    --url URL [--url URL ...]                    # title/meta/headings/first 45 words/tables/JSON-LD
    underlinked --crawl F --url TARGET [--url …]          # targets that are orphaned, weakly linked or deep
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

USER_AGENT = "PBServicesSEOAudit/1.0 (+site owner audit; seo/site_crawl.py)"
TIMEOUT = 20

# token, operator, purpose, kind (search = blocking costs visibility; training = policy choice)
AI_BOTS = [
    ("Googlebot", "Google", "Google Search index, incl. AI Overviews / AI Mode", "search"),
    ("Bingbot", "Microsoft", "Bing index (also grounds Copilot)", "search"),
    ("OAI-SearchBot", "OpenAI", "ChatGPT search index and citations", "search"),
    ("ChatGPT-User", "OpenAI", "user-initiated fetch (robots.txt may not apply)", "user"),
    ("Claude-SearchBot", "Anthropic", "Claude search index", "search"),
    ("Claude-User", "Anthropic", "user-initiated fetch", "user"),
    ("PerplexityBot", "Perplexity", "Perplexity search index (not training)", "search"),
    ("Perplexity-User", "Perplexity", "user-initiated fetch (generally ignores robots.txt)", "user"),
    ("GPTBot", "OpenAI", "model training", "training"),
    ("ClaudeBot", "Anthropic", "model training", "training"),
    ("Google-Extended", "Google", "Gemini training/grounding control — does NOT affect Search or AI Overviews", "training"),
    ("Applebot-Extended", "Apple", "Apple AI training control", "training"),
    ("CCBot", "Common Crawl", "open crawl dataset reused for model training", "training"),
]


# ---------------------------------------------------------------- fetching ---
def http_fetch(url: str) -> tuple[int, str, str, str]:
    """Return (status, final_url, content_type, text). Never raises on HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            charset = r.headers.get_content_charset() or "utf-8"
            return r.status, r.geturl(), ctype, r.read(5_000_000).decode(charset, "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type", "") if e.headers else "", ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, url, "", f"__error__ {e}"


def norm_url(url: str) -> str:
    """Lower-case scheme/host, drop fragment and default ports; keep path and query."""
    url, _ = urldefrag(url.strip())
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.port and not ((p.scheme == "http" and p.port == 80) or (p.scheme == "https" and p.port == 443)):
        host = f"{host}:{p.port}"
    return urlunparse((p.scheme.lower(), host, p.path or "/", "", p.query, ""))


def _same_site(url: str, host: str) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return h == host or h == f"www.{host}" or f"www.{h}" == host


# ----------------------------------------------------------------- parsing ---
class PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}
    CHROME = {"nav", "header", "footer", "aside"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, bool]] = []   # href, anchor text, nofollow
        self.canonical = None
        self.hreflang: dict[str, str] = {}
        self.robots = ""
        self.title = ""
        self.meta_description = ""
        self.lang = ""
        self.headings: list[tuple[str, str]] = []
        self.tables = self.lists = 0
        self.jsonld: list[str] = []
        self._stack: list[str] = []
        self._a: list | None = None
        self._h: list | None = None
        self._title = False
        self._ld: list | None = None
        self.main_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self._stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], [], "nofollow" in a.get("rel", "").lower()]
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel and a.get("href"):
                self.canonical = a["href"]
            if "alternate" in rel and a.get("hreflang") and a.get("href"):
                self.hreflang[a["hreflang"].lower()] = a["href"]
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name == "robots":
                self.robots = a.get("content", "")
            elif name == "description":
                self.meta_description = a.get("content", "")
        elif tag == "title":
            self._title = True
        elif tag in ("h1", "h2", "h3"):
            self._h = [tag, []]
        elif tag == "table":
            self.tables += 1
        elif tag in ("ul", "ol"):
            self.lists += 1
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._ld = []

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append((self._a[0], " ".join("".join(self._a[1]).split()), self._a[2]))
            self._a = None
        elif tag == "title":
            self._title = False
        elif tag in ("h1", "h2", "h3") and self._h is not None:
            self.headings.append((self._h[0], " ".join("".join(self._h[1]).split())))
            self._h = None
        elif tag == "script" and self._ld is not None:
            self.jsonld.append("".join(self._ld))
            self._ld = None
        while self._stack:
            if self._stack.pop() == tag:
                break

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
            return
        if self._title:
            self.title += data
        if self._a is not None:
            self._a[1].append(data)
        if self._h is not None:
            self._h[1].append(data)
        if not (set(self._stack) & (self.SKIP | self.CHROME)) and data.strip():
            self.main_text.append(data.strip())


def parse_page(html: str) -> PageParser:
    p = PageParser()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 — malformed HTML must not abort a crawl
        pass
    return p


def _jsonld_info(blobs: list[str]) -> dict:
    types: list[str] = []
    same_as = author = False

    def walk(o):
        nonlocal same_as, author
        if isinstance(o, dict):
            t = o.get("@type")
            for x in (t if isinstance(t, list) else [t] if t else []):
                if x not in types:
                    types.append(x)
            same_as = same_as or bool(o.get("sameAs"))
            author = author or bool(o.get("author") or o.get("reviewedBy"))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    errors = 0
    for b in blobs:
        try:
            walk(json.loads(b))
        except json.JSONDecodeError:
            errors += 1
    return {"types": types, "has_sameAs": same_as, "has_author_or_reviewer": author, "invalid_blocks": errors}


def page_facts(url: str, fetch=http_fetch) -> dict:
    status, final, ctype, text = fetch(url)
    out = {"url": url, "status": status, "final_url": final}
    if status != 200 or "html" not in ctype.lower():
        out["error"] = text[10:] if text.startswith("__error__") else f"status {status}, content-type {ctype!r}"
        return out
    p = parse_page(text)
    words = " ".join(p.main_text).split()
    h1 = [t for h, t in p.headings if h == "h1"]
    after_h1 = words
    if h1:
        first = h1[0].split()
        for i in range(len(words) - len(first) + 1):
            if words[i:i + len(first)] == first:
                after_h1 = words[i + len(first):]
                break
    out.update({
        "title": " ".join(p.title.split()), "title_length": len(" ".join(p.title.split())),
        "meta_description": p.meta_description, "meta_description_length": len(p.meta_description),
        "lang": p.lang, "canonical": p.canonical, "robots_meta": p.robots, "hreflang": p.hreflang,
        "h1": h1, "headings": [{"level": h, "text": t} for h, t in p.headings],
        "word_count": len(words), "first_45_words": " ".join(after_h1[:45]),
        "tables": p.tables, "lists": p.lists, "jsonld": _jsonld_info(p.jsonld),
    })
    return out


# ------------------------------------------------------------------ robots ---
def _robots(base: str, fetch=http_fetch) -> tuple[int, str, urllib.robotparser.RobotFileParser]:
    status, _, _, text = fetch(base + "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines() if status == 200 else [])
    return status, text, rp


class RobotsGate:
    """Whether this crawler may fetch a URL, per robots.txt of its host (fetched once per host).

    RFC 9309: 4xx = no rules (allowed); 5xx or unreachable = assume everything is disallowed."""

    def __init__(self, fetch=http_fetch, agent: str = USER_AGENT):
        self.fetch, self.agent, self.hosts = fetch, agent, {}

    def check(self, url: str) -> tuple[bool, str | None]:
        pu = urlparse(url)
        base = f"{pu.scheme}://{pu.netloc}"
        if base not in self.hosts:
            status, _, rp = _robots(base, self.fetch)
            self.hosts[base] = (status, rp)
        status, rp = self.hosts[base]
        if status == 0 or status >= 500:
            return False, f"robots.txt unreachable (status {status}): treated as disallow-all"
        if status == 200 and not rp.can_fetch(self.agent, url):
            return False, "disallowed by robots.txt for this crawler"
        return True, None


def _path(u: str) -> str:
    pu = urlparse(u)
    return (pu.path or "/") + (f"?{pu.query}" if pu.query else "")


def robots_report(site: str, fetch=http_fetch, urls: list[str] | None = None) -> dict:
    """robots.txt verdict per search/AI crawler, for the homepage and every page in ``urls``."""
    base = site.rstrip("/")
    status, text, rp = _robots(base, fetch)
    sitemaps = [ln.split(":", 1)[1].strip() for ln in text.splitlines()
                if status == 200 and ln.lower().startswith("sitemap:")]
    paths = list(dict.fromkeys(["/"] + [_path(u) for u in urls or []]))
    unreachable = status == 0 or status >= 500
    bots = []
    for token, op, purpose, kind in AI_BOTS:
        if unreachable:  # Google treats a 5xx/unreachable robots.txt as "disallow all" until it recovers
            bots.append({"token": token, "operator": op, "purpose": purpose, "kind": kind, "homepage_allowed": None,
                         "blocked_paths": None,
                         "verdict": f"UNKNOWN — robots.txt unreachable (status {status}); crawlers may treat the site as blocked"})
            continue
        blocked = [p for p in paths if status == 200 and not rp.can_fetch(token, base + p)]  # 4xx = no rules
        verdict = "ok"
        scope = "the whole site" if "/" in blocked else f"{len(blocked)} of {len(paths)} checked pages"
        if blocked and kind in ("search", "user"):
            verdict = f"VISIBILITY RISK — blocks a search/retrieval crawler on {scope}"
        elif blocked:
            verdict = f"blocked on {scope} (training opt-out; no direct search impact)"
        bots.append({"token": token, "operator": op, "purpose": purpose, "kind": kind,
                     "homepage_allowed": "/" not in blocked, "blocked_paths": blocked, "verdict": verdict})
    return {"robots_txt_status": status, "sitemaps": sitemaps, "paths_checked": paths, "bots": bots,
            "note": "robots.txt only; WAF/CDN bot rules are not visible here — confirm them in the host's firewall."}


# ----------------------------------------------------------------- sitemap ---
def sitemap_urls(site: str, fetch=http_fetch, limit: int = 5000) -> list[str]:
    base = site.rstrip("/")
    queue = robots_report(site, fetch)["sitemaps"] or [base + "/sitemap.xml"]
    seen, urls = set(), []
    while queue and len(urls) < limit and len(seen) < 200:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        status, _, _, text = fetch(sm)
        if status != 200 or not text.strip():
            continue
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            continue
        locs = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
        if root.tag.endswith("sitemapindex"):
            queue.extend(locs)
        else:
            urls.extend(locs)
    return [norm_url(u) for u in urls[:limit]]


# ------------------------------------------------------------- underlinked ---
def underlinked(crawl_res: dict, targets: list[str]) -> list[dict]:
    """Per target: inlinks, depth and why it is under-linked (orphan / weakly linked / deep / not crawled)."""
    pages = crawl_res.get("pages") or {}
    orphans, weak, deep = (set(crawl_res.get(k) or []) for k in ("orphans_vs_sitemap", "weakly_linked", "deep_pages"))
    out = []
    for t in targets:
        u = norm_url(t)
        e = pages.get(u)
        reasons = [r for r, s in (("orphan", orphans), ("weakly_linked", weak), ("deep", deep)) if u in s]
        if e is None and u not in orphans:
            reasons.append("not_crawled")
        out.append({"page": u, "inlinks": (e or {}).get("inlinks"), "depth": (e or {}).get("depth"),
                    "outlinks": len((e or {}).get("outlinks") or []), "underlinked": bool(reasons), "reasons": reasons})
    return sorted(out, key=lambda r: (not r["underlinked"], r["inlinks"] if r["inlinks"] is not None else -1))


# ------------------------------------------------------------------- crawl ---
def crawl(site: str, limit: int = 300, delay: float = 0.5, fetch=http_fetch,
          lang_of=None, sitemap: list[str] | None = None, sleep=time.sleep) -> dict:
    start = norm_url(site if site.endswith("/") else site + "/")
    host = (urlparse(start).hostname or "").lower()
    pages: dict[str, dict] = {}
    redirects: dict[str, str] = {}
    edges: list[dict] = []
    depth = {start: 0}
    q = deque([start])
    gate, skipped = RobotsGate(fetch), {}
    while q and len(pages) < limit:
        url = q.popleft()
        if url in pages or url in redirects or url in skipped:
            continue
        ok, why = gate.check(url)
        if not ok:  # this crawler respects robots.txt: the URL is listed, never fetched
            skipped[url] = why
            continue
        status, final, ctype, text = fetch(url)
        final = norm_url(final)
        if final != url:
            redirects[url] = final
            if final in pages or not _same_site(final, host):
                continue
            depth.setdefault(final, depth[url])
            url = final
        entry = {"status": status, "depth": depth.get(url, 0)}
        pages[url] = entry
        if status != 200 or "html" not in ctype.lower():
            continue
        p = parse_page(text)
        entry.update({"canonical": norm_url(urljoin(url, p.canonical)) if p.canonical else None,
                      "robots_meta": p.robots,
                      "hreflang": {k: norm_url(urljoin(url, v)) for k, v in p.hreflang.items()},
                      "title": " ".join(p.title.split())})
        for href, anchor, nofollow in p.links:
            target = norm_url(urljoin(url, href))
            if urlparse(target).scheme not in ("http", "https") or not _same_site(target, host):
                continue
            edges.append({"from": url, "to": target, "anchor": anchor, "nofollow": nofollow})
            if target not in depth:
                depth[target] = depth.get(url, 0) + 1
                q.append(target)
        if delay:
            sleep(delay)

    def resolved(u: str) -> str:
        seen = set()
        while u in redirects and u not in seen:
            seen.add(u)
            u = redirects[u]
        return u

    inlinks: dict[str, set] = {}
    outlinks: dict[str, set] = {}
    anchors: dict[str, list] = {}
    for e in edges:
        to = resolved(e["to"])
        if to != e["from"]:
            inlinks.setdefault(to, set()).add(e["from"])
            outlinks.setdefault(e["from"], set()).add(to)
            if e["anchor"]:
                anchors.setdefault(to, []).append(e["anchor"])
    for url, entry in pages.items():
        entry["inlinks"] = len(inlinks.get(url, ()))
        entry["outlinks"] = sorted(outlinks.get(url, ()))
        entry["top_anchors"] = sorted(set(anchors.get(url, [])), key=lambda a: -anchors[url].count(a))[:5] if url in anchors else []

    hreflang_issues, canonical_issues = [], []
    for url, e in pages.items():
        alts = e.get("hreflang") or {}
        if not alts:
            continue
        if url not in alts.values():
            hreflang_issues.append({"page": url, "issue": "missing self-referencing hreflang"})
        if "x-default" not in alts:
            hreflang_issues.append({"page": url, "issue": "missing x-default"})
        for lang, alt in alts.items():
            alt = resolved(alt)
            if alt == url or lang == "x-default":
                continue
            other = pages.get(alt)
            if other is None:
                hreflang_issues.append({"page": url, "issue": f"alternate '{lang}' not crawled (unverified)", "target": alt})
            elif other.get("status") != 200:
                hreflang_issues.append({"page": url, "issue": f"alternate '{lang}' returns {other.get('status')}", "target": alt})
            elif url not in (other.get("hreflang") or {}).values():
                hreflang_issues.append({"page": url, "issue": f"alternate '{lang}' does not link back (not reciprocal)", "target": alt})
    for url, e in pages.items():
        can = e.get("canonical")
        if can and can != url:
            item = {"page": url, "canonical": can}
            if lang_of and lang_of(can) != lang_of(url):
                item["issue"] = "canonical points to another language version"
            else:
                item["issue"] = "canonicalised to another URL"
            canonical_issues.append(item)

    reached = set(pages) | set(redirects) | set(skipped)
    orphans = [u for u in (sitemap or []) if u not in reached and resolved(u) not in pages] if sitemap is not None else None
    ok = {u: e for u, e in pages.items() if e.get("status") == 200}
    return {
        "site": start, "pages_crawled": len(pages), "limit_reached": len(pages) >= limit,
        "pages": pages, "redirects": redirects,
        "orphans_vs_sitemap": orphans,
        "weakly_linked": sorted((u for u, e in ok.items() if e["inlinks"] <= 1 and u != start), key=lambda u: pages[u]["inlinks"]),
        "deep_pages": sorted((u for u, e in ok.items() if e["depth"] > 3), key=lambda u: -pages[u]["depth"]),
        "hreflang_issues": hreflang_issues, "canonical_issues": canonical_issues,
        "broken_internal": sorted(u for u, e in pages.items() if e.get("status", 0) >= 400 or e.get("status") == 0),
        "skipped_by_robots": [{"url": u, "reason": r} for u, r in skipped.items()],
    }


# --------------------------------------------------------------------- CLI ---
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["robots", "sitemap", "crawl", "facts", "underlinked"])
    ap.add_argument("--crawl", help="recorded crawl JSON (underlinked)")
    ap.add_argument("--site")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--profile", help="site domain with a rules file (enables language-aware canonical checks)")
    a = ap.parse_args(argv)
    if a.command in ("robots", "sitemap", "crawl") and not a.site:
        ap.error("--site is required")
    if a.command == "robots":
        res = robots_report(a.site, urls=a.url)
    elif a.command == "sitemap":
        res = {"urls": sitemap_urls(a.site, limit=a.limit)}
    elif a.command == "crawl":
        lang_of = None
        if a.profile:
            import rules
            lang_of = rules.load(a.profile).page_language
        res = crawl(a.site, a.limit, a.delay, lang_of=lang_of, sitemap=sitemap_urls(a.site))
    elif a.command == "underlinked":
        if not a.crawl:
            ap.error("--crawl is required for underlinked")
        import gsc_metrics
        res = {"targets": underlinked(gsc_metrics._unwrap(json.loads(Path(a.crawl).read_text())), a.url)}
    else:
        if not a.url:
            ap.error("--url is required for facts")
        gate, pages = RobotsGate(), []
        for u in a.url:  # third-party pages too (SERP competitors): respect each host's robots.txt
            ok, why = gate.check(u)
            pages.append(page_facts(u) if ok else {"url": u, "skipped": why})
        res = {"pages": pages}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
