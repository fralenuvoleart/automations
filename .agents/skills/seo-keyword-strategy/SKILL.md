---
name: seo-keyword-strategy
description: Keyword strategy from real data — the site's striking-distance footholds valued with its own CTR curve and Keyword Planner volumes/CPC, related-keyword expansion per language, and a competitor keyword gap — clustered into a tiered roadmap. Use when asked "keyword strategy", "keyword research", "find keywords", "keyword gap", "traffic value" or "striking distance opportunities".
license: MIT
compatibility: Requires the `search-console` MCP server. `google-ads-planner` (with profile `ads_customer_id`) and `dataforseo` are optional enrichments. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Keyword Strategy (Research, Opportunity Sizing & Gap)

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Keyword roadmap per language: footholds (striking distance), their estimated value, expansions, and competitor gap — from GSC, the Keyword Planner and (optionally) DataForSEO.

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
- "keyword strategy", "keyword research", "build a keyword plan"
- "what should I rank for", "striking distance keywords", "opportunity sizing"
- "keyword gap vs competitor", "traffic value"

## When NOT to Use
- A brief for one keyword → `seo-content-brief`
- Movement of existing rankings → `seo-rank-tracking`
- No `search-console` server configured

## Requires
- **Required:** `search-console`.
- **Optional:** `google-ads-planner` + profile `ads_customer_id` (<!--site:ads_customer_id-->`python3 seo/site_profile.py --site <domain> --get ads_customer_id`<!--/site-->; if missing, ask the user for the Ads customer ID or degrade); `dataforseo` for the competitor gap. Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).
- Seeds: the user's topic, else profile `priority_keywords` (<!--site:priority_keywords-->`python3 seo/site_profile.py --site <domain> --get priority_keywords`<!--/site-->, per language with `--lang`) and `services` (<!--site:services-->`python3 seo/site_profile.py --site <domain> --get services`<!--/site-->).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `planner.ideas` | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner ideas: volume, competition, bids (≤20 seeds per call; server retries internally) |
| `gsc.keywords_related` | `search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country) | Related keyword expansion (volumes are estimates) |
| `planner.historical` | `google-ads-planner` → `keyword_historical_metrics` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner metrics for an exact keyword list (≤1,000 per call) |
| `gsc.keywords_stats` | `search-console` → `seo_keywords_research` {"type": "stats", "engine": "google"} (supply: keywords, language, country) | Keyword volume estimates (planner fallback; label as estimates) |
| `dfs.ranked_keywords` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) | Keywords a domain ranks for (estimate) *(optional, not configured)* |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`striking`, `curve`, `value`), [`seo/dfs_metrics.py`](../../../seo/dfs_metrics.py) (`keyword-gap`), [`seo/coverage.py`](../../../seo/coverage.py), [`seo/rules.py`](../../../seo/rules.py) (`keywords`).

## Workflow
<!--include:evidence days=90 flags=--->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-keyword-strategy --days 90 --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap-->.
2. **Footholds.** <!--cap:gsc.query-->`search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (current) → `python3 seo/gsc_metrics.py striking --query {run_dir}/data/query_cur.json --site <domain>` and `… curve …` (the site's own non-brand CTR by position).
3. **Expansion (per language).** Planner available and `ads_customer_id` set: <!--cap:planner.ideas-->`google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets)<!--/cap--> with seeds in batches of **≤ 20**, `language` = <!--site:ads_language_constants-->`python3 seo/site_profile.py --site <domain> --get ads_language_constants`<!--/site--> (`--lang <code>`), `geo_targets` = <!--site:ads_geo_targets-->`python3 seo/site_profile.py --site <domain> --get ads_geo_targets`<!--/site--> (empty = all locations). Otherwise <!--cap:gsc.keywords_related-->`search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country)<!--/cap--> with `language`/`country` codes → **estimates**.
4. **Metrics for footholds.** Striking-distance queries → <!--cap:planner.historical-->`google-ads-planner` → `keyword_historical_metrics` (supply: customer_id, keywords, language, geo_targets)<!--/cap--> (≤ 1,000 per call, same language/geo); fallback <!--cap:gsc.keywords_stats-->`search-console` → `seo_keywords_research` {"type": "stats", "engine": "google"} (supply: keywords, language, country)<!--/cap--> (**estimates**).
5. **Value.** `python3 seo/gsc_metrics.py value --planner {run_dir}/data/hist_<lang>.json --query {run_dir}/data/query_cur.json --site <domain>` → estimated monthly clicks gain and value at target position 3 (site CTR curve; heuristic only for buckets without site data; CPC = mid of top-of-page bids, account currency). Label **estimate**.
6. **Competitor gap (optional).** Competitor named or in <!--site:competitors-->`python3 seo/site_profile.py --site <domain> --get competitors`<!--/site-->; DataForSEO configured → <!--cap:dfs.ranked_keywords-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data)<!--/cap--> ([payloads](../../../seo/references/dataforseo-payloads.md)) → `python3 seo/dfs_metrics.py keyword-gap --ranked {run_dir}/data/ranked.json --query {run_dir}/data/query_cur.json` → their keywords where the site has no impressions.
7. **Roadmap.** Tier 1 = footholds with value (on-page refresh + internal links); Tier 2 = gap keywords matching a service line (new pages); Tier 3 = long-tail questions from expansion (supporting articles). Drop off-topic terms regardless of volume.
8. **Coverage.** `python3 seo/coverage.py --site <domain> --gsc {run_dir}/data/query_cur.json` → `findings.coverage` (priority keywords with/without impressions).
9. **Tracked set.** <!--cap:gsc.geo_query-->`search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`geo_cur`), then `python3 seo/rules.py --site <domain> keywords --query {run_dir}/data/query_cur.json --countries {run_dir}/data/geo_cur.json` → the tracked keywords the SEO sheet would pick from this window (Core, Brand, Proven, Opportunity, Generic) with each keyword's top 3 countries (use them for the market angle of Tier 1–3: language, examples, landing page), and `unclassified_to_review` (queries no category rule matches). Propose rule or Core-keyword changes to the user; never edit `seo/config/rules/<domain>.json` without confirmation.
10. <!--include:history-->

**Action history.** Before recommending, read `python3 seo/site_profile.py --site <domain> --history`: never re-recommend a `[done]` action; list open `[recommended]` ones as "previously recommended, still open". After the run, record each *new* recommendation with `--append-history "<action>" --status recommended` (exact duplicates are ignored). Use `--status done` only when the user confirms an action was carried out.

<!--/include-->

## Determinism
- GSC window: last 90 days from `.run_state.json`; planner calls carry explicit language/geo from the profile.
- Values come only from `gsc_metrics.py value`; the CTR source (site vs heuristic) is shown per row.

## Output
Provenance line first. **Verdict**: highest-value cluster and the total estimated value of Tier 1. Then: Tier 1 table (query, position, volume, est. clicks gain, est. value, CTR source), Tier 2 gap table, Tier 3 topics, per-language notes, and proposed changes to the tracked set / category rules. All planner/value numbers labelled estimates (`"estimate": true`).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-keyword-strategy`.

<!--/include-->

## Fallbacks
- Planner unavailable, quota exhausted (`RESOURCE_EXHAUSTED` after the server's own retries), or no `ads_customer_id` → `gsc.keywords_related` / `gsc.keywords_stats` estimates; one `unavailable` entry. Do not loop.
- DataForSEO not configured → skip step 6; `unavailable` = `{source: dataforseo, affects: competitor keyword gap}`.

## Pending Data Sources
- **DataForSEO** (optional, not configured): competitor ranked keywords and SERP difficulty.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Planner "Too many keywords" | > 20 seeds (ideas) or > 1,000 (historical) | batch |
| Planner `RESOURCE_EXHAUSTED` | per-customer quota | the server already retried within its budget; fall back (keep `PLANNER_MAX_RETRY_SECONDS` below ~55 s or the client times out) |
| `value` rows show `target_ctr: null` | no site data and no heuristic for that target bucket | use target 1–4 or report "insufficient data" |

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

Skill-specific: `seo/gsc_metrics.py`, `seo/dfs_metrics.py`, `seo/coverage.py`, `seo/rules.py`, `seo/site_profile.py` (Execute).

## Related / Delegation
- One keyword's brief → `seo-content-brief`.
- Cannibalization / declining pages → `seo-audit` or `seo-content-refresh`.
- PDF/email delivery → `report-export` (`--skill seo-keyword-strategy`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `google-ads-planner`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; customer ID from the site profile `ads_customer_id`.
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

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
