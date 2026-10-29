---
name: seo-brand-split
description: Brand vs non-brand performance split from Search Console — branded vs non-branded clicks/impressions trend, where non-brand growth is the real SEO signal. Use when asked "brand vs non-brand", "branded traffic", "non-brand growth", or "how much is brand".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. Brand terms come from the site profile (`seo/config/sites/<domain>.json`). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Brand vs Non-Brand

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: split branded vs non-branded search performance from the site's own GSC. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "brand vs non-brand", "branded traffic", "how much is brand"
- "non-brand growth", "branded vs organic"

## When NOT to Use
- No `search-console` server configured
- Whole-site organic audit (use `seo-audit`)
- Rank movement over time (use `seo-rank-tracking`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile with `brand_terms` ([`seo/site_profile.py`](../../../seo/site_profile.py)).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Brand vs non-brand | `search-console` → `seo_audit` {"type": "brand_vs_nonbrand"} (supply: siteUrl, brandKeywords) | available |
| Query-to-page mappings | `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) | available |
| Brand terms | site profile (`python3 seo/site_profile.py --site <domain> --get brand_terms`) | available |
| Language path map | site profile (`python3 seo/site_profile.py --site <domain> --get language_paths`) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Brand terms.** `python3 seo/site_profile.py --site <domain> --get brand_terms` — pass these as `brandKeywords`.
3. **The split.** `search-console` → `seo_audit` {"type": "brand_vs_nonbrand"} (supply: siteUrl, brandKeywords) — branded vs non-branded clicks/impressions/position.
4. **Cross-check.** `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) — classify queries against `brand_terms` to confirm the split and find top non-brand queries.
5. **Trend.** Compare current vs previous period; the signal that matters is **non-brand click/impression growth** (branded traffic mostly tracks demand, not SEO).
6. **By language & hreflang integrity.** GSC has no language dimension — derive language from the **page path** via the profile's `language_paths` map (`python3 seo/site_profile.py --site <domain> --get language_paths`; e.g. EN = `/`, RU = `/ru/`, AR = `/ar/`, ZH = `/zh/`). Classify each query by the path prefix of the page it maps to in the `analytics_query` rows; queries whose page matches no prefix fall back to script detection — label those **derived**. Verify reciprocal `hreflang` consistency so secondary language versions do not cannibalize primary language queries (see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md)). Report branded vs non-brand per language so a language-specific gap is visible.
7. **Assemble.** Verdict = non-brand direction; then branded vs non-branded table (overall + per language); top non-brand queries.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28 --compare` and pass the literal `startDate`/`endDate`/`compareStartDate`/`compareEndDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.

## Output
Begin with the **as-of line**. Verdict (is non-brand growing?), then: branded vs non-branded table (clicks, impressions, position, current vs previous), and the top non-brand queries. State the brand-term list used so the split is reproducible.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-brand-split --days 28 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the specialized `brand_vs_nonbrand` audit is not exposed, classify the raw `analytics_query` rows against `brand_terms` locally and label the split as derived.
- If the site profile has no `brand_terms`, stop and ask the user to add them — do not guess which terms are branded.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Brand split looks wrong | brand_terms incomplete in the profile | update `seo/config/sites/<domain>.json` and re-run |

## Files

| File | Purpose | Action |
|---|---|---|
| [`seo/capabilities.json`](../../../seo/capabilities.json) | capability registry (single source of truth) | Read |
| [`seo/references/report-structure.md`](../../../seo/references/report-structure.md) | report section contract | Read |
| [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md) | tone/label rules | Read |
| [`seo/references/data-source-map.md`](../../../seo/references/data-source-map.md) | freshness + degradation ladder | Read |
| [`seo/references/capability-usage.md`](../../../seo/references/capability-usage.md) | capability tokens, `args` vs `runtime`, `policy` | Read |
| [`seo/references/domain-knowledge.md`](../../../seo/references/domain-knowledge.md) | SEO interpretation methodology | Read |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | renders findings JSON → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

## Related / Delegation
- Whole-site organic audit → run `seo-audit`.
- Position movers over time → run `seo-rank-tracking`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-brand-split` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Third-party calls: none — capability calls go only to the configured MCP servers (GSC/GA4/Google Ads); the site's data does not leave Google.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
