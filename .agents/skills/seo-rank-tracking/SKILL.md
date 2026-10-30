---
name: seo-rank-tracking
description: Rank tracking without a tracker subscription — query-level position winners, losers, new and lost queries between two periods (or around a dated event) from real Search Console data, with the page that moved and optional Google-vs-Bing divergence. Use when asked "how are my rankings", "what moved this week/month", "track my keywords" or "did the update hit me".
license: MIT
compatibility: Requires the `search-console` MCP server; `dataforseo` (live SERP spot-check) is optional. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Rank Tracking

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Query-level position movement between two equal windows from the site's own GSC data; the page responsible for each big move.

## Report Audience & Purpose
<!--include:audience-->

- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel or content system — never a code-level fix referencing this repo's files.

<!--/include-->

## Memory-Bank Isolation
<!--include:memory-bank-->

While running this skill, do not read from or write to `memory-bank/` (repo-level exception recorded in `AGENTS.md`). Findings, evidence and reports stay in the run directory.

<!--/include-->

## When to Use
- "how are my rankings", "what moved this week/month"
- "track my keywords", "did the update hit me"

## When NOT to Use
- No `search-console` server configured
- Full site audit → `seo-audit`; declining pages → `seo-content-refresh`

## Requires
- **Required:** `search-console`.
- **Optional:** `dataforseo` (who took the spot); Bing in `search-console` (divergence). Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `web.search` | `tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query) | Web search fallback — not Google's ranking order; label as approximate |
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.compare_period` | `search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | Aggregate period-over-period delta |
| `gsc.compare_engines` | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) | Google vs Bing divergence (only when Bing is connected) |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data) | Live Google SERP incl. SERP features (featured snippet, PAA, AI Overview) *(optional, not configured)* |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`movers`), [`seo/rules.py`](../../../seo/rules.py) (`keywords`, `breakdown`).

## Workflow
<!--include:evidence days=28 flags=--compare-->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-rank-tracking --days 28 --compare --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

0. **Event split (when the user names an event).** Algorithm-update dates come **from the user** or from the Google Search Status Dashboard via <!--cap:web.search-->`tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query)<!--/cap--> (record it) — never from memory. With event date E, seed instead with `--days N --compare` where N = (today − 3) − E + 1, so the current window starts at E.
1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap-->.
2. **Rows.** For both periods: <!--cap:gsc.query-->`search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`query_cur`, `query_prev`). Current period: <!--cap:gsc.page_query-->`search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`pq_cur`). Aggregate: <!--cap:gsc.compare_period-->`search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate)<!--/cap-->.
3. **Movers.** `python3 seo/gsc_metrics.py movers --cur {run_dir}/data/query_cur.json --prev {run_dir}/data/query_prev.json --site <domain>` → winners/losers (position moved ≥ `mover_min_delta` on queries with ≥ `min_impressions`; losers sorted by clicks lost), new, lost, and `beyond_row_cutoff` (when a pull is truncated, these are not movements).
3b. **Tracked keywords and categories** (site rules, as in the SEO sheet). `python3 seo/rules.py --site <domain> keywords --query {run_dir}/data/query_cur.json --prev {run_dir}/data/query_prev.json` → the tracked set (Core, Brand, then automatic Proven / Opportunity / Generic picks) with position before → after and status (`New`, `Lost`, `No impressions`; `beyond row cutoff` when a pull is truncated). `python3 seo/rules.py --site <domain> breakdown --by category --cur {run_dir}/data/query_cur.json --prev {run_dir}/data/query_prev.json` → movement per service category (`low_volume` rows are noise). Picks use this run's window; the rules' `lookback_days` is the sheet's setting.
4. **Which page.** For the top 10 losers, the ranking pages from `pq_cur` (attribution only).
5. **Bing divergence (optional).** Only if diagnostics shows Bing connected: <!--cap:gsc.compare_engines-->`search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate)<!--/cap--> with `dimension: query` for the same window.
6. **SERP spot-check (optional).** DataForSEO configured → <!--cap:dfs.serp-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data)<!--/cap--> for the 3–5 most valuable losers ([payloads](../../../seo/references/dataforseo-payloads.md)); the section is a live snapshot (`window` note).

## Determinism
- Windows of equal length from `.run_state.json` (28 days is weekday-aligned). Query positions come from query rows, impression-weighted — never averaged from page rows.
- Thresholds from `gsc_metrics.py` defaults or profile `thresholds` (<!--site:thresholds-->`python3 seo/site_profile.py --site <domain> --get thresholds`<!--/site-->); quote them.

## Output
Provenance line first. **Verdict**: net movement and the single biggest move (and, for an update question, the before/after evidence around the dated event). Then four tables — Winners, Losers, New, Lost (query, position before → after, clicks delta, page) — plus "beyond the row cutoff" when present, then Tracked keywords (type, category, position before → after, status) and Categories.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-rank-tracking`.

<!--/include-->

## Fallbacks
- `gsc.compare_period` fails → aggregate from the two query pulls (state that anonymized queries are excluded).
- DataForSEO / Bing unavailable → skip steps 5–6 with `unavailable` entries.

## Recurring
If the user wants this weekly, suggest a scheduled run rather than re-running by hand.

## Pending Data Sources
- **DataForSEO** (optional, not configured): who took the spot for losers.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Losers list empty after an update | window too short or the update too recent | wait until the window holds ≥ 7 days after E; GSC data ends `today − 3` |
| Many "new" and "lost" queries | a pull was truncated | they move to `beyond_row_cutoff`; trust winners/losers only |
| Deltas look inverted | windows misaligned | always use the windows from `.run_state.json` |

## Files
<!--include:files-->

| File | Purpose | Action |
|---|---|---|
| [`seo/capabilities.json`](../../../seo/capabilities.json) | capability registry (single source of truth) | Read |
| [`seo/references/report-structure.md`](../../../seo/references/report-structure.md) | report contract + validation order | Read |
| [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md) | mandatory rules | Read |
| [`seo/references/data-source-map.md`](../../../seo/references/data-source-map.md) | freshness + the degradation rule | Read |
| [`seo/references/capability-usage.md`](../../../seo/references/capability-usage.md) | runtime args, GA4 filters, policy | Read |
| [`seo/references/domain-knowledge.md`](../../../seo/references/domain-knowledge.md) | methodology + thresholds | Read |
| [`seo/references/skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md) | shared troubleshooting | Read |
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence | Execute |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | render findings → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

<!--/include-->

Skill-specific: `seo/gsc_metrics.py` (Execute), `seo/rules.py` (Execute).

## Related / Delegation
- Full audit → `seo-audit`; declining pages → `seo-content-refresh`.
- PDF/email delivery → `report-export` (`--skill seo-rank-tracking`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `tavily`: `TAVILY_API_KEY` in `.roo/mcp.json` → `mcpServers.tavily.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: target domains/keywords/URLs are sent to Tavily (`tavily`), DataForSEO (`dataforseo`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
