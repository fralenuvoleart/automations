"""Tests for seo/report/validate_report.py — mechanical contract checks."""
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))

import build_report  # noqa: E402
import validate_report  # noqa: E402

FIXTURE = SEO / "tests" / "fixtures" / "findings_example.json"
GOOD = json.loads(FIXTURE.read_text())


def _clone():
    return json.loads(json.dumps(GOOD))


def test_valid_findings_pass():
    assert validate_report.validate(GOOD) == []


def test_missing_required_key_fails():
    bad = _clone()
    del bad["verdict"]
    assert any("verdict" in i for i in validate_report.validate(bad))


def test_bad_date_fails():
    bad = _clone()
    bad["as_of"] = "29-10-2026"
    assert any("as_of" in i for i in validate_report.validate(bad))


def test_estimate_label_enforced():
    bad = _clone()
    bad["sections"][1]["body"] = "Traffic value is 1k/month."
    assert any("estimate" in i.lower() for i in validate_report.validate(bad))


def test_unexpanded_token_fails():
    bad = _clone()
    bad["verdict"] = "run {{cap:gsc.query}}"
    assert any("{{cap:" in i for i in validate_report.validate(bad))


def test_url_hallucination_detected():
    bad = _clone()
    bad["sections"][0]["body"] = "see https://example.com/nope"
    issues = validate_report.validate(bad, data_text="no urls here")
    assert any("example.com" in i for i in issues)


def test_url_present_in_data_is_ok():
    bad = _clone()
    bad["sections"][0]["body"] = "see https://example.com/ok"
    assert validate_report.validate(bad, data_text="https://example.com/ok") == []


def test_report_missing_asof_line_fails():
    issues = validate_report.validate(GOOD, report_text="no header here")
    assert any("as-of" in i for i in issues)


def test_built_report_passes_validation():
    md = build_report.build(GOOD, generated_at="2026-10-29T06:00Z")
    assert validate_report.validate(GOOD, report_text=md) == []


def _run_all() -> int:
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
