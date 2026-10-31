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
# Folders outside the SEO toolkit that the owner asked to leave untouched (kinsta-logs: not to be used at all),
# and plans/ — never committed (git-ignored), so a link into it cannot resolve on a fresh clone.
EXCLUDE = (".agents/skills/kinsta-logs/", "plans/")


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
            if path and not _in_plans(f, path) and not (f.parent / path).exists():
                bad.append(f"{f.relative_to(ROOT)}: {target}")
    return bad


def _in_plans(source: Path, target: str) -> bool:
    """A link into `plans/` cannot be checked: the folder is git-ignored and absent on a fresh clone."""
    try:
        return str((source.parent / target).resolve().relative_to(ROOT.resolve())).startswith("plans/")
    except ValueError:  # outside the repo
        return False


def test_plans_links_are_not_checked_but_other_broken_links_are():
    memory_bank, seo_readme = ROOT / "memory-bank" / "activeContext.md", ROOT / "seo" / "README.md"
    assert _in_plans(memory_bank, "../plans/whatever.md")      # git-ignored folder: not a failure
    assert not _in_plans(seo_readme, "missing.md")             # everything else is checked
    assert not _in_plans(seo_readme, "../references/data-source-map.md")


def test_every_script_named_in_the_docs_exists():
    """A command copied out of COMMANDS.md / docs/SEO.md must not point at a file that moved."""
    import re
    scripts = set()
    for doc in (ROOT / "seo" / "COMMANDS.md", ROOT / "docs" / "SEO.md"):
        text = FENCE_RE.sub("", doc.read_text(errors="replace"))
        scripts |= set(re.findall(r"python3 ((?:seo|\.agents)/[\w./-]+\.py)", text))
    assert scripts, "no commands found: did the docs move?"
    missing = sorted(s for s in scripts if not (ROOT / s).exists())
    assert not missing, f"documented scripts that do not exist: {missing}"


def test_every_relative_markdown_link_resolves():
    bad = broken_links()
    assert not bad, "broken links:\n" + "\n".join(bad)


if __name__ == "__main__":
    main(globals())
