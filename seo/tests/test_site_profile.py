"""Tests for the site-profile layer: schema, determinism, unknown-key failure."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "seo"))
import site_profile  # noqa: E402


def test_schema_loads():
    s = site_profile.load_schema()
    assert "properties" in s and "required" in s


def test_all_profiles_and_rules_valid():
    for domain in site_profile.list_sites():
        issues = site_profile.validate_site(domain)
        assert not issues, f"{domain}: {issues}"


def test_list_sites_ignores_rules_and_history():
    assert site_profile.list_sites() == ["pbservices.ge"]


def test_classification_keys_are_derived_from_rules_not_stored():
    raw = site_profile.load_profile("pbservices.ge", derived=False)
    for k in ("languages", "sections", "services", "priority_keywords"):
        assert k not in raw, f"{k} must live in the rules file only"
    p = site_profile.load_profile("pbservices.ge")
    assert p["languages"] == ["EN", "RU", "AR", "ZH"]
    assert p["sections"] == ["Services", "Blog", "Homepage", "Other pages"]
    assert p["services"][:5] == ["IE", "Residency", "Tax", "Company", "Bank account"] and "Brand" not in p["services"]


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
    assert isinstance(flat, list) and len(flat) == len(ru) + len(en) == 20  # Core keywords; zh, ar have none
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
    issues = site_profile.validate({"domain": 1})
    assert any("domain" in i for i in issues)


def test_validate_rejects_unknown_and_moved_keys():
    issues = site_profile.validate({"domain": "x", "bogus": 1, "brand_terms": ["x"]})
    assert any("unknown key: bogus" in i for i in issues)
    assert any("unknown key: brand_terms" in i for i in issues)  # classification lives in the rules file


def test_validate_rejects_language_key_not_in_languages():
    issues = site_profile.validate({"domain": "x", "ads_language_constants": {"DE": "languageConstants/1001"}},
                                   languages=["EN", "RU"])
    assert any("not in the rules' languages" in i for i in issues)


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


def test_validate_checks_thresholds_and_ads_fields():
    prof = site_profile.load_profile("pbservices.ge", derived=False)
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


def test_ga4_ai_filter_comes_from_the_ai_channel_rule():
    import re
    f = site_profile.ga4_ai_filter("pbservices.ge")["filter"]
    assert f["field_name"] == "sessionSource" and f["string_filter"]["match_type"] == "FULL_REGEXP"
    rx = re.compile(f["string_filter"]["value"])  # GA4 FULL_REGEXP = whole-value match
    for host in ("chatgpt.com", "www.perplexity.ai", "chat.deepseek.com", "claude.ai", "copilot.microsoft.com",
                 "gemini.google.com", "grok.com", "meta.ai", "chat.mistral.ai", "you.com"):
        assert rx.fullmatch(host), host
    for host in ("google", "bing.com", "youtube.com", "facebook.com"):
        assert not rx.fullmatch(host), host


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
