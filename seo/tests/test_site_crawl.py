"""Tests for seo/site_crawl.py with an in-memory fake site (no network)."""
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import site_crawl as C  # noqa: E402
from _runner import main  # noqa: E402

H = "text/html; charset=utf-8"


def page(body, head=""):
    return f"<html lang='en'><head><title>T</title>{head}</head><body><nav><a href='/'>Home</a></nav>{body}</body></html>"


SITE = {
    "https://x.ge/robots.txt": (200, "text/plain",
                                "User-agent: GPTBot\nDisallow: /\nUser-agent: OAI-SearchBot\nDisallow: /\nSitemap: https://x.ge/sm.xml\n"),
    "https://x.ge/sm.xml": (200, "application/xml",
                            "<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><sitemap><loc>https://x.ge/sm1.xml</loc></sitemap></sitemapindex>"),
    "https://x.ge/sm1.xml": (200, "application/xml",
                             "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://x.ge/</loc></url>"
                             "<url><loc>https://x.ge/a/</loc></url><url><loc>https://x.ge/orphan/</loc></url></urlset>"),
    "https://x.ge/": (200, H, page("<a href='/a/'>Service A</a> <a href='/ru/a/'>RU</a> <a href='/broken/'>x</a>",
                                   "<link rel='alternate' hreflang='en' href='https://x.ge/'><link rel='alternate' hreflang='x-default' href='https://x.ge/'>")),
    "https://x.ge/a/": (200, H, page("<h1>Service A</h1><p>Service A is a registration service that takes five days.</p><table></table>",
                                     "<link rel='canonical' href='https://x.ge/a/'>"
                                     "<link rel='alternate' hreflang='en' href='https://x.ge/a/'>"
                                     "<link rel='alternate' hreflang='ru' href='https://x.ge/ru/a/'>"
                                     "<script type='application/ld+json'>{\"@type\":\"Organization\",\"sameAs\":[\"https://www.wikidata.org/x\"]}</script>")),
    "https://x.ge/ru/a/": (200, H, page("<p>RU</p>", "<link rel='canonical' href='https://x.ge/a/'>"
                                         "<link rel='alternate' hreflang='ru' href='https://x.ge/ru/a/'>")),
    "https://x.ge/broken/": (404, H, ""),
}


def fake(url):
    status, ctype, text = SITE.get(url, (404, H, ""))
    return status, url, ctype, text


def test_robots_matrix_flags_search_bots_only_as_risk():
    rep = C.robots_report("https://x.ge", fake)
    v = {b["token"]: b for b in rep["bots"]}
    assert v["GPTBot"]["homepage_allowed"] is False and "training" in v["GPTBot"]["verdict"]
    assert v["OAI-SearchBot"]["verdict"].startswith("VISIBILITY RISK")
    assert v["Googlebot"]["homepage_allowed"] is True
    assert rep["sitemaps"] == ["https://x.ge/sm.xml"]


def test_robots_5xx_is_unknown_not_allowed():
    rep = C.robots_report("https://x.ge", lambda u: (503, u, "text/plain", ""))
    assert all(b["homepage_allowed"] is None and b["verdict"].startswith("UNKNOWN") for b in rep["bots"])
    rep = C.robots_report("https://x.ge", lambda u: (404, u, "text/plain", ""))
    assert all(b["homepage_allowed"] is True for b in rep["bots"])


def test_sitemap_index_is_followed():
    assert C.sitemap_urls("https://x.ge", fake) == ["https://x.ge/", "https://x.ge/a/", "https://x.ge/orphan/"]


def test_crawl_graph_hreflang_canonicals_orphans():
    res = C.crawl("https://x.ge", limit=50, delay=0, fetch=fake, language_paths={"EN": "/", "RU": "/ru/"},
                  sitemap=C.sitemap_urls("https://x.ge", fake))
    pages = res["pages"]
    assert pages["https://x.ge/a/"]["inlinks"] == 1 and pages["https://x.ge/a/"]["depth"] == 1
    assert "https://x.ge/a/" in pages["https://x.ge/"]["outlinks"]
    assert res["orphans_vs_sitemap"] == ["https://x.ge/orphan/"]
    assert res["broken_internal"] == ["https://x.ge/broken/"]
    issues = {(i["page"], i["issue"]) for i in res["hreflang_issues"]}
    assert ("https://x.ge/a/", "missing x-default") in issues
    assert ("https://x.ge/a/", "alternate 'ru' does not link back (not reciprocal)") in issues
    assert ("https://x.ge/ru/a/", "missing x-default") in issues
    canon = {i["page"]: i["issue"] for i in res["canonical_issues"]}
    assert canon["https://x.ge/ru/a/"] == "canonical points to another language version"


def test_page_facts():
    f = C.page_facts("https://x.ge/a/", fake)
    assert f["h1"] == ["Service A"] and f["first_45_words"].startswith("Service A is a registration")
    assert f["tables"] == 1 and f["jsonld"]["types"] == ["Organization"] and f["jsonld"]["has_sameAs"]
    assert "Home" not in f["first_45_words"]  # nav text excluded
    assert C.page_facts("https://x.ge/broken/", fake)["status"] == 404


def test_norm_url():
    assert C.norm_url("HTTPS://X.GE:443/a/#frag") == "https://x.ge/a/"
    assert C.norm_url("https://x.ge") == "https://x.ge/"


if __name__ == "__main__":
    main(globals())
