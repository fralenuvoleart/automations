"""Tests for seo/report/build_report.py — deterministic rendering."""
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))

import build_report  # noqa: E402

FIXTURE = SEO / "tests" / "fixtures" / "findings_example.json"
FINDINGS = json.loads(FIXTURE.read_text())


def test_build_contains_header_asof_and_sections():
    md = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    assert "# seo-audit" in md
    assert "Window 2026-09-30\u21922026-10-27" in md
    assert "generated 2026-10-29T06:00Z" in md
    assert "## Losers" in md
    assert "| query | clicks_delta |" in md
    assert "## Action list" in md
    assert "1. Rewrite the titles" in md


def test_build_is_deterministic():
    a = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    b = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    assert a == b


def test_build_handles_missing_lag_and_sanitizes_tables():
    minimal = {
        "skill": "seo-audit",
        "as_of": "2026-10-29",
        "window": {"startDate": "2026-10-01", "endDate": "2026-10-28"},
        "verdict": "healthy",
        "sections": [{
            "heading": "Sanitized Table",
            "body": "table below",
            "table": [
                {"Query": "best | agency", "Notes": "line1\nline2", "Cost": None}
            ]
        }]
    }
    md = build_report.build(minimal, generated_at="2026-10-29T06:00Z")
    assert "GSC lag 2d" in md
    assert r"best \| agency" in md
    assert "line1 line2" in md
    assert "| None |" not in md


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
