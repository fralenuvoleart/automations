---
name: seo-technical
description: Technical SEO audit of priority pages — Core Web Vitals (LCP/INP/CLS), mobile vs desktop, structured-data coverage, accessibility (Lighthouse a11y category), and crawlability flags, from PageSpeed + GSC inspection. Use when asked "technical SEO", "core web vitals", "page speed audit", "why is my page slow", "accessibility", or "schema check".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC + PageSpeed + schema) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Technical SEO

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: technical health of the site's priority pages (CWV, mobile, structured data, crawlability, accessibility). Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "technical SEO", "core web vitals", "page speed audit"
- "why is my page slow", "schema check", "structured data"

## When NOT to Use
- No `search-console` server configured
- Whole-site organic performance audit (use `seo-audit`)
- Index coverage / sitemap health (use `seo-indexation`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile for priority pages ([`seo/site_profile.py`](../../../seo/site_profile.py)).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Page speed / CWV | `search-console` → `pagespeed_analyze` (supply: url, strategy) | available |
| Accessibility (Lighthouse a11y) | `search-console` → `pagespeed_analyze` {"category": ["accessibility"]} (supply: url) | available |
| Structured data | `search-console` → `schema_validate` (supply: url) | available |
| Index / canonical state | `search-console` → `inspection_inspect` (supply: siteUrl, urls) | available |
| Crawl health | `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) | available |
| Priority pages | site profile (`python3 seo/site_profile.py --site <domain> --get priority_pages`) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Template-level representative pages.** Identify one representative URL per template from the profile's `sections` (`python3 seo/site_profile.py --site <domain> --get sections`) and `priority_pages`: Homepage, a primary Service page, and a Blog post. CWV issues and layout shifts are systemic to page templates; testing representative templates delivers architectural recommendations without quota waste.
3. **Core Web Vitals.** For each representative template URL: `search-console` → `pagespeed_analyze` (supply: url, strategy) — run **mobile first, then desktop** (`strategy: "mobile"` / `"desktop"`). Record LCP, INP, CLS and the pass/fail band. Then run `search-console` → `pagespeed_analyze` {"category": ["accessibility"]} (supply: url) on the same pages for the Lighthouse accessibility category — flag contrast, missing alt text, ARIA, and label/heading issues per template.
4. **Structured data & Knowledge Graph entities.** `search-console` → `schema_validate` (supply: url) per page — required types present (Organization, LocalBusiness/Service, FAQ, Article), errors vs warnings. Check entity disambiguation: presence of `sameAs` authority links (Wikidata, Wikipedia, LinkedIn, Crunchbase) and verified `author`/`reviewedBy` Person entities for E-E-A-T and LLM grounding (see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md)).
5. **Index / canonical state.** `search-console` → `inspection_inspect` (supply: siteUrl, urls) for the priority set — canonical correctness, indexing state, last crawl.
6. **Crawl health & AI crawler access.** `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) — surface crawl/robots/sitemap blockers. Verify whether `robots.txt` allows AI search crawlers (`GPTBot`, `OAI-SearchBot`, `PerplexityBot`, `ClaudeBot`, `Google-Extended`).
7. **Assemble.** Rank issues by (severity × number of priority pages affected).

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** / **heuristic** label exactly as written (PageSpeed lab data is a snapshot, not field data).

## Output
Begin with the **as-of line**. Verdict (is the site technically healthy, and the #1 blocker), then: CWV table (page, mobile LCP/INP/CLS, desktop), accessibility findings (page, a11y issue, severity), structured-data coverage table (page, types, errors), crawlability flags, and a prioritized fix list. Each issue names the page and the exact change.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-technical --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If `pagespeed_analyze` fails (PageSpeed API unavailable/rate-limited), state it and still report structured data + inspection + crawl health.
- If `schema_validate` is unavailable, state it and skip the structured-data section.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| PageSpeed empty/timeout | PageSpeed API rate limit or slow page | retry once; otherwise state the page is unmeasured |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |

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
- Index coverage / sitemap health → run `seo-indexation`.
- Whole-site organic audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-technical` to select this skill's subject).

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
