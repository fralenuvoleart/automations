"""Tests for seo/report/build_report.py — deterministic rendering, refusal of malformed findings."""
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import build_report  # noqa: E402
from _runner import main  # noqa: E402

GOOD = json.loads((SEO / "tests" / "fixtures" / "findings_example.json").read_text())


def test_build_contains_header_asof_and_sections():
    md = build_report.build(GOOD, generated_at="2026-10-29T06:00Z")
    assert "# seo-audit" in md
    assert "Window 2026-09-30→2026-10-27" in md and "GSC lag 2d" in md
    assert "generated 2026-10-29T06:00Z" in md
    assert "## Losers" in md and "| query | clicks_delta |" in md
    assert "## Action list" in md and "1. Rewrite the titles" in md


def test_build_is_deterministic():
    assert build_report.build(GOOD, generated_at="X") == build_report.build(GOOD, generated_at="X")


def test_build_sanitizes_tables_and_defaults_lag():
    minimal = {"skill": "seo-audit", "as_of": "2026-10-29",
               "window": {"startDate": "2026-10-01", "endDate": "2026-10-26"}, "verdict": "healthy",
               "sections": [{"heading": "Sanitized Table", "body": "table below",
                             "table": [{"Query": "best | agency", "Notes": "line1\nline2", "Cost": None}]}]}
    md = build_report.build(minimal, generated_at="2026-10-29T06:00Z")
    assert "GSC lag 3d" in md
    assert r"best \| agency" in md and "line1 line2" in md and "| None |" not in md


def test_build_refuses_malformed_findings():
    for bad in ({**GOOD, "sections": ["oops"]}, {k: v for k, v in GOOD.items() if k != "window"},
                {**GOOD, "sections": [{"heading": "H"}]}):
        try:
            build_report.build(bad, generated_at="X")
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "invalid findings" in str(e)


def test_section_window_snapshot_and_coverage_wording():
    d = json.loads(json.dumps(GOOD))
    d["window"] = {"source": "snapshot", "startDate": "2026-10-29", "endDate": "2026-10-29"}
    d["sections"][0]["window"] = {"note": "PageSpeed run 2026-10-29; CrUX = trailing 28 days"}
    d["coverage"] = {"basis": "gsc_impressions", "priority_keywords": ["a", "b"], "covered": ["a"],
                     "missing": ["b"], "by_language": {"en": {"total": 2, "covered": 1, "missing": 1}}}
    md = build_report.build(d, generated_at="X")
    assert "Snapshot as of 2026-10-29 (live data)" in md
    assert "_Data window: PageSpeed run 2026-10-29" in md
    assert "1 with impressions in the window" in md and "**No impressions:**" in md



def test_definitions_cover_only_terms_used():
    md = build_report.build(GOOD, generated_at="X")
    assert "## Definitions" in md and "- **Clicks** —" in md
    assert "**Engagement rate**" not in md  # not mentioned in this report
    assert build_report.definitions("Sessions fell; engagement rate held.").count("- **") == 2
    assert build_report.definitions("Nothing measurable here.") == ""
    assert "Tracked keywords" not in build_report.definitions("a core idea")  # type names match case-sensitively


if __name__ == "__main__":
    main(globals())
