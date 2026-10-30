"""Tests for the site-profile layer: schema, determinism, unknown-key failure."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "seo"))
import site_profile  # noqa: E402


def test_schema_loads():
    s = site_profile.load_schema()
    assert "properties" in s and "required" in s


def test_all_profiles_valid():
    for domain in site_profile.list_sites():
        issues = site_profile.validate(site_profile.load_profile(domain))
        assert not issues, f"{domain}: {issues}"


def test_pbservices_profile_has_expected_keys():
    p = site_profile.load_profile("pbservices.ge")
    for k in ("domain", "languages", "services", "priority_keywords"):
        assert k in p, f"missing {k}"
    assert p["domain"] == "pbservices.ge"
    assert p["markets"] == ["WORLDWIDE"]


def test_priority_keywords_grouped_by_language():
    p = site_profile.load_profile("pbservices.ge")
    pk = p["priority_keywords"]
    assert isinstance(pk, dict)
    assert set(pk) == {"ru", "en", "zh", "ar"}
    assert len(pk["ru"]) > 0 and len(pk["en"]) > 0


def test_get_flattens_and_filters_by_lang():
    flat = site_profile.get("pbservices.ge", "priority_keywords")
    ru = site_profile.get("pbservices.ge", "priority_keywords", lang="ru")
    ru_upper = site_profile.get("pbservices.ge", "priority_keywords", lang="RU")
    en = site_profile.get("pbservices.ge", "priority_keywords", lang="en")
    assert isinstance(flat, list) and len(flat) == len(ru) + len(en) + 1  # +1 zh, ar empty
    assert ru == ru_upper
    assert "ип в грузии" in ru
    assert "individual entrepreneur georgia" in en
    assert "ип в грузии" not in en


def test_get_is_deterministic():
    a = site_profile.get("pbservices.ge", "priority_keywords")
    b = site_profile.get("pbservices.ge", "priority_keywords")
    assert a == b


def test_unknown_key_raises():
    try:
        site_profile.get("pbservices.ge", "does_not_exist")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_validate_rejects_bad_type():
    issues = site_profile.validate({
        "domain": 1, "languages": [], "sections": [],
        "services": [], "priority_keywords": {},
    })
    assert any("domain" in i for i in issues)


def test_validate_rejects_unknown_key():
    issues = site_profile.validate({
        "domain": "x", "languages": [], "sections": [],
        "services": [], "priority_keywords": {}, "bogus": 1,
    })
    assert any("unknown key" in i for i in issues)


def test_validate_rejects_language_key_not_in_languages():
    issues = site_profile.validate({
        "domain": "x", "languages": ["EN"], "sections": [],
        "services": [], "priority_keywords": {"de": ["x"]},
    })
    assert any("not in languages" in i for i in issues)


def test_history_append_and_read():
    domain = "_test_history_tmp"
    p = site_profile.history_path(domain)
    try:
        site_profile.append_history(domain, "did a thing", when="2026-01-01", status="done")
        assert site_profile.append_history(domain, "did  a thing", status="done") is None  # duplicate ignored
        site_profile.append_history(domain, "try another", when="2026-01-02")             # default: recommended
        text = site_profile.read_history(domain)
        assert "- **2026-01-01** [done] did a thing" in text and "[recommended] try another" in text
        assert site_profile.read_history(domain, "done").strip() == "- **2026-01-01** [done] did a thing"
    finally:
        if p.exists():
            p.unlink()


def test_validate_rejects_brand_terms_in_priority_keywords_and_bad_prefixes():
    prof = site_profile.load_profile("pbservices.ge")
    prof = {**prof, "priority_keywords": {**prof["priority_keywords"], "en": ["PB Services", "tax residency georgia"]},
            "language_paths": {**prof["language_paths"], "RU": "ru/"}}
    issues = site_profile.validate(prof)
    assert any("is a brand term" in i for i in issues)
    assert any("must start and end with '/'" in i for i in issues)


def test_validate_checks_thresholds_and_ads_fields():
    prof = site_profile.load_profile("pbservices.ge")
    bad = {**prof, "thresholds": {"decay_pct": "30", "bogus": 1}, "ads_geo_targets": ["2840"],
           "ads_customer_id": "12-34"}
    issues = site_profile.validate(bad)
    assert any("thresholds.decay_pct" in i for i in issues)
    assert any("unknown key 'bogus'" in i for i in issues)
    assert any("ads_geo_targets[0]" in i for i in issues)
    assert any("ads_customer_id" in i for i in issues)


def test_thresholds_merge_defaults():
    import gsc_metrics
    thr = site_profile.thresholds("pbservices.ge")
    assert thr["decay_pct"] == gsc_metrics.DEFAULTS["decay_pct"]


def test_ga4_ai_filter_matches_hosts_and_subdomains_only():
    import re
    f = site_profile.ga4_ai_filter("pbservices.ge")["filter"]
    assert f["field_name"] == "sessionSource" and f["string_filter"]["match_type"] == "FULL_REGEXP"
    rx = re.compile(f["string_filter"]["value"])
    for host in ("chatgpt.com", "www.perplexity.ai", "chat.deepseek.com", "claude.ai", "copilot.microsoft.com"):
        assert rx.match(host), host
    for host in ("notchatgpt.com", "chatgpt.com.evil.io", "google.com"):
        assert not rx.match(host), host


def test_site_token_expansion():
    import resolve
    assert resolve.site_display("priority_keywords") == (
        "`python3 seo/site_profile.py --site <domain> --get priority_keywords`"
    )
    assert "priority_keywords" in resolve.site_keys()
    assert "bogus" not in resolve.site_keys()


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
