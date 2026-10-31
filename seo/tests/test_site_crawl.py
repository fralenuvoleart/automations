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
    assert rep["crawler_agent"] == C.USER_AGENT and "crawler_agent" in rep["note"]


def test_robots_5xx_is_unknown_not_allowed():
    rep = C.robots_report("https://x.ge", lambda u: (503, u, "text/plain", ""))
    assert all(b["homepage_allowed"] is None and b["verdict"].startswith("UNKNOWN") for b in rep["bots"])
    rep = C.robots_report("https://x.ge", lambda u: (404, u, "text/plain", ""))
    assert all(b["homepage_allowed"] is True for b in rep["bots"])


def test_sitemap_index_is_followed():
    assert C.sitemap_urls("https://x.ge", fake) == ["https://x.ge/", "https://x.ge/a/", "https://x.ge/orphan/"]


def test_crawl_graph_hreflang_canonicals_orphans():
    res = C.crawl("https://x.ge", limit=50, delay=0, fetch=fake, lang_of=lambda u: "RU" if "/ru/" in u else "EN",
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


def test_robots_verdicts_cover_every_checked_page_not_just_the_homepage():
    site = {"https://y.ge/robots.txt": (200, "text/plain",
                                        "User-agent: GPTBot\nDisallow: /blog/\nUser-agent: OAI-SearchBot\nDisallow: /ru/\n")}
    def f(url):
        status, ctype, text = site.get(url, (404, H, ""))
        return status, url, ctype, text

    rep = C.robots_report("https://y.ge", f, urls=["https://y.ge/blog/post/", "https://y.ge/ru/uslugi/", "https://y.ge/about/"])
    v = {b["token"]: b for b in rep["bots"]}
    assert rep["paths_checked"] == ["/", "/blog/post/", "/ru/uslugi/", "/about/"]
    assert v["GPTBot"]["homepage_allowed"] is True and v["GPTBot"]["blocked_paths"] == ["/blog/post/"]
    assert "1 of 4 checked pages" in v["GPTBot"]["verdict"] and "training" in v["GPTBot"]["verdict"]
    assert v["OAI-SearchBot"]["verdict"].startswith("VISIBILITY RISK") and v["OAI-SearchBot"]["blocked_paths"] == ["/ru/uslugi/"]
    assert v["Googlebot"]["verdict"] == "ok"


def test_crawler_respects_robots_txt_and_lists_what_it_skipped():
    site = dict(SITE)
    site["https://x.ge/robots.txt"] = (200, "text/plain", "User-agent: *\nDisallow: /ru/\nSitemap: https://x.ge/sm.xml\n")
    fetched = []

    def f(url):
        fetched.append(url)
        status, ctype, text = site.get(url, (404, H, ""))
        return status, url, ctype, text

    res = C.crawl("https://x.ge", limit=50, delay=0, fetch=f)
    assert "https://x.ge/ru/a/" not in fetched and "https://x.ge/ru/a/" not in res["pages"]
    assert res["skipped_by_robots"] == [{"url": "https://x.ge/ru/a/", "reason": "disallowed by robots.txt for this crawler"}]
    assert "https://x.ge/a/" in res["pages"]


def test_unreachable_robots_txt_means_nothing_is_fetched():
    calls = []

    def f(url):
        calls.append(url)
        return (503, url, "text/plain", "") if url.endswith("/robots.txt") else (200, url, H, page("x"))

    res = C.crawl("https://z.ge", limit=5, delay=0, fetch=f)
    assert calls == ["https://z.ge/robots.txt"] and res["pages"] == {}
    assert "unreachable" in res["skipped_by_robots"][0]["reason"]


def test_facts_gate_checks_each_host_once():
    seen = []

    def f(url):
        seen.append(url)
        if url == "https://other.com/robots.txt":
            return 200, url, "text/plain", "User-agent: *\nDisallow: /private/\n"
        return 404, url, "text/plain", ""

    gate = C.RobotsGate(f)
    assert gate.check("https://other.com/private/x")[0] is False
    assert gate.check("https://other.com/public/y") == (True, None)
    assert gate.check("https://third.net/a") == (True, None)  # 404 robots.txt = no rules
    assert seen == ["https://other.com/robots.txt", "https://third.net/robots.txt"]


def test_svg_icon_titles_do_not_pollute_the_page_title():
    html = ('<html lang="en"><head><title>Real page title</title></head><body>'
            '<a href="/en/"><svg><title>English</title></svg></a>'
            '<a href="/x/"><svg><title>Telegram</title></svg>Link</a>'
            '</body></html>')
    p = C.parse_page(html)
    assert p.title == "Real page title", p.title          # svg titles never reach the page title
    assert p.links[0][1] == "English"                     # an icon-only link keeps its accessible label
    assert p.links[1][1] == "Link"                        # real text wins over the icon label


if __name__ == "__main__":
    main(globals())
