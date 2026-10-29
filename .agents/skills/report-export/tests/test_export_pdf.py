"""Tests for the pure Markdown -> HTML step of export_pdf (no PDF engine needed)."""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "export_pdf", HERE.parent / "scripts" / "export_pdf.py"
)
export_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_pdf)


def test_md_to_html_wraps_and_escapes_title():
    import html as _h

    title = "A & B"
    html = export_pdf.md_to_html("# Hi\n\nbody", title, "body{}")
    assert html.startswith("<!doctype html>")
    assert f"<title>{_h.escape(title)}</title>" in html
    assert "body{}" in html


def test_md_to_html_contains_content():
    html = export_pdf.md_to_html("hello world", "t", "")
    assert "hello world" in html


def test_minimal_renderer_handles_report_subset():
    h = export_pdf._minimal_md(
        "# H\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- x\n\n**b** `c`\n"
    )
    assert "<h1>H</h1>" in h
    assert "<table>" in h
    assert "<ul>" in h
    assert "<strong>b</strong>" in h
    assert "<code>c</code>" in h


def test_chromium_bin_env_override():
    os.environ["CHROMIUM_BIN"] = "/nonexistent/chromium"
    try:
        assert export_pdf._chromium_bin() == "/nonexistent/chromium"
    finally:
        del os.environ["CHROMIUM_BIN"]


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
