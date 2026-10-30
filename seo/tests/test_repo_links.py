"""Every relative link in the repository's Markdown files points to a file that exists.

SKILL.md links are also checked by test_skill_docs.py; this covers README, references, memory-bank,
AGENTS.md and the rest, where dead links (e.g. to removed audit documents) went unnoticed before.
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "seo" / "tests"))
from _runner import main  # noqa: E402

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
SKIP = ("http://", "https://", "mailto:", "#", "computer://", "data:")
# Folders outside the SEO toolkit that the owner asked to leave untouched (kinsta-logs: not to be used at all).
EXCLUDE = (".agents/skills/kinsta-logs/",)


def markdown_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.md"], capture_output=True, text=True,
                             timeout=20, check=True).stdout.split()
        return [ROOT / f for f in out]
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and "node_modules" not in p.parts]


def broken_links() -> list[str]:
    bad = []
    for f in markdown_files():
        if not f.exists() or str(f.relative_to(ROOT)).startswith(EXCLUDE):
            continue
        text = FENCE_RE.sub("", f.read_text(errors="replace"))
        text = re.sub(r"`[^`\n]*`", "", text)  # inline code is not a link
        for target in LINK_RE.findall(text):
            if target.startswith(SKIP) or "{" in target or "<" in target:
                continue
            path = unquote(target.split("#", 1)[0])
            if path and not (f.parent / path).exists():
                bad.append(f"{f.relative_to(ROOT)}: {target}")
    return bad


def test_every_relative_markdown_link_resolves():
    bad = broken_links()
    assert not bad, "broken links:\n" + "\n".join(bad)


if __name__ == "__main__":
    main(globals())
