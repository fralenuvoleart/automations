"""Tests for the deterministic coverage helper (flattened + per-language)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "seo"))

# Load by path: the module is named `coverage`, which would collide with the
# PyPI `coverage` package if it is already imported (e.g. under pytest-cov).
_spec = importlib.util.spec_from_file_location("seo_coverage", ROOT / "seo" / "coverage.py")
coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coverage)


def test_compute_flattened_and_by_language():
    out = coverage.compute("pbservices.ge", ["ип в грузии", "bank account georgia"], [])
    assert len(out["priority_keywords"]) == 20  # Core tracked keywords from the rules (brand excluded)
    assert "ип в грузии" in out["covered"]
    assert "bank account georgia" in out["covered"]
    assert out["by_language"]["ru"]["total"] == 12
    assert out["by_language"]["ru"]["covered"] == 1
    assert out["by_language"]["en"]["covered"] == 1
    assert out["by_language"]["zh"]["total"] == 0


def test_matching_is_case_and_space_insensitive():
    out = coverage.compute("pbservices.ge", ["  Bank   Account Georgia "], [])
    assert "bank account georgia" in out["covered"]


def test_missing_is_complement():
    out = coverage.compute("pbservices.ge", [], [])
    assert out["covered"] == []
    assert len(out["missing"]) == 20


def test_read_list_accepts_json_and_csv():
    assert coverage._read_list('["a","b"]') == ["a", "b"]
    assert coverage._read_list("a, b ,c") == ["a", "b", "c"]
    assert coverage._read_list(None) == []


def test_gsc_basis_counts_keywords_with_impressions():
    import json
    import tempfile
    rows = {"rows": [{"keys": ["ИП в Грузии"], "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 6.1},
                     {"keys": ["bank account georgia"], "clicks": 0, "impressions": 0, "ctr": 0, "position": 0}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(rows, fh, ensure_ascii=False)
    out = coverage.compute("pbservices.ge", coverage.visible_items(fh.name, "query"), [], basis="gsc_impressions")
    assert out["basis"] == "gsc_impressions"
    assert out["covered"] == ["ип в грузии"]          # case-insensitive; zero-impression rows don't count


def test_read_list_keeps_slashes_in_inline_values():
    assert coverage._read_list("24/7 accounting, tax") == ["24/7 accounting", "tax"]


def test_read_list_rejects_missing_file_path():
    try:
        coverage._read_list("nonexistent_covered.txt")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


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
