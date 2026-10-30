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


if __name__ == "__main__":
    main(globals())
