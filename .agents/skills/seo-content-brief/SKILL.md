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
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data) | Live Google SERP incl. SERP features (featured snippet, PAA, AI Overview) *(optional, not configured)* |
| `web.search` | `tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query) | Web search fallback — not Google's ranking order; label as approximate |
| `web.extract` | `tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls) | Extract page content when `site_crawl.py facts` cannot fetch a page (JS-rendered/blocked) |
| `planner.ideas` | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner ideas: volume, competition, bids (≤20 seeds per call; server retries internally) |
| `gsc.keywords_related` | `search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country) | Related keyword expansion (volumes are estimates) |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`facts`), [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`topic`).

## Workflow
<!--include:evidence days=90 flags=--->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-content-brief --days 90 --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap-->.
2. **The SERP.**
   - DataForSEO configured: <!--cap:dfs.serp-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data)<!--/cap--> with the payload in [`dataforseo-payloads.md`](../../../seo/references/dataforseo-payloads.md); `location_code` from <!--site:serp_locations-->`python3 seo/site_profile.py --site <domain> --get serp_locations`<!--/site--> for the keyword's language — if unset, ask the user which market to sample. Gives order + SERP features (featured snippet, PAA, AI Overview).
   - Otherwise: <!--cap:web.search-->`tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query)<!--/cap--> with the keyword → label the section "**approximate SERP (web search, not Google's order); SERP features unknown**" and add an `unavailable` entry for DataForSEO.
3. **Top pages.** `python3 seo/site_crawl.py facts --url <top 3 organic URLs>` (record `--source site_crawl --name serp_facts`): headings, word count, first 45 words, tables, schema types. If a page cannot be fetched, <!--cap:web.extract-->`tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls)<!--/cap-->.
4. **Keyword set.**
   - Planner available and <!--site:ads_customer_id-->`python3 seo/site_profile.py --site <domain> --get ads_customer_id`<!--/site--> set: <!--cap:planner.ideas-->`google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets)<!--/cap--> with ≤ 20 seeds, `language` = <!--site:ads_language_constants-->`python3 seo/site_profile.py --site <domain> --get ads_language_constants`<!--/site--> (`--lang <code>`), `geo_targets` = <!--site:ads_geo_targets-->`python3 seo/site_profile.py --site <domain> --get ads_geo_targets`<!--/site--> (empty = all locations).
   - Otherwise: <!--cap:gsc.keywords_related-->`search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country)<!--/cap--> with `language`/`country` codes → label volumes **estimates**.
5. **Existing foothold.** <!--cap:gsc.page_query-->`search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (current) → `python3 seo/gsc_metrics.py topic --page-query {run_dir}/data/pq_cur.json --terms "<main terms, comma-separated>"`. If one existing page already gets impressions for the cluster, recommend **expanding that page** instead of a new one (avoids cannibalization). Pages ranking for adjacent queries are the internal-link sources.
6. **Assemble the brief:**
   - Target + secondary keywords (volumes labelled), intent and format inferred from what ranks.
   - SERP feature target — only when features are known from step 2 (definition ≤ 45 words, table, or list). Never promise FAQ/HowTo rich results (no longer shown by Google).
   - Title (~50–60 characters, key phrase first; Google truncates by pixel width) and meta description (~150 characters).
   - H2/H3 outline, each with one line on what it must say; questions to answer (PAA if known, else question-form related keywords).
   - Table stakes (what all top pages cover) vs the differentiating angle (what none cover).
   - GEO checklist: direct answer in the first ~45 words, specific dated numbers with sources, a comparison table, entity markup (`Organization` + `sameAs`, author/reviewer) — see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md).
   - Internal links: 3–5 source pages from step 5 with natural anchors in the page's language.
   - Target length: median `word_count` of the top 3 (from step 3) — match, don't pad.

## Determinism
- GSC window: last 90 days (from `.run_state.json`). SERP and page facts are live snapshots: set the section `window` note "SERP/page snapshot, <date>".
- Volumes: planner first, `seo_keywords_research` second (labelled estimates); never mixed in one table without a source column.

## Output
Provenance line first. **Verdict**: create vs expand (and which page), and the winning angle. Then the brief sections from step 6, ready to hand to a writer.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-content-brief`.

<!--/include-->

## Fallbacks
- No DataForSEO → web-search SERP, labelled approximate; no SERP-feature target.
- Planner unavailable, `RESOURCE_EXHAUSTED`, or no `ads_customer_id` → `gsc.keywords_related` volumes labelled estimates (the planner server already retried; do not loop).

## Pending Data Sources
- **DataForSEO** (optional, not configured): Google's real order and SERP features.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Planner error "Too many keywords" | more than 20 seeds | batch seeds in groups of ≤ 20 |
| `topic` returns nothing | terms too specific or wrong script | use 1–2 stem terms in the page's language (prefix match handles inflection) |
| Top pages unreachable | bot protection | `web.extract`, else list the URL without structure notes |

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

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`), Tavily (`tavily`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.
- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).

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
