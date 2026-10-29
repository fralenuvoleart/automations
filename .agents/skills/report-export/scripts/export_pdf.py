#!/usr/bin/env python3
"""Render a Markdown report to PDF.

Engine order (first that works wins):
  1. ``npx md-to-pdf`` (Chromium) — proven path, proper formatting, no Python deps.
  2. WeasyPrint + the ``markdown`` package (pure Python, no network).
  3. WeasyPrint + a built-in minimal renderer (dependency-free fallback).
  4. Chromium rendering a self-built HTML string.

The Markdown -> HTML step is a pure function (testable without any engine).

Usage:
    python3 export_pdf.py --md report.md --out report.pdf [--css report.css] [--title "SEO Report"]
Exit codes: 0 = written, 1 = error.
"""
from __future__ import annotations

import argparse
import html as _html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CSS = HERE / "report.css"


# --------------------------------------------------------------------------- #
# Markdown -> HTML (pure)
# --------------------------------------------------------------------------- #
def _inline(s: str) -> str:
    s = _html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _minimal_md(md_text: str) -> str:
    """Dependency-free renderer for the report subset (headings, tables, lists,
    blockquotes, rules, fenced code, inline emphasis/links)."""
    lines = md_text.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    in_ul = in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):
            close_lists()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(_html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|", lines[i + 1]):
            close_lists()
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(c)}</th>" for c in header)
                       + "</tr></thead><tbody>")
            i += 2
            while i < n and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', line))}</li>")
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(re.sub(r'^\s*\d+\.\s+', '', line))}</li>")
            i += 1
            continue
        if re.match(r"^\s*>\s?", line):
            close_lists()
            out.append(f"<blockquote>{_inline(re.sub(r'^\s*>\s?', '', line))}</blockquote>")
            i += 1
            continue
        if re.match(r"^\s*---+\s*$", line):
            close_lists()
            out.append("<hr>")
            i += 1
            continue
        if not line.strip():
            close_lists()
            i += 1
            continue
        close_lists()
        out.append(f"<p>{_inline(line)}</p>")
        i += 1
    close_lists()
    return "\n".join(out)


def md_to_html(md_text: str, title: str, css: str) -> str:
    """Pure Markdown -> standalone HTML (no PDF engine needed)."""
    try:
        import markdown  # type: ignore

        body = markdown.markdown(
            md_text, extensions=["tables", "fenced_code", "toc", "sane_lists"]
        )
    except ImportError:
        body = _minimal_md(md_text)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{_html.escape(title)}</title><style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )


# --------------------------------------------------------------------------- #
# Engines
# --------------------------------------------------------------------------- #
def _chromium_bin() -> str | None:
    return (
        os.environ.get("CHROMIUM_BIN")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
        or shutil.which("chrome")
    )


def via_md_to_pdf(md_path: Path, out: Path, css_path: Path) -> bool:
    """Chromium via ``npx md-to-pdf`` (proven path; needs npx + network on first run)."""
    if not shutil.which("npx"):
        return False
    env = dict(os.environ)
    bin_ = _chromium_bin()
    if bin_:
        env["PUPPETEER_SKIP_DOWNLOAD"] = "true"
        env["PUPPETEER_EXECUTABLE_PATH"] = bin_
    default_out = md_path.with_suffix(".pdf")
    cmd = [
        "npx", "--yes", "md-to-pdf", str(md_path),
        "--stylesheet", str(css_path),
        "--pdf-options",
        '{"format":"a4","printBackground":true,'
        '"margin":{"top":"18mm","right":"18mm","bottom":"18mm","left":"18mm"}}',
        "--launch-options", '{"args":["--no-sandbox"]}',
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180, env=env)
    except Exception:
        return False
    if not default_out.exists():
        return False
    if default_out.resolve() != out.resolve():
        shutil.move(str(default_out), str(out))
    return out.exists()


def via_weasyprint(html: str, out: Path) -> bool:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return False
    try:
        HTML(string=html).write_pdf(str(out))
    except Exception:
        return False
    return out.exists()


def via_chromium(html: str, out: Path) -> bool:
    bin_ = _chromium_bin()
    if not bin_:
        return False
    with tempfile.TemporaryDirectory() as d:
        html_path = Path(d) / "report.html"
        html_path.write_text(html, encoding="utf-8")
        cmd = [
            bin_, "--headless", "--disable-gpu", "--no-sandbox",
            f"--print-to-pdf={out}", html_path.as_uri(),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except Exception:
            return False
    return out.exists()


def render(md_path: Path, out: Path, css_path: Path | None, title: str) -> str:
    css_file = css_path or DEFAULT_CSS
    if via_md_to_pdf(md_path, out, css_file):
        return "md-to-pdf (chromium)"
    md_text = md_path.read_text(encoding="utf-8")
    css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""
    html = md_to_html(md_text, title, css)
    if via_weasyprint(html, out):
        return "weasyprint"
    if via_chromium(html, out):
        return "chromium"
    raise RuntimeError(
        "no PDF engine available (install weasyprint, or provide npx + Chromium)"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--css", default=None)
    ap.add_argument("--title", default="Report")
    args = ap.parse_args(argv)
    try:
        engine = render(
            Path(args.md), Path(args.out),
            Path(args.css) if args.css else None, args.title,
        )
    except Exception as e:  # noqa: BLE001
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(f"wrote {args.out} ({engine})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
