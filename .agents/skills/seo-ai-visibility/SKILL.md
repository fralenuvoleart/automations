---
name: seo-ai-visibility
description: Measure real AI-engine visibility — traffic from ChatGPT, Perplexity, Claude, Gemini and which pages they cite — from actual GA4 referral data, not prompt sampling. Use when asked "AI visibility", "GEO/AEO check", "do LLMs cite us", "traffic from ChatGPT", or "how do we show up in AI search".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and the `analytics` MCP server (official GA4) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# AI Visibility

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: AI-engine visibility from GA4 referral data plus GSC generative-query heuristics. **Primary skill** — AI engines are a material share of searches for this site, not a nice-to-have. Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — name the pages and the exact change.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "AI visibility", "GEO/AEO check", "do LLMs cite us"
- "traffic from ChatGPT", "how do we show up in AI search"

## When NOT to Use
- No `search-console` server configured
- General organic audit (use `seo-audit`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics` — `google` must report `ok`).
- The `analytics` MCP server (official GA4) with the service account added to the GA4 property.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Sessions by source/medium | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) | available |
| Daily trend | `analytics` → `run_report` {"dimensions": ["date"], "metrics": ["sessions"]} (supply: property_id, date_ranges) | available |
| Cited landing pages (AI-filtered) | `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "conversions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) | available |
| Conversions by source | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "conversions", "engagementRate"]} (supply: property_id, date_ranges) | available |
| AI-shaped queries (heuristic) | `search-console` → `genai_query_insights` (supply: siteUrl) | available |
| Organic baseline | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |

## Workflow
1. **Verify.** `search-console` → `diagnostics` and `analytics` → `get_account_summaries` must both respond.
2. **Traffic by engine.** `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) (current vs previous period). Confirm the AI-source list matches the site profile's `ai_sources` (`python3 seo/site_profile.py --site <domain> --get ai_sources`) and extend the filter if the profile adds engines. Label this a **lower bound** — some AI visits arrive as `Referral` or `(direct)`.
3. **Trend.** `analytics` → `run_report` {"dimensions": ["date"], "metrics": ["sessions"]} (supply: property_id, date_ranges) — is AI traffic growing, and did anything spike (a spike = something started citing you; find it).
4. **Cited pages.** `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "conversions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) — which URLs AI engines actually send people to (filtered to AI sources). These are your proven-citable pages.
5. **Conversion comparison.** `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "conversions", "engagementRate"]} (supply: property_id, date_ranges) — compare AI-source conversion rate against organic.
6. **AI-shaped queries (bonus signal).** `search-console` → `genai_query_insights` (supply: siteUrl) — GSC queries that look like AI prompts (prompt verbs, follow-ups, conversational phrasing). This is a **heuristic undercount, not AI traffic** — use it to spot query patterns, never as the headline metric.
7. **Diagnose the winners.** Read the top 2–3 cited pages (fetch them). Note the pattern: direct answers high on the page, stats/definitions, clean headings, schema. That pattern is the citation recipe for this site.
8. **Find the misses.** Cross-reference with `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate): pages with strong organic queries but zero AI referrals — candidates to restructure toward the citation recipe from step 7.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28 --compare` and pass the literal `startDate`/`endDate`/`compareStartDate`/`compareEndDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** / **heuristic** label exactly as written (AI referral counts are a lower bound).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Verdict (**AI share of organic** — the headline metric — plus trend and top engine), then: engine table, cited-pages table with conversions, the citation recipe observed on winning pages, and a top-5 list of pages to restructure. Keep it concrete — name the pages and the exact change.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 28 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `analytics` (GA4) server is unavailable, fall back to `search-console` → `analytics_advanced` (supply: propertyId, metricType) for general GA4 metrics and state plainly that source-level AI attribution is unavailable — that tool has no AI-referral breakdown.
- If GA4 AI-referral data is unavailable entirely, fall back to `search-console` → `genai_query_insights` (supply: siteUrl) alone and label the report **heuristic, not measured**.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, skip SERP / AI-answer citation checks.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
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
- General organic audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `analytics` (GA4) uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`); `search-console` manages its own OAuth.
- Optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

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
