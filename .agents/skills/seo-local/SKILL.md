---
name: seo-local
description: Local SEO check — local-intent search performance from Search Console, and where a Google Business Profile would help. Use when asked "local SEO", "local pack", "Google Business Profile", or "near me" rankings.
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. A Google Business Profile data source is NOT wired — the skill degrades to GSC local-intent queries only. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Local SEO

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: local-intent organic performance from the site's own GSC; GBP/map-pack analysis is pending a data source. Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — where local visibility is missing.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "local SEO", "local pack", "near me" rankings
- "Google Business Profile", "map pack"

## When NOT to Use
- No `search-console` server configured
- Non-local business (use `seo-audit`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- *(Pending)* A Google Business Profile data source — not wired; the skill reports GSC local-intent queries only and states the gap.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Local-intent queries | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| GBP / map-pack data | Google Business Profile API | not connected |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Local-intent queries.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) — filter to queries containing local modifiers ("near me", city/region names). If the site profile's `markets` is `WORLDWIDE`, there is no local focus: report local-intent queries only and state that local SEO is not a priority.
3. **Coverage.** Which local-intent queries have a page ranking; which do not.
4. **State the gap.** Record `findings.unavailable` = `{source: google_business_profile, affects: map-pack/local visibility}` so the report states the missing half.
5. **Assemble.** Rank local opportunities by impressions × winnability.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.

## Output
Begin with the **as-of line** and the **Data availability** section (stating the GBP/map-pack half is unavailable). Verdict, then: local-intent query table (query, page, position, impressions), and an action list.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- Without a GBP data source, report GSC local-intent queries only and record the missing source in `findings.unavailable` (the report states it under **Data availability**).

## Pending Data Sources
- **Google Business Profile API** (not configured): without it, map-pack/local-pack visibility and GBP health cannot be assessed — only GSC local-intent queries are reported.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| No local queries found | no local modifier / market in the profile | add `markets` to the site profile |

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

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.

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
