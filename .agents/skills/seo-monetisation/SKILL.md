---
name: seo-monetisation
description: AdSense earnings vs organic search — where organic traffic earns the most, and which pages carry the revenue. Use when asked "AdSense revenue", "which pages earn", "monetisation", or "ads vs organic earnings".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC + AdSense) in .roo/mcp.json. Only relevant if the site monetises with AdSense. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Monetisation (AdSense vs Organic)

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: AdSense earnings correlated with organic search performance. Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — which pages and queries carry the money.

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
| AdSense report | `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS"} (supply: accountId) | available* |
| Organic queries | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |

\* only if the site monetises with AdSense and it is connected.

## Workflow
1. **Verify + accounts.** `search-console` → `diagnostics`; then `search-console` → `adsense_accounts` {"mode": "configured"}. If none, state that AdSense is not connected and stop.
2. **Earnings.** `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS"} (supply: accountId) — earnings/impressions by page or date.
3. **Organic overlay.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) — join on page.
4. **Correlate.** Rank pages by earnings and by organic clicks; find high-earning pages with weak organic and vice-versa.
5. **Assemble.** Verdict (where the money is), then the page × earnings × organic table.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (AdSense revenue is platform-reported, not an SEO estimate).

## Output
Begin with the **as-of line**. Verdict (which pages carry the revenue), then: a page table (page, AdSense earnings, organic clicks, position), and an action list. State clearly if AdSense is not connected.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
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

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth (Google + AdSense).

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
