"""Per-skill findings-schema coverage: every seo-* skill validates and builds."""
import datetime as dt
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))

import build_report  # noqa: E402
import validate_report  # noqa: E402
import window  # noqa: E402

SKILLS = SEO.parent / ".agents" / "skills"


def _names() -> list[str]:
    return sorted(p.parent.name for p in SKILLS.glob("seo-*/SKILL.md"))


def _doc(name: str) -> dict:
    win = window.resolve(28, dt.date(2026, 10, 29), lag=2, compare=True)
    return {
        "skill": name,
        "as_of": win["as_of"],
        "window": win,
        "verdict": "ok",
        "sections": [{"heading": "Overview", "body": "nothing notable."}],
        "actions": ["none"],
    }


def test_seo_skills_present():
    names = _names()
    assert len(names) >= 8, names
    for required in (
        "seo-audit", "seo-ai-visibility", "seo-backlink-check", "seo-competitor-gap",
        "seo-content-brief", "seo-keyword-research", "seo-rank-tracking", "seo-vs-ads",
    ):
        assert required in names, f"missing {required}"


def test_every_skill_findings_validate():
    for n in _names():
        assert validate_report.validate(_doc(n)) == [], n


def test_every_skill_builds_and_revalidates():
    for n in _names():
        md = build_report.build(_doc(n), generated_at="2026-10-29T06:00Z")
        assert validate_report.validate(_doc(n), report_text=md) == [], n


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
