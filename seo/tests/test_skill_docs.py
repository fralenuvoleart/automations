"""Lint the SEO SKILL.md contract: frontmatter, required sections, resolvable links.

Locks the structure in place so future edits can't silently drop required sections.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"

REQUIRED_HEADERS = [
    "## When to Use",
    "## When NOT to Use",
    "## Requires",
    "## Workflow",
    "## Output",
    "## Fallbacks",
    "## Pending Data Sources",
    "## Troubleshooting",
    "## Files",
    "## Related / Delegation",
]
REQUIRED_FRONTMATTER = ["name", "description", "license", "compatibility"]
SHARED_LINKS = ["seo/references/report-structure.md", "seo/references/conciseness-directives.md"]

LINK_RE = re.compile(r"\]\(([^)]+)\)")
DOUBLE_BACKTICK_RE = re.compile(r"(?<!`)``(?!`)")


def _skill_files():
    return sorted(SKILLS.glob("seo-*/SKILL.md"))


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    fm = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def test_frontmatter_complete_and_named():
    for f in _skill_files():
        text = f.read_text()
        fm = _frontmatter(text)
        for key in REQUIRED_FRONTMATTER:
            assert key in fm, f"{f.parent.name}: missing frontmatter '{key}'"
        assert fm["name"] == f.parent.name, f"{f.parent.name}: name mismatch ({fm['name']})"


def test_required_sections_present_in_order():
    for f in _skill_files():
        text = f.read_text()
        positions = []
        for h in REQUIRED_HEADERS:
            idx = text.find(h)
            assert idx != -1, f"{f.parent.name}: missing section {h!r}"
            positions.append(idx)
        assert positions == sorted(positions), f"{f.parent.name}: sections out of order"


def test_shared_contract_links_present():
    for f in _skill_files():
        text = f.read_text()
        for link in SHARED_LINKS:
            assert link in text, f"{f.parent.name}: missing shared-contract link {link}"


def test_relative_links_resolve():
    for f in _skill_files():
        for target in LINK_RE.findall(f.read_text()):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = target.split("#", 1)[0]
            resolved = (f.parent / path).resolve()
            assert resolved.exists(), f"{f.parent.name}: broken link {target}"


def test_no_unexpanded_tokens():
    for f in _skill_files():
        text = f.read_text()
        assert "{{cap:" not in text, f"{f.parent.name}: unexpanded {{cap:}} token"
        assert "{{site:" not in text, f"{f.parent.name}: unexpanded {{site:}} token"


def test_no_double_backtick_artifacts():
    for f in _skill_files():
        for i, line in enumerate(f.read_text().splitlines(), 1):
            assert not DOUBLE_BACKTICK_RE.search(line), (
                f"{f.parent.name}:{i}: double-backtick artifact"
            )


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
