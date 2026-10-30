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
| `ads.search` | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings, login_customer_id) | GAQL query (search terms, account currency) |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `ads.customers` | `google-ads` → `customers_list_accessible_customers` | Accessible Ads customer IDs *(agent call, only when a step needs it)* |
| `ads.metadata` | `google-ads` → `metadata_get_resource_metadata` (supply: resource_name, login_customer_id) | GAQL field discovery (verify fields before querying) *(agent call, only when a step needs it)* |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) *(agent call, only when a step needs it)* |

<!--/include-->

Local tools: [`seo/ads_metrics.py`](../../../seo/ads_metrics.py) (`overlap`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-paid-organic --site <domain>`. It seeds the fixed, git-ignored run folder, makes every call in [`seo/plans/seo-paid-organic.json`](../../../seo/plans/seo-paid-organic.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. A call the plan does not make (a judgment step below): check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`.

<!--/include-->

1. **Account.** The plan uses the profile's Ads customer ID (<!--site:ads_customer_id-->`python3 seo/site_profile.py --site <domain> --get ads_customer_id`<!--/site-->; required — without it the pipeline stops: find it with <!--cap:ads.customers-->`google-ads` → `customers_list_accessible_customers`<!--/cap--> and set it in the profile). If access goes through a manager account, rerun with `--input login_customer_id=<manager ID> --force`. A GAQL field error → check fields with <!--cap:ads.metadata-->`google-ads` → `metadata_get_resource_metadata` (supply: resource_name, login_customer_id)<!--/cap--> (`search_term_view`, `customer`) — never guess GAQL fields.
2. **Paid search terms.** `data/terms.json` (search terms over the run window, by cost) in the currency of `data/currency.json`. The search-terms report omits low-volume terms (privacy thresholds) — say so.
3. **Organic.** `data/query_cur.json` over the same window. If campaigns target specific countries, compare like with like: an extra <!--cap:gsc.geo_query-->`search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> pull (recorded).
4. **Overlap.** `computed/overlap.json` → buckets `double_paying` (organic ≤ 3 + spend), `defend_check` (double-paying with ad absolute-top share < 50 %: competitors may bid — needs a manual SERP check), `paid_only_winners` (converting in Ads, no organic top-20: the content roadmap), `organic_only` (scale candidates), plus spend in the account currency.
5. **Savings (estimate).** Spend on `double_paying` is avoidable; the paid clicks organic would *not* recapture are the cost — shown for a heuristic 50–70 % recapture range (`computed/overlap.json`). Recommend a **holdout test** (pause the terms in one region or alternate weeks for 2–4 weeks; compare total paid + organic clicks and conversions) before cutting permanently.

## Determinism
- One 90-day window from `.run_state.json` for both sides; Ads `conditions` use exactly those dates.
- Joins are case/punctuation-insensitive (`ads_metrics.py`); money = `cost_micros ÷ 1,000,000` in `customer.currency_code`.

## Output
Provenance line first. **Headline**: "<currency> X over 90 days spent on terms you already rank top-3 for" (estimate of recoverable spend). Then the four bucket tables (term, cost, conversions, organic position), the savings range with its assumption, the holdout-test plan, and a short action list: exact negatives/bid changes to test, exact pages to build.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
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
| GAQL "unknown field" | field guessed or renamed | check the fields with `ads.metadata` (step 1), then fix the plan |
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
| [`seo/pipeline.py`](../../../seo/pipeline.py) | run the skill's data plan (`seo/plans/`): seed, pull, record, compute | Execute (first) |
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window (called by the pipeline) | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence (extra calls, derived figures) | Execute |
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

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the git-ignored run folder (`python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/             # <run_root>/<site>/<date>/<skill>/ (seo/runs.py; git-ignored)
  .run_state.json     # window + paths (seo/orchestrate.py)
  pipeline.json       # every plan step and its status (seo/pipeline.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  computed/*.json     # analysis outputs — the numbers the report may state (seo/pipeline.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
