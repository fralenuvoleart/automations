# SEO Report Structure (contract)

Every SEO skill produces the same minimum shape. The LLM writes **findings JSON**
([`findings-schema.json`](findings-schema.json)) from the outputs of the deterministic tools
(`seo/gsc_metrics.py`, `seo/coverage.py`, `seo/site_crawl.py`);
[`seo/report/build_report.py`](../report/build_report.py) renders the Markdown. Never hand-edit
the rendered report.

## Required order
1. **Title** — the skill name.
2. **Provenance line** — `Window <start>→<end> (vs …) · GSC lag Nd · generated <UTC>`, or
   `Snapshot as of <date> (live data) · generated <UTC>` for live-only skills. From
   [`seo/window.py`](../window.py) `as_of_line()`; the `window` object is copied from `.run_state.json`.
3. **Verdict** — one paragraph: healthy or not, and the #1 issue.
4. **Data availability** *(only when a source is missing)* — one line per `findings.unavailable` entry.
5. **Coverage vs site profile** *(when the skill uses the profile)* — from `seo/coverage.py`;
   with `basis: gsc_impressions`, "covered" means ≥1 impression in the window.
6. **Sections** — heading, optional data-window line (`sections[].window`, when the data covers a
   different period than the report window), prose body, optional table.
7. **Action list** — prioritized, concrete; each action an object with impact, effort and the page or keyword it concerns.
8. **Definitions** *(automatic)* — `build_report.py` appends plain-language definitions for the
   metrics the report uses, from [`definitions.json`](definitions.json).

## Rules
- Plain language; tables carry the numbers.
- Estimates/heuristics are labelled ([`conciseness-directives.md`](conciseness-directives.md));
  set `"estimate": true` on such sections.
- Every URL and number must come from recorded evidence (`data/`, written by `seo/pipeline.py` / `seo/record.py`) or a computed output (`computed/`).
- No authoring tokens or marker blocks in the output.

## Validation order (mechanical)
1. `validate_report.py --findings F --data {run_dir}/context.json` — structure, dates
   (`endDate < as_of`, no overlapping comparison), labels, evidence for every URL, and every figure
   against evidence + `computed/` at the precision written ([`number_check.py`](../report/number_check.py)).
2. `build_report.py` — refuses malformed findings.
3. `validate_report.py --findings F --report R --data {run_dir}/context.json` — the rendered report
   contains the provenance line, every heading, unavailable source and coverage item.
