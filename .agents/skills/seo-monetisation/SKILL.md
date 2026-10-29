---
name: seo-monetisation
description: AdSense earnings vs organic search — where organic traffic earns the most, broken down by date and domain (page-level only if AdSense URL channels are configured). Use when asked "AdSense revenue", "which pages earn", "monetisation", or "ads vs organic earnings".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC + AdSense) in .roo/mcp.json. Only relevant if the site monetises with AdSense. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Monetisation (AdSense vs Organic)

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: AdSense earnings correlated with organic search performance. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "AdSense revenue", "which pages earn", "monetisation"
- "ads vs organic earnings", "RPM"

## When NOT to Use
- The site does not monetise with AdSense
- No `search-console` server configured, or AdSense not connected to it

## Requires
- The `search-console` MCP server with **GSC and AdSense** connected (verify with `search-console` → `diagnostics`).
- AdSense must be connected to the property — otherwise the skill states the gap and stops.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| AdSense accounts | `search-console` → `adsense_accounts` {"mode": "configured"} | available* |
| AdSense report | `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS", "dimensions": ["DATE", "DOMAIN_NAME"]} (supply: accountId) | available* |
| Page-level earnings | `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS", "dimensions": ["DATE", "DOMAIN_NAME"]} with runtime dimension override `["URL_CHANNEL_ID"]` | only if URL channels are configured in AdSense |
| Organic queries | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |

\* only if the site monetises with AdSense and it is connected.

## Workflow
1. **Verify + accounts.** `search-console` → `diagnostics`; then `search-console` → `adsense_accounts` {"mode": "configured"}. If none, state that AdSense is not connected and stop.
2. **Earnings.** `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS", "dimensions": ["DATE", "DOMAIN_NAME"]} (supply: accountId) — earnings/impressions/RPM by date and domain. **The AdSense API has no page dimension** — the finest grain is `DOMAIN_NAME`, or `URL_CHANNEL_ID` if the publisher manually configured URL channels.
3. **Page-level check.** Try one `adsense_report` call with dimension `["URL_CHANNEL_ID"]`. If it returns rows, page-level earnings exist via URL channels — use them. If empty, record `findings.unavailable` = `{source: adsense_url_channels, affects: page-level earnings}` and continue at domain level.
4. **Organic overlay.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) — top pages by organic clicks.
5. **Correlate.** With URL channels: rank pages by earnings × organic clicks. Without: overlay the domain-level earnings trend/RPM on the organic page table and say plainly that per-page attribution is unavailable — never invent per-page earnings.
6. **Assemble.** Verdict (where the money is, at the granularity the data supports), then the earnings table (date/domain or URL channel) and the organic-pages table.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (AdSense revenue is platform-reported, not an SEO estimate).

## Output
Begin with the **as-of line** and the **Data availability** section (stating whether page-level earnings exist via URL channels). Verdict (what carries the revenue, at the granularity the data supports), then: the earnings table (date/domain, or URL channel when configured), the top-organic-pages table, and an action list. State clearly if AdSense is not connected.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-monetisation --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If AdSense is not connected, state it and stop (or fall back to `seo-opportunity` for traffic value instead of revenue).
- If `adsense_report` is unavailable, report the accounts only and state that earnings are unavailable.

## Pending Data Sources
- **AdSense** (must be connected to `search-console`): without it the earnings half is impossible. The report states this under **Data availability**.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| AdSense empty | AdSense not connected to the property | connect AdSense in `search-console`; state it otherwise |
| `URL_CHANNEL_ID` returns no rows | no URL channels configured in AdSense | record `findings.unavailable`; report domain/date level only — do not estimate per-page earnings |
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
- Traffic value (CPC-based) → run `seo-opportunity`.
- Whole-site organic audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-monetisation` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth (Google + AdSense).

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
