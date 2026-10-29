"""Tests for send_email subject resolution (one config, per-skill subjects)."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "send_email", HERE.parent / "scripts" / "send_email.py"
)
send_email = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(send_email)


def test_config_has_recipients_and_subjects():
    cfg = send_email._load(send_email.CONFIG)
    assert cfg.get("to_emails")
    assert cfg.get("subjects")


def test_subject_from_config_map():
    cfg = send_email._load(send_email.CONFIG)
    assert send_email.resolve_subject(cfg, "seo-audit", None) == "SEO Audit — pbservices.ge"


def test_explicit_subject_wins():
    cfg = send_email._load(send_email.CONFIG)
    assert send_email.resolve_subject(cfg, "seo-audit", "Custom") == "Custom"


def test_unknown_skill_falls_back_to_default():
    cfg = send_email._load(send_email.CONFIG)
    assert send_email.resolve_subject(cfg, "does-not-exist", None) == cfg["subject"]


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
