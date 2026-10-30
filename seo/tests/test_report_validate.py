"""Tests for seo/report/validate_report.py — structure, dates, labels, evidence gate, URL matching."""
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import build_report  # noqa: E402
import validate_report as V  # noqa: E402
from _runner import main  # noqa: E402

FIXTURE = SEO / "tests" / "fixtures" / "findings_example.json"
GOOD = json.loads(FIXTURE.read_text())


def _clone():
    return json.loads(json.dumps(GOOD))


def _with_body(body):
    d = _clone()
    d["sections"][0]["body"] = body
    return d


def test_valid_findings_pass():
    assert V.validate(GOOD) == []


def test_missing_required_key_fails():
    bad = _clone()
    del bad["verdict"]
    assert any("verdict" in i for i in V.validate(bad))


def test_bad_date_fails():
    bad = _clone()
    bad["as_of"] = "29-10-2026"
    assert any("as_of" in i for i in V.validate(bad))


def test_window_must_end_before_as_of():
    bad = _clone()
    bad["window"]["endDate"] = bad["as_of"]
    assert any("never include today" in i for i in V.validate(bad))


def test_snapshot_window_may_end_on_as_of():
    d = _clone()
    d["window"] = {"source": "snapshot", "startDate": d["as_of"], "endDate": d["as_of"]}
    assert V.validate(d) == []


def test_start_after_end_and_overlapping_compare_fail():
    bad = _clone()
    bad["window"]["startDate"], bad["window"]["endDate"] = "2026-10-20", "2026-10-01"
    assert any("after endDate" in i for i in V.validate(bad))
    bad = _clone()
    bad["window"].update(compareStartDate="2026-10-01", compareEndDate="2026-10-05")
    assert any("overlaps" in i for i in V.validate(bad))


def test_malformed_input_returns_issues_not_tracebacks():
    for bad in ([], {"skill": "x", "as_of": "2026-10-29", "window": "w", "verdict": "v", "sections": ["oops"]},
                {**_clone(), "actions": "Do X"}, {**_clone(), "unavailable": [{"source": 1}]},
                {**_clone(), "sections": [{"heading": "H", "body": "b", "table": [{"a": {"nested": 1}}]}]}):
        issues = V.validate(bad)
        assert issues and all(isinstance(i, str) for i in issues), bad


def test_estimate_label_enforced():
    bad = _clone()
    bad["sections"][1]["body"] = "Traffic value is 1k/month."
    assert any("estimate" in i.lower() for i in V.validate(bad))


def test_authoring_tokens_fail():
    for tok in ("run {{cap:gsc.query}}", "x <!--cap:gsc.page-->"):
        bad = _clone()
        bad["verdict"] = tok
        assert any("token" in i for i in V.validate(bad))


def test_section_window_shape():
    d = _clone()
    d["sections"][0]["window"] = {"note": "tool lookback: last 28 days"}
    assert V.validate(d) == []
    d["sections"][0]["window"] = {"startDate": "bad"}
    assert any("window" in i for i in V.validate(d))


def test_url_hallucination_detected():
    issues = V.validate(_with_body("see https://example.com/nope"), data_text="no urls here")
    assert any("example.com" in i for i in issues)


def test_url_present_in_data_is_ok():
    assert V.validate(_with_body("see https://example.com/ok"), data_text="https://example.com/ok") == []


def test_cyrillic_url_matches_raw_and_percent_encoded_evidence():
    url = "https://pbservices.ge/ru/внж-грузии/"
    raw = json.dumps({"rows": [{"keys": [url]}]}, ensure_ascii=False)
    enc = json.dumps({"rows": [{"keys": ["https://pbservices.ge/ru/%D0%B2%D0%BD%D0%B6-%D0%B3%D1%80%D1%83%D0%B7%D0%B8%D0%B8/"]}]})
    for data in (raw, enc, json.dumps({"rows": [{"keys": [url]}]})):  # ensure_ascii escapes too
        assert V.validate(_with_body(f"Page {url} lost clicks"), data_text=data) == [], data[:60]


def test_trailing_punctuation_and_trailing_slash_are_normalised():
    data = "https://pbservices.ge/residency/"
    assert V.validate(_with_body("Fix https://pbservices.ge/residency/."), data_text=data) == []
    assert V.validate(_with_body("Fix https://pbservices.ge/residency, then"), data_text=data) == []


def test_ga4_path_only_evidence_is_accepted():
    data = json.dumps({"rows": [{"landingPagePlusQueryString": "/ru/bank-account/"}]})
    assert V.validate(_with_body("See https://pbservices.ge/ru/bank-account/"), data_text=data) == []


def test_ignored_documentation_hosts():
    d = _with_body("docs at https://developers.google.com/search/docs")
    assert V.validate(d, data_text="no urls here") == []


def test_evidence_gate_requires_recorded_calls():
    issues = V.validate(_with_body("see https://example.com/x"), data_text="{}", evidence_calls=0)
    assert any("no tool responses were recorded" in i for i in issues)


def test_load_evidence_reads_index_and_files():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    (tmp / "data" / "page_cur.json").write_text('{"rows": [{"keys": ["https://example.com/a"]}]}')
    (tmp / "context.json").write_text(json.dumps({"calls": [{"name": "page_cur", "file": "data/page_cur.json"},
                                                            {"name": "gone", "file": "data/gone.json"}]}))
    text, n, problems = V.load_evidence(tmp / "context.json")
    assert n == 2 and "https://example.com/a" in text
    assert any("gone.json" in p for p in problems)
    _, _, problems = V.load_evidence(tmp / "missing.json")
    assert problems and "not found" in problems[0]


def test_heading_with_surrounding_spaces_validates_after_build():
    d = _clone()
    d["sections"][0]["heading"] = " Losers "
    assert V.validate(d, report_text=build_report.build(d, generated_at="X")) == []


def test_report_checks():
    assert any("as-of" in i for i in V.validate(GOOD, report_text="no header here"))
    md = build_report.build(GOOD, generated_at="2026-10-29T06:00Z")
    assert V.validate(GOOD, report_text=md) == []



def test_window_weeks_must_sit_inside_the_window():
    d = _clone()
    d["window"]["weeks"] = [{"startDate": d["window"]["startDate"], "endDate": d["window"]["endDate"]}]
    assert V.validate_structure(d) == []
    d["window"]["weeks"] = [{"startDate": "2020-01-01", "endDate": "2020-01-07"}]
    assert any("window.weeks[0]" in i for i in V.validate_structure(d))



def test_structured_actions_are_validated():
    d = _clone()
    d["actions"] = ["legacy text action",
                    {"action": "Add internal links to the target page", "impact": "high", "effort": "low",
                     "page": "https://pbservices.ge/services/bank-account-georgia/", "why": "wrong page ranks", "est_clicks": 12}]
    assert V.validate_structure(d) == []
    d["actions"] = [{"action": "", "impact": "huge", "effort": "low", "page": "/x/", "est_clicks": -1, "owner": "me"}]
    msg = " | ".join(V.validate_structure(d))
    for part in ("non-empty 'action'", "impact must be", "absolute URL", "est_clicks", "unknown key 'owner'"):
        assert part in msg, part


if __name__ == "__main__":
    main(globals())
