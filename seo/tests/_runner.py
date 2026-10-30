"""Minimal pytest-compatible runner: `python3 seo/tests/test_x.py` runs every test_* function."""
import sys
import traceback


def run_all(ns: dict) -> int:
    fns = [v for k, v in sorted(ns.items()) if k.startswith("test_") and callable(v)]
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


def main(ns: dict) -> None:
    sys.exit(run_all(ns))
