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
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.compare_period` | `search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | Aggregate period-over-period delta |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data) | Live Google SERP incl. SERP features (featured snippet, PAA, AI Overview) *(optional, not configured)* |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `web.search` | `tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query) | Web search fallback — not Google's ranking order; label as approximate *(agent call, only when a step needs it)* |
| `gsc.compare_engines` | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) | Google vs Bing divergence (only when Bing is connected) *(agent call, only when a step needs it)* |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`movers`), [`seo/rules.py`](../../../seo/rules.py) (`keywords`, `breakdown`, `targets`, `trend`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-rank-tracking --site <domain>`. It seeds the fixed run folder (outside git; `python3 seo/runs.py root` shows where), makes every call in [`seo/data-plans/seo-rank-tracking.json`](../../../seo/data-plans/seo-rank-tracking.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

0. **Event split (when the user names an event).** Algorithm-update dates come **from the user** or from the Google Search Status Dashboard via <!--cap:web.search-->`tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query)<!--/cap--> (record it) — never from memory. With event date E, run the plan with `--days N --compare --tag event` where N = (today − 3) − E + 1, so the current window starts at E.
1. **Aggregate.** `data/compare.json` → clicks, impressions, CTR and position, period over period. Missing → `computed/totals.json` (from the query rows: anonymized queries excluded — say so).
2. **Movers.** `computed/movers.json` → winners/losers (position moved ≥ `mover_min_delta` on queries with ≥ `min_impressions`; losers sorted by clicks lost), new, lost, and `beyond_row_cutoff` (when a pull is truncated, these are not movements).
3. **Tracked keywords and categories** (site rules, as in the SEO sheet). `computed/keywords.json` → the tracked set (Core, Brand, then automatic Proven / Opportunity / Generic picks) with position before → after, status (`New`, `Lost`, `No impressions`; `beyond row cutoff` when a pull is truncated) and top 3 countries (which market each keyword serves). `computed/categories.json` → movement per service category (`low_volume` rows are noise). Picks use this run's window; the rules' `lookback_days` is the sheet's setting.
4. **Target pages.** `computed/targets.json` → report `wrong page` (Google shows another page more often — name it, with both positions) and `target not ranking` first; fixes: internal links and anchors to the target, align titles/H1, or change the target in the rules if the ranking page is the better answer.
5. **Which page.** For the top 10 losers, the ranking pages from `data/pq_cur.json` (attribution only).
6. **Bing divergence (optional).** Only if `data/diagnostics.json` shows Bing connected: <!--cap:gsc.compare_engines-->`search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate)<!--/cap--> with `dimension: query` for the same window (record it).
7. **SERP spot-check.** `data/serp_*.json` (DataForSEO, the top 5 losers) → who took the spot; the section is a live snapshot (`window` note).
8. **Weekly mode** (the SEO sheet's weekly report — use when asked for the weekly report, "this week" or a trend): `python3 seo/pipeline.py --skill seo-rank-tracking --site <domain> --mode weekly` ([plan](../../../seo/data-plans/seo-rank-tracking.weekly.json)) — 8 Monday–Sunday weeks ending with the latest complete week (`window.weeks`), one query and one page pull per week (a single 8-week query × date pull exceeds the 25,000-row limit on this site). Then:
   - `computed/trend_category.json`, `trend_keyword.json`, `trend_page_tag.json`, `trend_language.json` → week-by-week clicks, impressions and position (`low_volume` cells are noise, never trends);
   - week vs previous week: `computed/movers.json` (step 2), `keywords.json` (step 3) and `targets.json` (step 4).

## Determinism
- Windows of equal length from `.run_state.json` (28 days is weekday-aligned; weekly mode uses calendar Monday–Sunday weeks, as in the SEO sheet). Query positions come from query rows, impression-weighted — never averaged from page rows.
- Thresholds from `gsc_metrics.py` defaults or profile `thresholds` (<!--site:thresholds-->`python3 seo/site_profile.py --site <domain> --get thresholds`<!--/site-->); quote them.

## Output
Provenance line first. **Verdict**: net movement and the single biggest move (and, for an update question, the before/after evidence around the dated event). Then four tables — Winners, Losers, New, Lost (query, position before → after, clicks delta, page) — plus "beyond the row cutoff" when present, then Tracked keywords (type, category, position before → after, status, top countries), Target pages (problems first) and Categories. Weekly mode adds the 8-week trend tables (category, page type, language, tracked keywords; latest week last).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-rank-tracking`.

<!--/include-->

## Fallbacks
- `gsc.compare_period` fails → `computed/totals.json` (from the two query pulls; state that anonymized queries are excluded).
- DataForSEO unavailable → the pipeline lists it in `unavailable` (step 7); Bing not connected → skip step 6 and add an `unavailable` entry.

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
| [`seo/pipeline.py`](../../../seo/pipeline.py) | run the skill's data plan (`seo/data-plans/`): seed, pull, record, compute | Execute (first) |
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window (called by the pipeline) | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence (extra calls, derived figures) | Execute |
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
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.
- `tavily`: `TAVILY_API_KEY` in `.roo/mcp.json` → `mcpServers.tavily.env`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the run folder outside git (`run_root` in `seo/config/settings.json`; `python3 seo/runs.py root`); `python3 seo/runs.py prune` (or `pipeline.py --prune`) deletes runs and cache entries older than `retention_days`.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`), Tavily (`tavily`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/             # <run_root>/<site>/<date>/<skill>/ (seo/runs.py; outside git)
  .run_state.json     # window + paths (seo/orchestrate.py)
  pipeline.json       # every plan step and its status (seo/pipeline.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  computed/*.json     # analysis outputs — the numbers the report may state (seo/pipeline.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
