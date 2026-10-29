# SEO Report Structure (contract)

Every SEO skill produces the same minimum shape. The LLM writes **findings JSON**
([`findings-schema.json`](findings-schema.json)); [`seo/report/build_report.py`](../report/build_report.py)
renders the Markdown. Do not hand-edit the rendered report.

## Required order
1. **Title** — the skill name / subject.
2. **As-of line** — `Window <start>→<end> (vs …) · GSC lag Nd · generated <UTC>`. From [`seo/window.py`](../window.py) `as_of_line()`.
3. **Verdict** — one paragraph: healthy or not, and the #1 issue.
4. **Data availability** *(only when a source is missing)* — one line per unavailable source: what it affects and why. Driven by `findings.unavailable` (graceful degradation).
5. **Coverage vs site profile** *(only when a profile is used)* — priority keywords/pages covered vs missing, the per-language breakdown (`by_language`), and the missing list. Driven by `findings.coverage` (produce it with [`seo/coverage.py`](../coverage.py)).
6. **Sections** — one per finding group. Each: heading, prose body, optional table.
7. **Action list** — prioritized, concrete.

## Rules
- Every section body is plain language; tables carry the numbers.
- Numbers that are **estimates/heuristics** must be labelled (see [`conciseness-directives.md`](conciseness-directives.md)).
- The as-of line is mandatory and must reflect the *actual* window used.
- The report must contain no `{{cap:}}` tokens (those are authoring-only).

## Validation
[`seo/report/validate_report.py`](../report/validate_report.py) enforces this contract mechanically.
