"""Tests for seo/gsc_metrics.py — parsing, aggregation, truncation, every analysis and the CLI."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import gsc_metrics as G  # noqa: E402
from _runner import main  # noqa: E402


def R(**k):
    return {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0, **k}


def test_parse_shapes():
    keys = {"rows": [{"keys": ["q1"], "clicks": 2, "impressions": 10, "ctr": 0.2, "position": 3}]}
    named = [{"query": "q1", "clicks": "2", "impressions": "10", "ctr": "20%", "position": "3"}]
    wrapped = {"content": [{"type": "text", "text": json.dumps(keys)}]}
    for p in (keys, named, wrapped):
        rows = G.parse_rows(p, ["query"])
        assert rows == [{"query": "q1", "clicks": 2.0, "impressions": 10.0, "ctr": 0.2, "position": 3.0}], p
    assert G.parse_rows({}, ["query"]) == []
    assert G.parse_rows({"result": keys}, ["query"])[0]["query"] == "q1"   # FastMCP structured content
    for bad in ({"weird": 1}, {"rows": [{"keys": ["a", "b"]}]}, [{"page": "x"}]):
        try:
            G.parse_rows(bad, ["query"])
            raise AssertionError(bad)
        except ValueError:
            pass


def test_aggregate_is_impression_weighted():
    agg = G.aggregate([R(query="a", clicks=1, impressions=100, position=2), R(query="a", clicks=9, impressions=300, position=10)],
                      lambda r: r["query"])["a"]
    assert agg["clicks"] == 10 and agg["position"] == 8.0 and agg["ctr"] == 10 / 400


def test_truncation_and_movers_cutoff():
    full = [R(query=f"q{i}", impressions=100, position=5) for i in range(G.ROW_LIMIT)]
    assert G.is_truncated(full)
    prev = [R(query="gone", impressions=500, position=4, clicks=20)]
    cur = full
    out = G.movers(cur, prev)
    assert out["lost"] == [] and out["beyond_row_cutoff"][0]["query"] == "gone"
    assert out["meta"]["truncated"]["current"] is True


def test_movers_classify_and_sort():
    prev = [R(query="money", clicks=50, impressions=1000, position=4), R(query="noise", clicks=1, impressions=60, position=40),
            R(query="up", clicks=5, impressions=200, position=9), R(query="dropped", clicks=8, impressions=300, position=7)]
    cur = [R(query="money", clicks=20, impressions=900, position=7), R(query="noise", clicks=0, impressions=60, position=80),
           R(query="up", clicks=30, impressions=400, position=3), R(query="fresh", clicks=3, impressions=80, position=12)]
    out = G.movers(cur, prev)
    assert [r["query"] for r in out["losers"]] == ["money", "noise"]  # sorted by clicks lost
    assert [r["query"] for r in out["winners"]] == ["up"]
    assert [r["query"] for r in out["new"]] == ["fresh"] and [r["query"] for r in out["lost"]] == ["dropped"]


def test_striking_low_ctr_and_curve():
    rows = [R(query=f"s{i}", impressions=600, clicks=6, position=1.2) for i in range(3)]  # site bucket 1: 1% CTR
    rows += [R(query="strike", impressions=900, clicks=9, position=12), R(query="tiny", impressions=10, position=12)]
    curve = G.ctr_curve(rows)
    bench = G.load_benchmark()
    assert curve["1"]["source"] == "site" and curve["1"]["ctr"] == 0.01
    assert curve["2"]["source"] == "benchmark" and curve["2"]["ctr"] == bench["positions"]["2"]
    assert [r["query"] for r in G.striking(rows)] == ["strike"]
    low = G.low_ctr([R(query="bad", impressions=1000, clicks=5, position=2.1)], curve)
    assert low and low[0]["expected_source"] == "benchmark" and low[0]["missed_clicks_est"] > 0
    assert G.expected_ctr(30.0, curve) == (None, "insufficient data")


def test_curve_prefers_the_sites_own_data_then_its_last_12_months_then_the_benchmark():
    run = [R(query="a", impressions=600, clicks=60, position=1.0)]                      # bucket 1 from the run
    year = [R(query="a", impressions=5000, clicks=100, position=1.0),                   # ignored: run has bucket 1
            R(query="b", impressions=800, clicks=40, position=2.0),                     # bucket 2 from 12 months
            R(query="c", impressions=100, clicks=9, position=3.0),                      # too few: benchmark
            R(query="pb services", impressions=900, clicks=500, position=4.0),          # brand: excluded
            R(query="d", impressions=700, clicks=7, position=8.0)]                      # bucket 8 (no benchmark)
    curve = G.ctr_curve(run, lambda q: q.startswith("pb"), longer_rows=year)
    assert {b: e["source"] for b, e in curve.items()} == {"1": "site", "2": "site_12m", "3": "benchmark",
                                                           "4": "benchmark", "5": "benchmark", "8": "site_12m"}
    assert curve["1"]["ctr"] == 0.1 and curve["2"]["ctr"] == 0.05
    basis = G.curve_basis(curve, longer=True)
    assert basis["buckets_by_source"]["site_12m"] == ["2", "8"] and basis["site_12m_supplied"] is True
    assert "post-AI-Overviews" in basis["benchmark"]["label"] and basis["benchmark"]["published"]
    only_site = G.ctr_curve(run, benchmark={"positions": {}})
    assert list(only_site) == ["1"] and "benchmark" not in G.curve_basis(only_site)


def test_benchmark_file_is_valid_and_post_ai_overviews():
    import datetime as dt
    b = G.load_benchmark()
    assert int(b["published"][:4]) >= 2025 and "AI Overviews" in b["source"] + b.get("ai_overviews", "")
    assert all(0 < v < 1 for v in b["positions"].values())
    assert G.benchmark_status(b, dt.date(2025, 9, 1))["stale"] is False
    st = G.benchmark_status(b, dt.date(2030, 1, 1))
    assert st["stale"] is True and st["age_months"] > b["max_age_months"]
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "b.json"
        bad.write_text(json.dumps({**b, "positions": {"1": 27.6}}))  # a percentage, not a ratio
        try:
            G.load_benchmark(bad)
            raise AssertionError("percent values must be rejected")
        except ValueError as e:
            assert "bad position" in str(e)


def test_brand_queries_excluded_from_curve():
    rows = [R(query="pb services", impressions=1000, clicks=600, position=1)]
    assert G.ctr_curve(rows, lambda q: q.startswith("pb"))["1"]["source"] == "benchmark"


def test_cannibalization():
    rows = [R(query="q", page="/a", impressions=500, clicks=10, position=5), R(query="q", page="/b", impressions=300, clicks=4, position=8),
            R(query="q", page="/c", impressions=10, position=30), R(query="solo", page="/a", impressions=900, position=2)]
    out = G.cannibalization(rows)
    assert len(out) == 1 and [p["page"] for p in out[0]["pages"]] == ["/a", "/b"]


def test_decay_classes_are_exclusive_with_precedence():
    prev = [R(page=p, clicks=100, impressions=1000, position=5) for p in ("rank", "demand", "ctr", "gone", "ok")]
    cur = [R(page="rank", clicks=40, impressions=500, position=7),      # position worse AND impressions down
           R(page="demand", clicks=40, impressions=500, position=5.2),
           R(page="ctr", clicks=40, impressions=1000, position=5),
           R(page="ok", clicks=95, impressions=1000, position=5)]
    res = G.decay(cur, prev)
    cls = {p["page"]: p["class"] for p in res["pages"]}
    assert cls == {"rank": "ranking_loss", "demand": "demand_drop", "ctr": "ctr_loss", "gone": "vanished"}


def test_brand_split_by_language_with_unattributed():
    rows = [R(query="pb services", page="https://x.ge/", clicks=10, impressions=20, position=1),
            R(query="внж грузии", page="https://x.ge/ru/vnzh/", clicks=5, impressions=200, position=6),
            R(query="tax georgia", page="https://x.ge/tax/", clicks=3, impressions=100, position=9)]
    import rules
    r = rules.load("pbservices.ge")
    out = G.brand_split(rows, r.is_brand, r.page_language, totals={"clicks": 30, "impressions": 400})
    assert out["by_language"]["RU"]["non_brand"]["clicks"] == 5
    assert out["by_language"]["EN"]["brand"]["clicks"] == 10 and out["by_language"]["EN"]["non_brand"]["clicks"] == 3
    assert out["unattributed"]["clicks"] == 12 and out["unattributed"]["clicks_share"] == 0.4
    assert out["top_non_brand"][0]["query"] == "внж грузии"


def test_value_model_and_topic():
    curve = {"3": {"ctr": 0.11, "source": "benchmark"}}
    q = [R(query="tax residency georgia", clicks=2, impressions=200, position=12)]
    items = [{"keyword": "Tax Residency Georgia", "avg_monthly_searches": 1000, "low_top_of_page_bid": 1.0, "high_top_of_page_bid": 3.0}]
    v = G.value_model(items, q, curve, 3)[0]
    assert v["cpc_mid"] == 2.0 and v["est_monthly_clicks_gain"] == 100.0 and v["est_monthly_value"] == 200.0
    assert v["label"] == "estimate" and v["target_ctr_source"] == "benchmark"
    rows = [R(query="внж грузии для россиян", page="/ru/a", impressions=50), R(query="банки грузии", page="/ru/b", impressions=9)]
    assert [r["query"] for r in G.topic(rows, ["внж", "грузи"])] == ["внж грузии для россиян"]


def test_cli_reads_dims_from_recorded_context():
    with tempfile.TemporaryDirectory() as d:
        run = Path(d)
        (run / "data").mkdir()
        for name, rows in (("page_cur", [["/a", 10, 100, 0.1, 3]]), ("page_prev", [["/a", 100, 1000, 0.1, 3]])):
            (run / "data" / f"{name}.json").write_text(json.dumps({"rows": [
                {"keys": [r[0]], "clicks": r[1], "impressions": r[2], "ctr": r[3], "position": r[4]} for r in rows]}))
        (run / "context.json").write_text(json.dumps({"calls": [
            {"name": n, "file": f"data/{n}.json", "args": {"dimensions": ["page"]}} for n in ("page_cur", "page_prev")]}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = G.main(["decay", "--cur", str(run / "data/page_cur.json"), "--prev", str(run / "data/page_prev.json")])
        assert rc == 0 and json.loads(buf.getvalue())["pages"][0]["class"] == "demand_drop"



def test_site_without_rules_still_runs_non_brand_analyses():
    import rules
    saved = rules.load
    rules.load = lambda site: (_ for _ in ()).throw(FileNotFoundError(site))
    try:
        thr, site_rules = G._site("pbservices.ge")
        assert site_rules is None and thr["min_impressions"] == G.DEFAULTS["min_impressions"]
    finally:
        rules.load = saved


def test_inspection_summary_counts_states_mismatches_and_dedupes():
    def res(url, verdict, state, google=None, declared=None):
        r = {"verdict": verdict, "coverageState": state, "indexingState": "INDEXING_ALLOWED"}
        if google:
            r.update({"googleCanonical": google, "userCanonical": declared})
        return {"url": url, "inspectionResult": {"indexStatusResult": r}}
    batch1 = {"content": [{"type": "text", "text": json.dumps({"results": [
        res("https://x.ge/a", "PASS", "Submitted and indexed", "https://x.ge/a", "https://x.ge/a/"),
        res("https://x.ge/b", "NEUTRAL", "Crawled - currently not indexed")]})}]}
    batch2 = [res("https://x.ge/c", "PASS", "Submitted and indexed", "https://x.ge/en/c", "https://x.ge/c"),
              res("https://x.ge/b", "NEUTRAL", "Crawled - currently not indexed")]  # duplicate URL
    with tempfile.TemporaryDirectory() as d:
        files = []
        for i, b in enumerate((batch1, batch2)):
            f = Path(d) / f"inspect_{i}.json"
            f.write_text(json.dumps(b))
            files.append(str(f))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert G.main(["inspection", "--inspect", *files]) == 0
    out = json.loads(buf.getvalue())
    assert out["inspected"] == 3 and out["not_indexed_share"] == 0.333
    assert out["by_coverage_state"][0] == {"coverageState": "Submitted and indexed", "urls": 2, "share": 0.667}
    assert [m["url"] for m in out["canonical_mismatch"]] == ["https://x.ge/c"]  # trailing slash is not a mismatch
    assert out["not_indexed"] == [{"url": "https://x.ge/b", "coverage_state": "Crawled - currently not indexed"}]


def test_cli_curve_with_12_months_and_benchmark_check():
    with tempfile.TemporaryDirectory() as d:
        run = Path(d) / "q.json"
        year = Path(d) / "q12.json"
        run.write_text(json.dumps({"rows": [{"keys": ["a"], "clicks": 60, "impressions": 600, "ctr": 0.1, "position": 1}]}))
        year.write_text(json.dumps({"rows": [{"keys": ["b"], "clicks": 40, "impressions": 800, "ctr": 0.05, "position": 2}]}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert G.main(["curve", "--query", str(run), "--curve-query", str(year)]) == 0
        out = json.loads(buf.getvalue())
        assert out["curve"]["2"]["source"] == "site_12m" and out["basis"]["site_12m_supplied"] is True
        with contextlib.redirect_stdout(io.StringIO()):
            assert G.main(["benchmark", "--check"]) in (0, 2)


if __name__ == "__main__":
    main(globals())
