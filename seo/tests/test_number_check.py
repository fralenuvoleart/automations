"""Tests for seo/report/number_check.py — figures in findings must trace to evidence or computed outputs."""
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import number_check as N  # noqa: E402
import orchestrate  # noqa: E402
import validate_report as V  # noqa: E402
from _runner import main  # noqa: E402

AS_OF = dt.date(2026, 10, 30)


def _findings(run_dir: Path, verdict: str, body: str = "See table.", table=None, actions=None) -> dict:
    f = json.loads((run_dir / "findings.json").read_text())
    f["verdict"] = verdict
    f["sections"] = [{"heading": "Overview", "body": body, **({"table": table} if table else {})}]
    if actions is not None:
        f["actions"] = actions
    return f


def _run(evidence: dict | None = None, computed: dict | None = None) -> Path:
    rd = orchestrate.seed("seo-audit", site="pbservices.ge", out_dir=tempfile.mkdtemp(), as_of=AS_OF, compare=True)
    calls = []
    for name, payload in (evidence or {}).items():
        (rd / "data" / f"{name}.json").write_text(json.dumps(payload))
        calls.append({"name": name, "cap": "gsc.page", "file": f"data/{name}.json"})
    (rd / "context.json").write_text(json.dumps({"calls": calls}))
    if computed:
        (rd / "computed").mkdir()
        for name, payload in computed.items():
            (rd / "computed" / f"{name}.json").write_text(json.dumps(payload))
    return rd


def test_tokens_skip_noise_and_keep_findings():
    t = ("Clicks fell 18.4% to 1,234 (−276) over 28 days in the top 20; `x 999`; 2026-10-27; year 2025; "
         "https://pbservices.ge/en/page-12345/; GA4 H1; 7 pages; title 60 characters; 1.4k/month")
    got = [w for w, _, _ in N.tokens(t)]
    assert got == ["18.4%", "1,234", "−276", "1.4k"], got


def test_precision_and_rounding_tolerance():
    idx = N.Index([1234, 0.1226, 3400, 1987, 12345])
    assert idx.has(*N.tokens("12.3%")[0][1:])            # ratio written as %
    assert not idx.has(*N.tokens("12.4%")[0][1:])
    assert idx.has(*N.tokens("3.4 s")[0][1:])             # ms written as s
    assert idx.has(*N.tokens("1,234")[0][1:])
    assert not idx.has(*N.tokens("1,235")[0][1:])
    assert idx.has(*N.tokens("2,000")[0][1:])             # 1,987 rounded to two significant figures
    assert idx.has(*N.tokens("12k")[0][1:])
    assert not idx.has(*N.tokens("1,300")[0][1:])


def test_numbers_from_evidence_and_computed_pass():
    rd = _run(evidence={"page_cur": {"rows": [{"keys": ["https://pbservices.ge/"], "clicks": 1234, "ctr": 0.0321}]}},
              computed={"compare": {"clicks": {"current": 1234, "previous": 1510, "delta": -276, "delta_pct": -18.28},
                                    "orphans": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n"]}})
    f = _findings(rd, "Clicks fell 18.3% (−276) to 1,234; CTR 3.2%.", body="14 orphan pages found.",
                  table=[{"page": "https://pbservices.ge/", "clicks": 1234, "previous": "1,510"}])
    assert N.check(f, N.Index.from_run(rd)) == []


def test_invented_numbers_are_flagged_with_location():
    rd = _run(evidence={"page_cur": {"rows": [{"clicks": 1234}]}})
    f = _findings(rd, "Clicks reached 1,234.", body="Impressions grew 37.5% to 48,213.",
                  actions=[{"action": "Refresh the guide", "impact": "high", "effort": "low",
                            "page": "https://pbservices.ge/", "why": "lost 912 clicks", "est_clicks": 640}])
    issues = N.check(f, N.Index.from_run(rd))
    assert len(issues) == 4, issues
    assert any("'37.5%' in sections[0].body" in i for i in issues)
    assert any("'48,213' in sections[0].body" in i for i in issues)
    assert any("'912' in actions[0].why" in i for i in issues)
    assert any("'640' in actions[0].est_clicks" in i for i in issues)


def test_site_thresholds_and_window_are_allowed():
    rd = _run()
    thr = __import__("site_profile").thresholds("pbservices.ge")
    f = _findings(rd, f"Pages with at least {thr['min_impressions']} impressions over the last 28 days; "
                      f"striking distance is positions {thr['striking_min']}–{thr['striking_max']}; 404 and 301 checked.")
    assert N.check(f, N.Index.from_run(rd)) == []


def test_validate_cli_runs_the_number_check():
    rd = _run(evidence={"page_cur": {"rows": [{"keys": ["https://pbservices.ge/"], "clicks": 1234}]}})
    good = _findings(rd, "Clicks reached 1,234 on https://pbservices.ge/.")
    bad = _findings(rd, "Clicks reached 4,321 on https://pbservices.ge/.")
    for f, rc in ((good, 0), (bad, 1)):
        (rd / "findings.json").write_text(json.dumps(f))
        r = subprocess.run([sys.executable, str(SEO / "report" / "validate_report.py"), "--findings",
                            str(rd / "findings.json"), "--data", str(rd / "context.json")],
                           capture_output=True, text=True)
        assert r.returncode == rc, r.stdout + r.stderr
        if rc:
            assert "'4,321' in verdict" in r.stdout


def test_validate_without_index_skips_numbers():
    rd = _run()
    f = _findings(rd, "Clicks reached 4,321.")
    assert V.validate(f) == []
    assert any("4,321" in i for i in V.validate(f, numbers=N.Index.from_run(rd)))


def test_issue_list_is_capped():
    rd = _run()
    f = _findings(rd, " ".join(f"{1001 + i * 37:,}" for i in range(30)))
    issues = N.check(f, N.Index.from_run(rd), limit=5)
    assert len(issues) == 6 and issues[-1].startswith("… and ") and "more unverified" in issues[-1], issues


if __name__ == "__main__":
    main(globals())
