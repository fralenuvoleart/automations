"""Number check: every figure in the findings must come from recorded evidence or a computed output.

The URL gate catches invented pages; this catches invented or mis-copied figures. A number in
the findings passes when some evidence value matches it at the precision it is written with
(``12.3%`` ↔ 12.26 or 0.1226; ``1,009`` ↔ 1009; ``1.4k`` ↔ 1,350–1,449; round thousands like
``2,000`` ↔ 1,950–2,049; ``12,000`` ↔ 11,500–12,499). Ignored: small counts (≤ 10), years, dates/times, numbers inside URLs or
`code`, identifiers like GA4 or H1, and standard constants (HTTP codes, Core Web Vitals limits,
the site's thresholds, rules and settings). Counts of computed lists ("14 orphan pages") match the
list's length. A figure the agent derives itself must be computed by a script and recorded
(``record.py --source derived``) — never worked out in prose. Figures found only in a pull that is still
cut at the row limit after the pipeline's splitting/paging (``pipeline.json`` ``truncated``), or in an
output built on it (``tainted``), are refused: incomplete data cannot support a figure.

Limits: matching is by value, not by meaning, so a large evidence set can contain a coincidental
match for a short decimal; the check is strongest on distinctive figures (clicks, impressions,
counts, sums).
"""
from __future__ import annotations

import bisect
import json
import re
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
URL_RE = re.compile(r"https?://\S+")
SKIP_RE = re.compile(r"`[^`]*`|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
NUM_RE = re.compile(r"(?<![\w.,/#-])([-+−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%|[kKM]\b)?(?!\w)")
ORDINAL_RE = re.compile(r"(?:\btop|\bfirst|\blast|\btier|\bstep|\bphase|\bpage|\bweek|\bsection|\bpriority|#)\s*$", re.I)
UNIT_RE = re.compile(r"^\s?-?(?:days?|weeks?|months?|years?|hours?|minutes?|mins?|words?|characters?|chars?|px)\b", re.I)
STANDARD = {
    200, 204, 301, 302, 304, 307, 308, 400, 401, 403, 404, 410, 429, 500, 502, 503, 504,  # HTTP codes
    2.5, 4, 0.1, 0.25, 800, 1800, 2500, 4000,  # Core Web Vitals: LCP s/ms, INP ms, CLS, TTFB/FCP ms
    25000, 1000, 2000, 600,                    # API row limits, URL-inspection quota
    16, 45, 50, 60, 70, 150, 155, 160,         # months of GSC history, title/meta lengths
    24, 48, 100,                               # hours, percent base
}


def tokens(text: str) -> list[tuple[str, float, float]]:
    """(as written, value, tolerance) for every number worth checking in ``text``."""
    text = SKIP_RE.sub(" ", URL_RE.sub(" ", text or ""))
    out = []
    for m in NUM_RE.finditer(text):
        whole, frac, suffix = m.group(2), m.group(3) or "", (m.group(4) or "").strip()
        digits = whole.replace(",", "")
        val = float(digits + frac)
        decimals = len(frac) - 1 if frac else 0
        if not frac and not suffix and (val <= 10 or ("," not in whole and 1900 <= val <= 2100)):
            continue  # small counts, ordinals, years ("2,000" is a count, "2026" a year)
        if not frac and not suffix and val <= 100 and ORDINAL_RE.search(text[: m.start()]):
            continue  # "top 20", "week 3", "#12"
        if not suffix and UNIT_RE.match(text[m.end():]):
            continue  # durations and lengths ("28 days", "60 characters") are criteria, not findings
        tol = 0.5 * 10 ** -decimals
        if suffix in ("k", "K"):
            val, tol = val * 1_000, tol * 1_000
        elif suffix == "M":
            val, tol = val * 1_000_000, tol * 1_000_000
        elif not frac and not suffix and val >= 1000 and digits.endswith("00"):
            zeros = min(len(digits) - len(digits.rstrip("0")), len(digits) - 2)
            tol = 0.5 * 10 ** zeros  # written rounded to two significant figures: "2,000", "12,000"
        out.append((m.group(0).strip(), val, tol + 1e-9))
    return out


def _walk(obj, out: list[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append(abs(float(obj)))
    elif isinstance(obj, str):
        for _, v, _ in tokens_raw(obj):
            out.append(v)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk(v, out)
    elif isinstance(obj, list):
        out.append(float(len(obj)))  # "14 orphan pages" = length of a computed list
        for v in obj:
            _walk(v, out)


def tokens_raw(text: str):
    """Every number in an evidence string (no skipping), e.g. GA4 metric values or '2.5 s'."""
    for m in re.finditer(r"\d+(?:,\d{3})*(?:\.\d+)?", text):
        yield m.group(0), float(m.group(0).replace(",", "")), 0.0


class Index:
    """Sorted evidence values (plus ratio→% and ms→s forms) for tolerance lookups."""

    def __init__(self, values, tainted: "Index | None" = None, tainted_files: list[str] | None = None):
        vals = {round(v, 9) for v in values}
        self.vals = sorted(vals | {round(v * 100, 9) for v in vals if v <= 100}       # ratio → %
                           | {round(v / 1000, 9) for v in vals if v >= 100})          # ms → s
        self.tainted = tainted              # values found only in data cut at the row limit
        self.tainted_files = tainted_files or []

    def has(self, x: float, tol: float) -> bool:
        x = abs(x)
        i = bisect.bisect_left(self.vals, x - tol)
        return i < len(self.vals) and self.vals[i] <= x + tol

    @classmethod
    def from_run(cls, run_dir: Path, extra_json: list | None = None) -> "Index":
        vals: list[float] = list(STANDARD)
        bad: list[float] = []
        ctx = run_dir / "context.json"
        files = []
        if ctx.exists():
            for c in json.loads(ctx.read_text()).get("calls", []):
                if isinstance(c, dict) and c.get("file"):
                    files.append(run_dir / c["file"])
        files += sorted((run_dir / "computed").glob("*.json")) if (run_dir / "computed").exists() else []
        # pulls still cut at the row limit (pipeline.json) and outputs built on them: their figures are incomplete
        tainted: set[str] = set()
        pj = run_dir / "pipeline.json"
        if pj.exists():
            summary = json.loads(pj.read_text())
            tainted = {f"data/{n}.json" for n in summary.get("truncated") or []} | set(summary.get("tainted") or [])
        for f in files:
            rel = f"{f.parent.name}/{f.name}"
            try:
                _walk(json.loads(f.read_text()), bad if rel in tainted else vals)
            except (OSError, json.JSONDecodeError):
                continue
        state = run_dir / ".run_state.json"
        if state.exists():
            st = json.loads(state.read_text())
            vals += [float(st.get("window", {}).get("days") or 0), float(st.get("window", {}).get("lag") or 0)]
            vals += site_constants(st.get("site"))
        for obj in extra_json or []:
            _walk(obj, vals)
        return cls(vals, cls(bad) if bad else None, sorted(tainted))


def site_constants(site: str | None) -> list[float]:
    """Thresholds, rule settings and toolkit settings: numbers a report may quote as criteria."""
    out: list[float] = []
    _walk(json.loads((SEO / "config" / "settings.json").read_text()), out)
    if site:
        sys.path.insert(0, str(SEO))
        try:
            import site_profile
            _walk(site_profile.thresholds(site), out)
            rp = SEO / "config" / "rules" / f"{site}.json"
            if rp.exists():
                _walk(json.loads(rp.read_text()).get("keywords", {}).get("auto", {}), out)
        except (FileNotFoundError, KeyError, ValueError):
            pass
    return out


def texts(findings: dict) -> list[tuple[str, str]]:
    """(where, text) for every place the findings state figures."""
    out = [("verdict", findings.get("verdict", ""))]
    for i, s in enumerate(findings.get("sections") or []):
        out.append((f"sections[{i}].body", s.get("body", "")))
        for r, row in enumerate(s.get("table") or []):
            for k, v in (row.items() if isinstance(row, dict) else []):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out.append((f"sections[{i}].table[{r}].{k}", repr(v)))
                elif isinstance(v, str):
                    out.append((f"sections[{i}].table[{r}].{k}", v))
    for i, a in enumerate(findings.get("actions") or []):
        if isinstance(a, str):
            out.append((f"actions[{i}]", a))
        else:
            out += [(f"actions[{i}].{k}", str(a[k])) for k in ("action", "why", "est_clicks") if a.get(k) is not None]
    return out


def check(findings: dict, index: Index, limit: int = 20) -> list[str]:
    issues = []
    for where, text in texts(findings):
        for written, val, tol in tokens(text):
            if index.has(val, tol):
                continue
            if index.tainted is not None and index.tainted.has(val, tol):
                issues.append(f"number comes only from data cut at the row limit ({', '.join(index.tainted_files)}): "
                              f"{written!r} in {where} — incomplete data cannot support a figure; drop it or "
                              "report the gap")
            else:
                issues.append(f"number not found in evidence or computed outputs (possible hallucination): "
                              f"{written!r} in {where}")
    if len(issues) > limit:
        issues = issues[:limit] + [f"… and {len(issues) - limit} more unverified numbers"]
    return issues
