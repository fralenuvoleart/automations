"""Tests for seo/record.py — evidence recording guards and the end-to-end evidence gate."""
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import orchestrate  # noqa: E402
import record  # noqa: E402
import validate_report as V  # noqa: E402
from _runner import main  # noqa: E402


def _seed(d):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        orchestrate.main(["--skill", "seo-audit", "--days", "28", "--compare", "--as-of", "2026-10-29", "--out-dir", d])
    return json.loads((Path(d) / ".run_state.json").read_text())["window"]


def _expect_error(fn, text):
    try:
        fn()
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert text in str(e), e


def test_records_raw_response_with_full_args():
    with tempfile.TemporaryDirectory() as d:
        w = _seed(d)
        args = {"siteUrl": "sc-domain:x.ge", "startDate": w["startDate"], "endDate": w["endDate"]}
        record.record(Path(d), "page_cur", '{"rows": [{"keys": ["https://x.ge/a/"]}]}', cap="gsc.page", args=args)
        ctx = json.loads((Path(d) / "context.json").read_text())
        call = ctx["calls"][0]
        assert call["cap"] == "gsc.page" and call["args"]["rowLimit"] == 25000 and call["args"]["siteUrl"] == "sc-domain:x.ge"
        assert json.loads((Path(d) / "data" / "page_cur.json").read_text())["rows"][0]["keys"] == ["https://x.ge/a/"]
        record.record(Path(d), "page_cur", '{"rows": []}', cap="gsc.page", args=args)   # re-record replaces
        assert len(json.loads((Path(d) / "context.json").read_text())["calls"]) == 1


def test_guards():
    with tempfile.TemporaryDirectory() as d:
        w = _seed(d)
        run = Path(d)
        _expect_error(lambda: record.record(run, "x", "{}", cap="gsc.nope"), "unknown capability")
        _expect_error(lambda: record.record(run, "x", "{}", cap="gsc.page", args={"rowLimit": 10}), "not runtime args")
        _expect_error(lambda: record.record(run, "x", "{}", cap="gsc.page",
                                            args={"startDate": "2026-01-01", "endDate": "2026-01-28"}), "window")
        _expect_error(lambda: record.record(run, "x", "{}", cap="ga4.channels",
                                            args={"date_ranges": [{"start_date": "2026-01-01", "end_date": "2026-01-02"}]}), "window")
        _expect_error(lambda: record.record(run, "bad name", "{}", source="user"), "--name")
        record.record(run, "cmp", "{}", cap="gsc.page", args={"startDate": w["compareStartDate"], "endDate": w["compareEndDate"]})
        record.record(run, "odd", "{}", cap="gsc.page", args={"startDate": "2026-01-01", "endDate": "2026-01-28"},
                      allow_window="user asked for January")
        record.record(run, "crawl", "not json", source="site_crawl")
        assert json.loads((run / "data" / "crawl.json").read_text()) == {"text": "not json"}


def test_cli_missing_response_file_is_a_clean_error():
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = record.main(["--run-dir", d, "--name", "a", "--cap", "gsc.page", "--response-file", f"{d}/missing.json"])
        assert rc == 1 and err.getvalue().startswith("ERROR")


def test_end_to_end_evidence_gate():
    with tempfile.TemporaryDirectory() as d:
        w = _seed(d)
        findings = {"skill": "seo-audit", "as_of": w["as_of"], "window": w, "verdict": "v",
                    "sections": [{"heading": "H", "body": "https://x.ge/a/ and https://x.ge/made-up/"}]}
        text, n, problems = V.load_evidence(Path(d) / "context.json")
        assert any("no tool responses were recorded" in i for i in V.validate(findings, None, text, n))
        record.record(Path(d), "page_cur", '{"rows": [{"keys": ["https://x.ge/a/"]}]}', cap="gsc.page",
                      args={"startDate": w["startDate"], "endDate": w["endDate"]})
        text, n, problems = V.load_evidence(Path(d) / "context.json")
        issues = V.validate(findings, None, text, n)
        assert issues == ["URL not found in recorded evidence (possible hallucination): https://x.ge/made-up/"]



def test_weekly_run_accepts_each_week_and_rejects_partial_weeks():
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as d:
        with contextlib.redirect_stdout(io.StringIO()):
            orchestrate.main(["--skill", "seo-rank-tracking", "--weeks", "8", "--as-of", "2026-10-30", "--out-dir", d])
        a = {"siteUrl": "sc-domain:x.ge"}
        record.record(Path(d), "query_w8", "{}", cap="gsc.query", args={**a, "startDate": "2026-10-19", "endDate": "2026-10-25"})
        record.record(Path(d), "geo", "{}", cap="gsc.geo_query", args={**a, "startDate": "2026-08-31", "endDate": "2026-10-25"})
        _expect_error(lambda: record.record(Path(d), "bad", "{}", cap="gsc.query",
                                            args={**a, "startDate": "2026-10-20", "endDate": "2026-10-25"}), "its weeks")



def _site_run(root, skill, as_of="2026-10-30", extra=()):
    import contextlib
    import io
    import runs
    runs.settings = lambda: {"run_root": str(root), "cache": True, "retention_days": 180}
    with contextlib.redirect_stdout(io.StringIO()):
        assert orchestrate.main(["--skill", skill, "--site", "pbservices.ge", "--days", "28", "--compare",
                                 "--as-of", as_of, *extra]) == 0
    return runs.run_dir("pbservices.ge", as_of, skill, None if not extra else extra[-1])


def test_cache_reuses_windowed_data_across_skills_and_skips_errors():
    import runs
    saved = runs.settings
    with tempfile.TemporaryDirectory() as root:
        try:
            a, b = _site_run(Path(root), "seo-audit"), _site_run(Path(root), "seo-brand-split")
            win = json.loads((a / ".run_state.json").read_text())["window"]
            args = {"siteUrl": "sc-domain:pbservices.ge", "startDate": win["startDate"], "endDate": win["endDate"]}
            assert record.record_from_cache(b, "query_cur", "gsc.query", args) is None          # miss
            record.record(a, "query_cur", '{"rows": [{"keys": ["x"], "clicks": 1}]}', cap="gsc.query", args=args)
            out = record.record_from_cache(b, "query_cur", "gsc.query", args)                    # hit in another skill's run
            assert json.loads(out.read_text())["rows"][0]["keys"] == ["x"]
            call = json.loads((b / "context.json").read_text())["calls"][0]
            assert call["cached_from"] and call["args"]["rowLimit"] == 25000
            other = {**args, "siteUrl": "sc-domain:other.ge"}
            assert record.record_from_cache(b, "q2", "gsc.query", other) is None                # different args: miss
            record.record(a, "page_cur", '{"error": "quota exceeded"}', cap="gsc.page", args=args)
            assert record.record_from_cache(b, "page_cur", "gsc.page", args) is None             # errors never cached
            record.record(a, "diag", '{"ok": true}', cap="gsc.diagnostics")
            assert record.cached(b, "gsc.diagnostics", {}) is None                                # undated live data: not cached
            _expect_error(lambda: record.record_from_cache(b, "bad", "gsc.query", {**args, "startDate": "2020-01-01"}),
                          "matches neither")                                                      # guards still apply
        finally:
            runs.settings = saved


def test_cache_ttl_for_live_capabilities():
    import datetime as dt
    import runs
    saved = runs.settings
    with tempfile.TemporaryDirectory() as root:
        try:
            a = _site_run(Path(root), "seo-technical")
            args = {"url": "https://pbservices.ge/", "strategy": "mobile"}
            record.record(a, "psi", '{"lighthouseResult": {}}', cap="gsc.pagespeed", args=args)
            assert record.cached(a, "gsc.pagespeed", args) is not None
            later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
            assert record.cached(a, "gsc.pagespeed", args, now=later) is None                     # 7-day TTL
            runs.settings = lambda: {"run_root": root, "cache": False}
            assert record.cached(a, "gsc.pagespeed", args) is None                                # cache switched off
        finally:
            runs.settings = saved


def test_cli_from_cache_exit_codes():
    import contextlib
    import io
    import runs
    saved = runs.settings
    with tempfile.TemporaryDirectory() as root:
        try:
            a = _site_run(Path(root), "seo-audit")
            win = json.loads((a / ".run_state.json").read_text())["window"]
            args = json.dumps({"siteUrl": "sc-domain:pbservices.ge", "startDate": win["startDate"], "endDate": win["endDate"]})
            base = ["--run-dir", str(a), "--cap", "gsc.page", "--name", "page_cur", "--args", args]
            with contextlib.redirect_stdout(io.StringIO()):
                assert record.main([*base, "--from-cache"]) == record.CACHE_MISS
                f = Path(root) / "resp.json"
                f.write_text('{"rows": []}')
                assert record.main([*base, "--response-file", str(f)]) == 0
                assert record.main([*base, "--from-cache"]) == 0
        finally:
            runs.settings = saved



def test_only_final_dated_windows_are_kept_forever():
    import datetime as dt
    today = dt.date(2026, 10, 30)
    gsc, ga4 = {"server": "search-console"}, {"server": "analytics"}
    assert record._final_window(gsc, {"startDate": "2026-09-01", "endDate": "2026-10-27"}, today)        # lag 3
    assert not record._final_window(gsc, {"startDate": "2026-10-01", "endDate": "2026-10-28"}, today)    # may still change
    assert record._final_window(ga4, {"date_ranges": [{"start_date": "2026-10-01", "end_date": "2026-10-28"}]}, today)
    assert not record._final_window(ga4, {"date_ranges": [{"start_date": "28daysAgo", "end_date": "yesterday"}]}, today)
    assert not record._final_window(gsc, {"startDate": "2026-09-01", "endDate": "2026-10-20",
                                          "compareStartDate": "x", "compareEndDate": "2026-08-31"}, today)


def test_a_wrapped_answer_also_gets_a_plain_rows_file():
    """data/<name>.json stays exactly as received; <name>.rows.json is the same answer, readable."""
    import runs
    saved = runs.settings
    with tempfile.TemporaryDirectory() as root:
        try:
            d = _site_run(Path(root), "seo-audit")
            win = json.loads((d / ".run_state.json").read_text())["window"]
            args = {"siteUrl": "sc-domain:pbservices.ge", "startDate": win["startDate"], "endDate": win["endDate"]}
            wrapped = {"content": [{"type": "text", "text": json.dumps({"rows": [{"keys": ["https://x.ge/a/"],
                                                                                  "clicks": 3}]})}],
                       "isError": False}
            record.record(d, "page_cur", json.dumps(wrapped), cap="gsc.page", args=args)
            assert json.loads((d / "data" / "page_cur.json").read_text()) == wrapped          # untouched
            rows = json.loads((d / "data" / "page_cur.rows.json").read_text())
            assert rows["rows"][0]["clicks"] == 3                                              # plain
            call = json.loads((d / "context.json").read_text())["calls"][0]
            assert call["rows_file"] == "data/page_cur.rows.json" and call["file"] == "data/page_cur.json"
            record.record(d, "plain", '{"rows": []}', cap="gsc.page", args=args)               # already plain
            assert not (d / "data" / "plain.rows.json").exists()
            record.record(d, "diag", json.dumps({"content": [{"type": "text", "text": '{"ok": true}'}]}),
                          cap="gsc.diagnostics")                                                # not a table
            assert not (d / "data" / "diag.rows.json").exists()
            record.record(d, "crawl", '{"pages": {}}', source="site_crawl")                     # local step
            assert not (d / "data" / "crawl.rows.json").exists()
        finally:
            runs.settings = saved


if __name__ == "__main__":
    main(globals())

