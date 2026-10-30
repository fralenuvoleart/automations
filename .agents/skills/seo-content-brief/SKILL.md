---
name: seo-content-brief
description: SERP-driven content brief for one target keyword — what ranks, what to cover, outline, questions, the site's existing foothold, internal links and a GEO citability checklist. Use when asked for a "content brief", "outline to rank for X", "what should this article cover", or before writing any SEO page.
license: MIT
compatibility: Requires the `search-console` MCP server. `dataforseo` (live SERP), `tavily` (web-search fallback) and `google-ads-planner` (volumes) are optional enrichments. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Content Brief

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- A brief for **one** target keyword in **one** language, grounded in a recorded SERP, the top pages' structure, and the site's own GSC foothold.

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
- "content brief", "outline to rank for X"
- "what should this article cover"
- Before writing any SEO page

## When NOT to Use
- No `search-console` server configured
- Planning across many topics → `seo-keyword-strategy`

## Requires
- **Required:** `search-console`; the target keyword and its language (ask if not given — it decides the market and language codes).
- **Optional:** `dataforseo` (live Google SERP with features) → else `tavily` web search (approximate); `google-ads-planner` + profile `ads_customer_id` (volumes). Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data) | Live Google SERP incl. SERP features (featured snippet, PAA, AI Overview) *(optional, not configured)* |
| `web.search` | `tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query) | Web search fallback — not Google's ranking order; label as approximate |
| `planner.ideas` | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner ideas: volume, competition, bids (≤20 seeds per call; server retries internally) |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `web.extract` | `tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls) | Extract page content when `site_crawl.py facts` cannot fetch a page (JS-rendered/blocked) *(agent call, only when a step needs it)* |
| `gsc.keywords_related` | `search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country) | Related keyword expansion (volumes are estimates) *(agent call, only when a step needs it)* |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`facts`), [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`topic`).

## Workflow
<!--include:evidence flags=--input_keyword="<keyword>"-->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-content-brief --site <domain> --input keyword="<keyword>"`. It seeds the fixed run folder (outside git; `python3 seo/runs.py root` shows where), makes every call in [`seo/data-plans/seo-content-brief.json`](../../../seo/data-plans/seo-content-brief.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

1. **The SERP.** `data/serp.json` (DataForSEO; market = the keyword's language in <!--site:serp_locations-->`python3 seo/site_profile.py --site <domain> --get serp_locations`<!--/site-->) → order + SERP features (featured snippet, PAA, AI Overview). Only `data/web_serp.json` (web-search fallback) → label the section "**approximate SERP (web search, not Google's order); SERP features unknown**" (the DataForSEO gap is already in `unavailable`). Neither (no `serp_locations` entry for the language) → ask the user which market to sample.
2. **Top pages.** `data/serp_facts.json` (top 3 organic URLs): headings, word count, first 45 words, tables, schema types. The crawler respects each site's robots.txt: a page marked `skipped` was not fetched — use <!--cap:web.extract-->`tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls)<!--/cap--> (record it) or list it without structure notes; same for a page that could not be fetched.
3. **Keyword set.** `data/ideas_*.json` (Keyword Planner, seeds ≤ 20, language <!--site:ads_language_constants-->`python3 seo/site_profile.py --site <domain> --get ads_language_constants`<!--/site-->, geo <!--site:ads_geo_targets-->`python3 seo/site_profile.py --site <domain> --get ads_geo_targets`<!--/site-->). Planner unavailable → <!--cap:gsc.keywords_related-->`search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country)<!--/cap--> with `language`/`country` codes (record it) → label volumes **estimates**.
4. **Existing foothold.** `computed/foothold.json` (pages with impressions on the keyword's terms). If one existing page already gets impressions for the cluster, recommend **expanding that page** instead of a new one (avoids cannibalization). Pages ranking for adjacent queries are the internal-link sources. To widen the terms: `python3 seo/gsc_metrics.py topic --page-query {run_dir}/data/pq_cur.json --terms "<main terms, comma-separated>"`, recorded as `--source derived`.
5. **Assemble the brief:**
   - Target + secondary keywords (volumes labelled), intent and format inferred from what ranks.
   - SERP feature target — only when features are known from step 1 (definition ≤ 45 words, table, or list). Never promise FAQ/HowTo rich results (no longer shown by Google).
   - Title (~50–60 characters, key phrase first; Google truncates by pixel width) and meta description (~150 characters).
   - H2/H3 outline, each with one line on what it must say; questions to answer (PAA if known, else question-form related keywords).
   - Table stakes (what all top pages cover) vs the differentiating angle (what none cover).
   - GEO checklist: direct answer in the first ~45 words, specific dated numbers with sources, a comparison table, entity markup (`Organization` + `sameAs`, author/reviewer) — see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md).
   - Internal links: 3–5 source pages from step 4 with natural anchors in the page's language.
   - Target length: median `word_count` of the top 3 (from step 2) — match, don't pad.

## Determinism
- GSC window: last 90 days (from `.run_state.json`). SERP and page facts are live snapshots: set the section `window` note "SERP/page snapshot, <date>".
- Volumes: planner first, `seo_keywords_research` second (labelled estimates); never mixed in one table without a source column.

## Output
Provenance line first. **Verdict**: create vs expand (and which page), and the winning angle. Then the brief sections from step 5, ready to hand to a writer.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-content-brief`.

<!--/include-->

## Fallbacks
- No DataForSEO → web-search SERP, labelled approximate; no SERP-feature target.
- Planner unavailable, `RESOURCE_EXHAUSTED`, or no `ads_customer_id` → `gsc.keywords_related` (record it) volumes labelled estimates (the planner server already retried; do not loop).

## Pending Data Sources
- **DataForSEO** (optional, not configured): Google's real order and SERP features.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Planner error "Too many keywords" | more than 20 seeds | batch seeds in groups of ≤ 20 |
| `topic` returns nothing | terms too specific or wrong script | use 1–2 stem terms in the page's language (prefix match handles inflection) |
| Top pages unreachable | bot protection | `web.extract` (record it), else list the URL without structure notes |

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

Skill-specific: `seo/site_crawl.py` (Execute), `seo/gsc_metrics.py` (Execute), [`seo/references/dataforseo-payloads.md`](../../../seo/references/dataforseo-payloads.md) (Read).

## Related / Delegation
- Many topics / roadmap → `seo-keyword-strategy`.
- Refreshing an existing page → `seo-content-refresh`.
- PDF/email delivery → `report-export` (`--skill seo-content-brief`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.
- `tavily`: `TAVILY_API_KEY` in `.roo/mcp.json` → `mcpServers.tavily.env`.
- `google-ads-planner`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; customer ID from the site profile `ads_customer_id`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the run folder outside git (`run_root` in `seo/config/settings.json`; `python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`), Tavily (`tavily`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.
- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).

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
