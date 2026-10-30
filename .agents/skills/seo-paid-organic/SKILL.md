---
name: seo-paid-organic
description: Find money leaking between Google Ads and SEO — search terms you pay for while already ranking top-3 organically, paid terms that convert with no organic coverage, and organic winners with no ads — in the account's currency, with a test plan before cutting spend. Use when asked "am I paying for clicks I'd get free", "brand bidding waste", "SEO vs ads overlap" or "cut wasted ad spend with SEO".
license: MIT
compatibility: Requires the `search-console` MCP server; the `google-ads` server supplies the paid half. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Paid vs Organic (Query Overlap & Waste Elimination)

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Overlap between Google Ads search terms and the site's organic Google queries over the same window; the only skill that uses the `google-ads` server.

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
- "am I paying for clicks I'd get free", "brand bidding waste"
- "SEO vs ads overlap", "cut wasted ad spend with SEO", "paid vs organic"

## When NOT to Use
- No `search-console` server configured
- Organic-only questions → `seo-audit`

## Requires
- **Required:** `search-console`.
- **Optional (paid half):** `google-ads`; without it, report the organic half only and name the missing connection. Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `ads.customers` | `google-ads` → `customers_list_accessible_customers` | Accessible Ads customer IDs |
| `ads.metadata` | `google-ads` → `metadata_get_resource_metadata` (supply: resource_name, login_customer_id) | GAQL field discovery (verify fields before querying) |
| `ads.search` | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings, login_customer_id) | GAQL query (search terms, account currency) |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) |

<!--/include-->

Local tools: [`seo/ads_metrics.py`](../../../seo/ads_metrics.py) (`overlap`).

## Workflow
<!--include:evidence days=90 flags=--->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-paid-organic --days 90 --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap--> (required). <!--cap:ads.customers-->`google-ads` → `customers_list_accessible_customers`<!--/cap--> → the Ads customer ID (ask if several). If access goes through a manager account, pass its ID as `login_customer_id` in every Ads call.
2. **Field check.** <!--cap:ads.metadata-->`google-ads` → `metadata_get_resource_metadata` (supply: resource_name, login_customer_id)<!--/cap--> for `search_term_view` and `customer` — never guess GAQL fields.
3. **Currency.** <!--cap:ads.search-->`google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings, login_customer_id)<!--/cap--> with `resource: customer`, `fields: [customer.currency_code]`.
4. **Paid search terms.** <!--cap:ads.search-->`google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings, login_customer_id)<!--/cap--> with `resource: search_term_view`, `fields: [search_term_view.search_term, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.absolute_top_impression_percentage]`, `conditions: ["segments.date BETWEEN '<startDate>' AND '<endDate>'"]` (run window), `orderings: ["metrics.cost_micros DESC"]`. The search-terms report omits low-volume terms (privacy thresholds) — say so.
5. **Organic.** <!--cap:gsc.query-->`search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> over the same window. If campaigns target specific countries, also <!--cap:gsc.geo_query-->`search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> and compare like with like.
6. **Overlap.** `python3 seo/ads_metrics.py overlap --ads {run_dir}/data/terms.json --query {run_dir}/data/query_cur.json --currency <code>` → buckets `double_paying` (organic ≤ 3 + spend), `defend_check` (double-paying with ad absolute-top share < 50 %: competitors may bid — needs a manual SERP check), `paid_only_winners` (converting in Ads, no organic top-20: the content roadmap), `organic_only` (scale candidates), plus spend in the account currency.
7. **Savings (estimate).** Spend on `double_paying` is avoidable; the paid clicks organic would *not* recapture are the cost — shown for a heuristic 50–70 % recapture range. Recommend a **holdout test** (pause the terms in one region or alternate weeks for 2–4 weeks; compare total paid + organic clicks and conversions) before cutting permanently.

## Determinism
- One 90-day window from `.run_state.json` for both sides; Ads `conditions` use exactly those dates.
- Joins are case/punctuation-insensitive (`ads_metrics.py`); money = `cost_micros ÷ 1,000,000` in `customer.currency_code`.

## Output
Provenance line first. **Headline**: "<currency> X over 90 days spent on terms you already rank top-3 for" (estimate of recoverable spend). Then the four bucket tables (term, cost, conversions, organic position), the savings range with its assumption, the holdout-test plan, and a short action list: exact negatives/bid changes to test, exact pages to build.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-paid-organic`.

<!--/include-->

## Fallbacks
- `google-ads` not configured → organic half only (top organic queries by clicks) and `unavailable` = `{source: google-ads, affects: paid half}`.
- Empty `search_term_view` → no spend in the window: the overlap analysis is moot, not failed — say so.

## Pending Data Sources
- None beyond `google-ads`.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| GAQL "unknown field" | field guessed | run step 2 first |
| `USER_PERMISSION_DENIED` | access through a manager account | pass `login_customer_id` |
| No overlap found | ads target another market/language | compare against `gsc.geo_query` for the ad countries |

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

Skill-specific: `seo/ads_metrics.py` (Execute).

## Related / Delegation
- Organic-only view → `seo-audit`; pages for paid-only winners → `seo-content-brief`.
- PDF/email delivery → `report-export` (`--skill seo-paid-organic`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `google-ads`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; pass `login_customer_id` when access is through a manager account.

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
