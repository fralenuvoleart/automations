---
name: seo-indexation
description: Index-coverage and sitemap health from Search Console — indexed vs excluded, "Crawled — currently not indexed", sitemap status, and a submit list for priority pages. Use when asked "index coverage", "pages not indexed", "sitemap health", or "why isn't my page indexed".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Indexation & Sitemaps

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: index coverage and sitemap health from the site's own GSC. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "index coverage", "pages not indexed", "why isn't my page indexed"
- "sitemap health", "sitemap errors"

## When NOT to Use
- No `search-console` server configured
- Page speed / structured data (use `seo-technical`)
- Whole-site organic audit (use `seo-audit`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile for priority pages ([`seo/site_profile.py`](../../../seo/site_profile.py)).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Crawl / index health | `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) | available |
| Sitemap status | `search-console` → `sitemaps_list` (supply: siteUrl) | available |
| Page inspection | `search-console` → `inspection_inspect` (supply: siteUrl, urls) | available |
| Submit for indexing | `search-console` → `indexing_submit` (supply: siteUrl, urls) | available |
| Priority pages | site profile (`python3 seo/site_profile.py --site <domain> --get priority_pages`) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Crawl / index health.** `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) — indexed vs excluded counts, "Crawled — currently not indexed", "Discovered — currently not indexed", redirect/canonical exclusions.
3. **Sitemaps.** `search-console` → `sitemaps_list` (supply: siteUrl) — submitted vs indexed, last read, errors/warnings per sitemap.
4. **Priority pages.** `python3 seo/site_profile.py --site <domain> --get priority_pages`. If empty, use the top pages by impressions from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate).
5. **Inspect priority pages.** `search-console` → `inspection_inspect` (supply: siteUrl, urls) — is each priority page indexed? canonical? last crawl?
6. **Submit the missing.** For priority pages that are not indexed, `search-console` → `indexing_submit` (supply: siteUrl, urls) — then list them as the action list. Caveat: Google's Indexing API officially covers only JobPosting/BroadcastEvent content — for ordinary pages submission is a nudge (or routes via Bing/IndexNow), not an indexing guarantee. Say so in the report, and keep internal links + sitemap health as the primary fix.
7. **Assemble.** Rank by (priority × excluded volume).

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.

## Output
Begin with the **as-of line**. Verdict (is index coverage healthy, and the #1 exclusion), then: coverage table (indexed vs each exclusion reason), sitemap status table, priority-page inspection table (indexed? canonical? last crawl), and a submit/action list. Each issue names the page and the exact fix.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-indexation --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If `sitemaps_list` is unavailable, state it and report coverage + inspection only.
- If `indexing_submit` fails, state it and still list the pages to submit manually in GSC.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Submit rejected | URL not on a verified property | confirm the property in `sites_list` |
| Submitted pages still not indexed | Indexing API is a nudge for ordinary pages, not a guarantee | fix internal links/sitemap; re-inspect after the next crawl |

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
- Page speed / structured data → run `seo-technical`.
- Whole-site organic audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-indexation` to select this skill's subject).

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
