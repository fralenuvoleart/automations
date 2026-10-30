"""Tests for the small helper commands the data plans call (targets, samples, SERP URLs, representatives)."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))
import dfs_metrics  # noqa: E402
import ga4_metrics  # noqa: E402
import gsc_metrics as G  # noqa: E402
import rules  # noqa: E402
import site_crawl  # noqa: E402
from _runner import main  # noqa: E402

U = "https://pbservices.ge"
R = rules.load("pbservices.ge")


def _page_rows(pairs):
    return [{"page": p, "clicks": c, "impressions": i, "ctr": c / i if i else 0, "position": 5.0} for p, c, i in pairs]


def _cli(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert fn(argv) == 0
    return json.loads(buf.getvalue())


def test_gsc_top_pages_merges_jump_links_and_ranks():
    rows = _page_rows([(f"{U}/a/", 5, 100), (f"{U}/a/#faq", 4, 50), (f"{U}/b/", 8, 20), (f"{U}/c/", 1, 500)])
    by_clicks = G.top_pages(rows, "clicks", 2)
    assert [p["page"] for p in by_clicks] == [f"{U}/a/", f"{U}/b/"] and by_clicks[0]["clicks"] == 9
    assert G.top_pages(rows, "impressions", 1)[0]["page"] == f"{U}/c/"


def test_gsc_unseen_keeps_sitemap_order_and_limit():
    rows = _page_rows([(f"{U}/a/", 1, 10), (f"{U}/b/", 0, 0)])
    listed = [f"{U}/b/", f"{U}/a/", f"{U}/c/", f"{U}/d/"]
    assert G.unseen(rows, listed, 2) == [f"{U}/b/", f"{U}/c/"]
    with tempfile.TemporaryDirectory() as d:
        pf, uf = Path(d) / "page.json", Path(d) / "sitemap.json"
        pf.write_text(json.dumps({"rows": [{"keys": [f"{U}/a/"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 3}]}))
        uf.write_text(json.dumps({"urls": listed}))
        assert _cli(G.main, ["unseen", "--page", str(pf), "--urls", str(uf)])["urls"] == [f"{U}/b/", f"{U}/c/", f"{U}/d/"]


def test_underlinked_reasons():
    crawl = {"pages": {f"{U}/a/": {"inlinks": 0, "depth": 1, "outlinks": [f"{U}/"]},
                       f"{U}/deep/": {"inlinks": 3, "depth": 5, "outlinks": []},
                       f"{U}/ok/": {"inlinks": 9, "depth": 1, "outlinks": [f"{U}/a/", f"{U}/"]}},
             "orphans_vs_sitemap": [f"{U}/orphan/"], "weakly_linked": [f"{U}/a/"], "deep_pages": [f"{U}/deep/"]}
    out = {r["page"]: r for r in site_crawl.underlinked(crawl, [f"{U}/ok/", f"{U}/a/#x", f"{U}/deep/", f"{U}/orphan/", f"{U}/new/"])}
    assert out[f"{U}/a/"]["reasons"] == ["weakly_linked"] and out[f"{U}/a/"]["outlinks"] == 1
    assert out[f"{U}/deep/"]["reasons"] == ["deep"]
    assert out[f"{U}/orphan/"]["reasons"] == ["orphan"]
    assert out[f"{U}/new/"]["reasons"] == ["not_crawled"]
    assert out[f"{U}/ok/"]["underlinked"] is False


def test_serp_urls_from_dataforseo_and_web_search():
    dfs = {"tasks": [{"result": [{"items": [{"type": "featured_snippet", "url": "https://x.com/f"},
                                            {"type": "organic", "url": "https://a.com/"},
                                            {"type": "organic", "url": "https://a.com/"},
                                            {"type": "organic", "url": "https://b.com/"},
                                            {"type": "organic", "url": "https://c.com/"}]}]}]}
    assert dfs_metrics.serp_urls(dfs, 2) == ["https://a.com/", "https://b.com/"]
    web = {"content": [{"type": "text", "text": json.dumps({"results": [{"url": "https://w.com/1"}, {"url": "https://w.com/2"}]})}]}
    assert dfs_metrics.serp_urls(web) == ["https://w.com/1", "https://w.com/2"]


def test_ga4_top_pages_and_misses():
    rows = [{"landingPage": "/", "sessionSourceMedium": "chatgpt.com / referral", "sessions": 5.0, "engagedSessions": 1.0, "keyEvents": 1.0},
            {"landingPage": "/blog/x/", "sessionSourceMedium": "chatgpt.com / referral", "sessions": 9.0, "engagedSessions": 2.0, "keyEvents": 0.0},
            {"landingPage": "(not set)", "sessionSourceMedium": "chatgpt.com / referral", "sessions": 50.0, "engagedSessions": 0.0, "keyEvents": 0.0}]
    top = ga4_metrics.top_pages(R, rows, 3)
    assert [t["page"] for t in top] == [f"{U}/blog/x/", f"{U}/"]  # absolute URLs, "(not set)" skipped
    gsc = _page_rows([(f"{U}/", 50, 500), (f"{U}/services/x/", 40, 400), (f"{U}/blog/x/", 30, 300), (f"{U}/ru/", 20, 200)])
    assert [m["page"] for m in ga4_metrics.misses(R, rows, gsc, 5)] == [f"{U}/services/x/", f"{U}/ru/"]


def test_representatives_cover_every_page_type_and_language():
    rows = _page_rows([(f"{U}/", 100, 1000), (f"{U}/services/individual-entrepreneur-georgia/", 80, 800),
                       (f"{U}/blog/bank-account-georgia/", 60, 600), (f"{U}/ru/", 50, 500),
                       (f"{U}/ru/blog/x/", 40, 400), (f"{U}/ar/", 3, 30), (f"{U}/zh/", 2, 20), (f"{U}/about/", 1, 10)])
    reps = R.representatives(rows)
    assert {r["tag"] for r in reps} == set(R.sections())
    assert {r["language"] for r in reps} == set(R.languages())
    assert len(reps) == len({r["page"] for r in reps}) <= len(R.sections()) + len(R.languages())
    assert reps[0]["page"] == f"{U}/"  # top-clicked first


if __name__ == "__main__":
    main(globals())
