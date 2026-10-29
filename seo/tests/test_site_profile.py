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
    en = site_profile.get("pbservices.ge", "priority_keywords", lang="en")
    assert isinstance(flat, list) and len(flat) == len(ru) + len(en) + 1  # +1 zh, ar empty
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
        site_profile.append_history(domain, "did a thing", when="2026-01-01")
        text = site_profile.read_history(domain)
        assert "did a thing" in text
        assert "2026-01-01" in text
    finally:
        if p.exists():
            p.unlink()


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
