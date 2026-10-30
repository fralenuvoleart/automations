"""Tests for seo/ga4_metrics.py — GA4 rows classified with the site rules (fixtures: the SEO sheet's GA4 data)."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))
import ga4_metrics as M  # noqa: E402
import rules  # noqa: E402
from _runner import main  # noqa: E402

R = rules.load("pbservices.ge")


def report(rows, snake=True, ranges=False):
    """A GA4 run_report response (snake_case like the GA4 MCP, or camelCase like the REST API)."""
    dims = ["landingPage", "sessionSourceMedium"] + (["dateRange"] if ranges else [])
    k = (lambda s, c: s) if snake else (lambda s, c: c)
    return {k("dimension_headers", "dimensionHeaders"): [{"name": d} for d in dims],
            k("metric_headers", "metricHeaders"): [{"name": m} for m in M.METRICS],
            "rows": [{k("dimension_values", "dimensionValues"): [{"value": v} for v in r[:len(dims)]],
                      k("metric_values", "metricValues"): [{"value": str(v)} for v in r[len(dims):]]} for r in rows]}


CUR = [("/ru/blog/proizvodstvennyj-kalendar-gruzii", "google / organic", 54, 28, 0),
       ("/services/individual-entrepreneur-georgia", "(direct) / (none)", 34, 4, 1),
       ("/ru", "yandex / cpc", 33, 16, 2),
       ("(not set)", "google / organic", 23, 0, 0),
       ("/", "google / organic", 21, 15, 1),
       ("/zh/blog/cost-of-living-in-georgia-prices-zh", "chatgpt.com / ai-assistant", 4, 2, 0)]
PREV = [("/ru/blog/proizvodstvennyj-kalendar-gruzii", "google / organic", 100, 50, 0),
        ("/", "google / organic", 20, 14, 0)]


def test_parse_snake_and_camel_and_date_ranges():
    for snake in (True, False):
        rows = M.parse_rows(report(CUR, snake))
        assert rows[0] == {"landingPage": "/ru/blog/proizvodstvennyj-kalendar-gruzii", "sessionSourceMedium": "google / organic",
                           "sessions": 54.0, "engagedSessions": 28.0, "keyEvents": 0.0}
    wrapped = {"content": [{"type": "text", "text": json.dumps(report(CUR))}]}
    assert len(M.parse_rows(wrapped)) == len(CUR)
    both = [(r[0], r[1], "date_range_0", *r[2:]) for r in CUR] + [(r[0], r[1], "date_range_1", *r[2:]) for r in PREV]
    cur, prev = M.split_ranges(M.parse_rows(report(both, ranges=True)))
    assert len(cur) == len(CUR) and len(prev) == len(PREV)


def test_breakdown_by_channel_page_type_and_language():
    rows, prev = M.parse_rows(report(CUR)), M.parse_rows(report(PREV))
    ch = {r["channel"]: r for r in M.breakdown(R, rows, "channel", prev)["rows"]}
    assert list(ch) == ["AI assistants", "Organic search", "Paid search", "Direct"]
    assert ch["Organic search"]["sessions"] == 98 and ch["Organic search"]["prev_sessions"] == 120
    assert ch["Organic search"]["sessions_change_pct"] == -18.3 and ch["AI assistants"]["prev_sessions"] == 0
    tags = {r["page_tag"]: r for r in M.breakdown(R, rows, "page_tag", organic_only=True)["rows"]}
    assert tags["Blog"]["sessions"] == 54 and tags["Homepage"]["sessions"] == 21 and tags["Other pages"]["sessions"] == 23
    assert "Services" not in tags  # the services visit was direct, not organic
    langs = {r["language"]: r["sessions"] for r in M.breakdown(R, rows, "language")["rows"]}
    assert langs == {"EN": 78, "RU": 87, "ZH": 4}
    tot = M.breakdown(R, rows, "language", organic_only=True)["total"]
    assert tot["sessions"] == 98 and tot["engagementRate"] == round(43 / 98, 3)


def test_channel_breakdown_states_ai_share_and_rates():
    rows, prev = M.parse_rows(report(CUR)), M.parse_rows(report(PREV))
    out = M.breakdown(R, rows, "channel", prev)
    assert out["ai_share_of_organic"]["current"] == round(4 / 98, 4)
    assert out["ai_share_of_organic"]["previous"] == 0.0 and "lower bound" in out["ai_share_of_organic"]["label"]
    ch = {r["channel"]: r for r in out["rows"]}
    assert ch["Paid search"]["key_event_rate"] == round(2 / 33, 4)
    assert ch["Direct"]["session_share"] == round(34 / 169, 4)
    assert "ai_share_of_organic" not in M.breakdown(R, rows, "language")


def test_reconcile_flags_not_set_and_diverging_trends():
    gsc_cur = [{"date": "d", "clicks": 242.0, "impressions": 1, "ctr": 0, "position": 1}]
    gsc_prev = [{"date": "d", "clicks": 500.0, "impressions": 1, "ctr": 0, "position": 1}]
    rows, prev = M.parse_rows(report(CUR)), M.parse_rows(report(PREV))
    res = M.reconcile(R, rows, gsc_cur, prev, gsc_prev)
    assert res["current"]["gsc_clicks"] == 242 and res["current"]["ga4_organic_sessions"] == 98
    assert res["current"]["not_set_share"] == round(23 / 98, 3) and res["current"]["not_set_engagement_rate"] == 0.0
    assert res["gsc_clicks_change_pct"] == -51.6 and res["ga4_organic_sessions_change_pct"] == -18.3
    assert any("(not set)" in f for f in res["flags"]) and any("trends diverge" in f for f in res["flags"])
    calm = M.reconcile(R, prev, gsc_prev, prev, gsc_prev)
    assert calm["flags"] == [] and "compare the trends" in calm["note"]


def test_cli():
    with tempfile.TemporaryDirectory() as d:
        g = Path(d) / "ga4.json"
        g.write_text(json.dumps(report(CUR)))
        t = Path(d) / "totals.json"
        t.write_text(json.dumps({"rows": [{"keys": ["2026-10-19"], "clicks": 242, "impressions": 1009, "ctr": 0.24, "position": 4.8}]}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert M.main(["breakdown", "--site", "pbservices.ge", "--ga4", str(g), "--by", "channel"]) == 0
        assert json.loads(buf.getvalue())["total"]["sessions"] == 169
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert M.main(["reconcile", "--site", "pbservices.ge", "--ga4", str(g), "--gsc-totals", str(t)]) == 0
        assert json.loads(buf.getvalue())["current"]["clicks_per_session"] == round(242 / 98, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            assert M.main(["reconcile", "--site", "pbservices.ge", "--ga4", str(g)]) == 1


if __name__ == "__main__":
    main(globals())
