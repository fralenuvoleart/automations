---
name: seo-serp-features
description: Find featured-snippet and People-Also-Ask capture opportunities on priority keywords — what the snippet currently shows, your position, and the answer format to use. Use when asked "featured snippet", "people also ask", "SERP features", or "win the snippet".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. The `dataforseo` server (live SERP) is optional — without it the SERP is built from web search. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# SERP Features

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: featured-snippet and PAA opportunities on the site's priority keywords. Does not read or write `memory-bank/`.
- **Audience**: the content editor — each row names the keyword, the format, and the target page.

## Report Audience & Purpose
- **Audience**: the content editor (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "featured snippet", "people also ask", "win the snippet"
- "SERP features", "position zero"

## When NOT to Use
- No `search-console` server configured
- Full content brief (use `seo-content-brief`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile with `priority_keywords` ([`seo/site_profile.py`](../../../seo/site_profile.py)).
- *(Optional)* The `dataforseo` MCP server (SERP API). Without it, build the SERP from web search.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Live SERP | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) | optional* (fallback: web search) |
| Current positions | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Priority keywords | site profile (`python3 seo/site_profile.py --site <domain> --get priority_keywords`) | available |

\* requires DataForSEO credentials in `.roo/mcp.json`; without them, use web search and record `unavailable`.

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Keyword set.** `python3 seo/site_profile.py --site <domain> --get priority_keywords` — the keywords that matter.
3. **SERP per keyword.** `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data). If unauthenticated, fetch the top results via web search instead and record `findings.unavailable` = `{source: dataforseo, affects: live SERP}`.
4. **Identify features.** For each keyword: is there a featured snippet? a PAA block? who holds the snippet, and in what format (paragraph/list/table)?
5. **Your position.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) — which of your pages rank 2–10 (snippet-capture candidates).
6. **Opportunity.** Rank by (impressions × snippet winnability). For each, state the target page and the answer format to use.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **heuristic** label exactly as written (SERP snapshots vary by location/time).

## Output
Begin with the **as-of line**. Verdict (how many priority keywords have a capturable snippet), then: an opportunity table (keyword, feature, current holder, your position, target page, format), and a ranked action list. If the SERP came from web search, say so in the **Data availability** section.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `dataforseo` server is unavailable, build the SERP from web search and record the missing source in `findings.unavailable` (the report will state it under **Data availability**).
- If GSC is unavailable, state it and report SERP structure only.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, build the SERP from web search — the brief must still be built from a real SERP.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| SERP looks wrong | location/device mismatch | pin the target country and device; note the snapshot locale |

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
- Full content brief → run `seo-content-brief`.
- Content decay / refresh → run `seo-content-refresh`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Capability calls go only to the configured MCP servers (GSC/GA4/Google Ads); no data leaves to a third party unless the skill explicitly uses `tavily`/`dataforseo`.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
