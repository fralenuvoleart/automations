---
name: seo-audit
description: Whole-site SEO health audit from real Search Console (+ GA4) data — performance delta, declining pages, low-CTR and striking-distance quick wins, cannibalization, indexation spot-check, organic engagement and AI share. Use when asked to "audit my site", "SEO audit", "SEO health check" or "why is my organic traffic down".
license: MIT
compatibility: Requires the `search-console` MCP server; `analytics` (GA4) is optional. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# SEO Audit

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Whole-site macro health from the site's own GSC (+ GA4): performance delta, anomalies, declining pages, quick wins (striking distance + low CTR), cannibalization, indexation spot-check, organic engagement, AI share, local visibility when target markets are set. Deep dives are delegated (see Related).

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
- "audit my site", "SEO audit", "SEO health check"
- "why is my organic traffic down"
- Periodic site health review

## When NOT to Use
- No `search-console` server configured
- One page's speed or schema → `seo-technical`; one keyword's brief → `seo-content-brief`
- Competitor analysis → `seo-keyword-strategy` or `seo-backlink-check`

## Requires
- **Required:** `search-console` with the property verified (`google` reports ok in diagnostics).
- **Optional:** `analytics` (GA4) for the engagement and AI cross-checks. Missing optional sources follow the rule in [`data-source-map.md`](../../../seo/references/data-source-map.md).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `ga4.properties` | `analytics` → `get_account_summaries` | GA4 accounts/properties (connection check) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.compare_period` | `search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | Aggregate period-over-period delta |
| `gsc.daily_totals` | `search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Daily site totals, including anonymized queries (reconciliation baseline) |
| `gsc.anomalies` | `search-console` → `analytics_anomalies` {"engine": "google"} (supply: siteUrl, startDate, endDate) | Day-level anomaly detection |
| `gsc.compare_drop` | `search-console` → `analytics_compare` {"mode": "drop_attribution", "engine": "google"} (supply: siteUrl, startDate, endDate) | Drop attribution (which segments drove a decline) |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) |
| `gsc.inspect` | `search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls) | URL Inspection: coverage state, canonicals, last crawl (quota 2,000/day/property) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl) | Crawl/robots/sitemap blockers (report only the fields returned; not a site-wide index count) |
| `ga4.organic_landing_pages` | `analytics` → `run_report` {"dimensions": ["landingPagePlusQueryString"], "metrics": ["sessions", "engagementRate", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionDefaultChannelGroup", "string_filter": {"match_type": "EXACT", "value": "Organic Search", "case_sensitive": false}}}} (supply: property_id, date_ranges) | Organic-search landing pages: sessions, engagement, key events |
| `ga4.ai_sources` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter) | AI-assistant referral sessions (filter from `site_profile.py --ga4-ai-filter`) |
| `ga4.channels` | `analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges) | Sessions/key events by channel and source (organic baseline) |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py), [`seo/coverage.py`](../../../seo/coverage.py), [`seo/site_profile.py`](../../../seo/site_profile.py).

## Workflow
<!--include:evidence days=90 flags=--compare-->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-audit --days 90 --compare --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap--> (required — stop if it fails). <!--cap:ga4.properties-->`analytics` → `get_account_summaries`<!--/cap--> (optional — if it fails, add a `findings.unavailable` entry for GA4 and skip steps 8–9).
2. **Property.** <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap--> → the user's domain (`sc-domain:` preferred); ask only if ambiguous.
3. **Baseline.** <!--cap:gsc.compare_period-->`search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate)<!--/cap--> for the aggregate delta; <!--cap:gsc.daily_totals-->`search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> for both periods (`totals_cur`, `totals_prev`); <!--cap:gsc.anomalies-->`search-console` → `analytics_anomalies` {"engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> for the current period. If clicks fell, also <!--cap:gsc.compare_drop-->`search-console` → `analytics_compare` {"mode": "drop_attribution", "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap-->.
4. **Rows.** For both periods: <!--cap:gsc.query-->`search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`query_cur`, `query_prev`) and <!--cap:gsc.page-->`search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`page_cur`, `page_prev`); for the current period: <!--cap:gsc.page_query-->`search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`pq_cur`).
5. **Compute** (all `python3 seo/gsc_metrics.py … --site <domain>`, inputs from `{run_dir}/data/`):
   - `anonymized --totals totals_cur.json --rows query_cur.json` → share of clicks not attributable to queries (state it).
   - `decay --cur page_cur.json --prev page_prev.json` → **declining pages** with mutually exclusive classes (`vanished` / `ranking_loss` / `demand_drop` / `ctr_loss`); top 10 here, depth → `seo-content-refresh`.
   - `low-ctr --query query_cur.json` and `striking --query query_cur.json` → **quick wins** (top 5 of each, by impressions / missed clicks).
   - `cannibalization --page-query pq_cur.json` → apply the decision matrix in [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md).
   - Any output with `truncated: true` → report "beyond the row cutoff" items as such, never as movements.
6. **Local visibility (only when profile markets ≠ WORLDWIDE).** <!--site:markets-->`python3 seo/site_profile.py --site <domain> --get markets`<!--/site--> → <!--cap:gsc.geo_query-->`search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> for the current period; clicks/impressions per target country. For WORLDWIDE, skip and say so.
7. **Indexation spot-check.** <!--cap:gsc.inspect-->`search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls)<!--/cap--> for up to 5 declining pages (`vanished` and `ranking_loss` first): coverage state, Google vs declared canonical, last crawl. <!--cap:gsc.health-->`search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl)<!--/cap-->: report only the fields it returns — site-wide indexed/excluded counts are not available via the API (→ `seo-indexation`).
8. **Organic engagement (GA4, optional).** <!--cap:ga4.organic_landing_pages-->`analytics` → `run_report` {"dimensions": ["landingPagePlusQueryString"], "metrics": ["sessions", "engagementRate", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionDefaultChannelGroup", "string_filter": {"match_type": "EXACT", "value": "Organic Search", "case_sensitive": false}}}} (supply: property_id, date_ranges)<!--/cap--> with `date_ranges` = current + comparison window. Join landing paths to declining pages; call out pages that keep rankings but lose key events.
9. **AI share (GA4, optional).** `python3 seo/site_profile.py --site <domain> --ga4-ai-filter` → `dimension_filter` for <!--cap:ga4.ai_sources-->`analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter)<!--/cap-->; organic baseline from <!--cap:ga4.channels-->`analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges)<!--/cap-->. AI sessions ÷ Organic Search sessions = AI share (**lower bound**: some AI visits arrive as direct).
10. **Coverage.** `python3 seo/coverage.py --site <domain> --gsc {run_dir}/data/query_cur.json --gsc-pages {run_dir}/data/page_cur.json` → paste as `findings.coverage`.
11. <!--include:history-->

**Action history.** Before recommending, read `python3 seo/site_profile.py --site <domain> --history`: never re-recommend a `[done]` action; list open `[recommended]` ones as "previously recommended, still open". After the run, record each *new* recommendation with `--append-history "<action>" --status recommended` (exact duplicates are ignored). Use `--status done` only when the user confirms an action was carried out.

<!--/include-->

## Determinism
- One window for every call: 90 days vs the previous 90, from `.run_state.json` (GSC data ends `today − 3`).
- Thresholds come from `gsc_metrics.py` defaults, overridden only by the profile's `thresholds` (<!--site:thresholds-->`python3 seo/site_profile.py --site <domain> --get thresholds`<!--/site-->); quote the thresholds used.
- The aggregate delta comes from `gsc.compare_period`; every per-query/per-page number comes from `gsc_metrics.py` output.

## Output
Provenance line first. **Verdict** (healthy or not, and the #1 issue), then sections: Performance (delta, anomalies, drop attribution, anonymized share), Declining pages, Quick wins, Cannibalization, Indexation spot-check, Engagement & AI share (when GA4 is available), and **Coverage vs site profile**. End with a prioritized 5-item action list.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-audit`.

<!--/include-->

## Fallbacks
- `gsc.compare_period` / `gsc.anomalies` / `gsc.compare_drop` fail → compute the aggregate from the two `gsc.daily_totals` pulls and add `unavailable` entries for anomalies/drop attribution.
- GA4 unavailable → skip steps 8–9, add one `unavailable` entry ("engagement and AI share"). Never substitute third-party estimates.

## Pending Data Sources
- **DataForSEO** (optional, not configured): live SERP context for the worst pages is not run.
- **Google Business Profile** (not connected): map-pack visibility for local markets is out of reach.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Anonymized share > 50 % | many rare queries | query-level sections cover only part of traffic — state the share; page sections remain complete |
| Traffic down but no declining pages | drop spread thinly, or a demand shift | use the drop-attribution and anomaly output; consider `seo-rank-tracking` |
| `sites_list` shows two properties | URL-prefix and domain property both exist | use the `sc-domain:` property; note it in the verdict |

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

Skill-specific: `seo/gsc_metrics.py` (Execute), `seo/coverage.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- Declining pages in depth → `seo-content-refresh`; position movers → `seo-rank-tracking`.
- Brand vs non-brand → `seo-brand-split`; AI visibility in depth → `seo-ai-visibility`.
- Speed/schema/accessibility → `seo-technical`; index coverage and hreflang → `seo-indexation`.
- Paid vs organic overlap → `seo-paid-organic`.
- PDF/email delivery → `report-export` (`--skill seo-audit`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `analytics`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; the account must be added to the GA4 property.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.

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
