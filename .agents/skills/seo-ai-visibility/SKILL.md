---
name: seo-ai-visibility
description: Measure real AI-assistant visibility — referral sessions from ChatGPT, Perplexity, Claude, Gemini, Copilot and others, the pages they cite, AI share of organic, and whether AI search crawlers can reach the site — from GA4 data and robots.txt, not prompt sampling. Use when asked "AI visibility", "GEO/AEO check", "do LLMs cite us", "traffic from ChatGPT" or "how do we show up in AI search".
license: MIT
compatibility: Requires the `search-console` MCP server; `analytics` (GA4) supplies the headline metrics and is strongly recommended. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# AI Visibility

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- AI-assistant referral traffic (GA4), the landing pages assistants send people to, AI share of organic, AI-crawler access (robots.txt), and GSC's AI-shaped-query heuristic. Primary skill for this site's GEO work.

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
- "AI visibility", "GEO/AEO check", "do LLMs cite us"
- "traffic from ChatGPT", "how do we show up in AI search"

## When NOT to Use
- No `search-console` server configured
- General organic audit → `seo-audit`

## Requires
- **Required:** `search-console`.
- **Optional (headline):** `analytics` (GA4) with the service account on the property. Without it the report is **heuristic-only** (crawler access + AI-shaped queries), stated in Data availability. Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).
- The `AI assistants` channel rule in the site rules (`seo/config/rules/<domain>.json`) — the single list of assistant referrers (substring match on `sessionSource`, as in the SEO sheet).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `ga4.ai_sources` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter) | AI-assistant referral sessions (filter from `site_profile.py --ga4-ai-filter`) |
| `ga4.ai_time_series` | `analytics` → `run_report` {"dimensions": ["date", "sessionSource"], "metrics": ["sessions"]} (supply: property_id, date_ranges, dimension_filter) | Daily AI-assistant referral sessions (same AI filter) |
| `ga4.ai_cited_pages` | `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "keyEvents"]} (supply: property_id, date_ranges, dimension_filter) | Landing pages AI assistants send visitors to (same AI filter) |
| `ga4.landing_source` | `analytics` → `run_report` {"dimensions": ["landingPage", "sessionSourceMedium"], "metrics": ["sessions", "engagedSessions", "keyEvents"], "limit": 25000} (supply: property_id, date_ranges) | Sessions, engaged sessions and key events by landing page × source/medium (classified with the site rules: channel, page type, language) |
| `gsc.genai` | `search-console` → `genai_query_insights` {"engine": "google", "includePages": true} (supply: siteUrl, days) | AI-prompt-shaped GSC queries (heuristic; `days` = window length) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `ga4.channels` | `analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges) | Sessions/key events by channel and source (organic baseline) *(agent call, only when a step needs it)* |
| `web.extract` | `tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls) | Extract page content when `site_crawl.py facts` cannot fetch a page (JS-rendered/blocked) *(agent call, only when a step needs it)* |
| `gsc.analytics_advanced` | `search-console` → `analytics_advanced` (supply: propertyId, metricType, startDate, endDate) | Aggregate GA4 metrics via search-console (no source breakdown) *(agent call, only when a step needs it)* |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`robots`, `facts`), [`seo/site_profile.py`](../../../seo/site_profile.py) (`--ga4-ai-filter`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-ai-visibility --site <domain>`. It seeds the fixed run folder (outside git; `python3 seo/runs.py root` shows where), makes every call in [`seo/data-plans/seo-ai-visibility.json`](../../../seo/data-plans/seo-ai-visibility.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

1. **Crawler access.** `data/robots.json` — verdicts for the homepage and every priority page (`blocked_paths` names the pages a bot may not fetch). Blocking a **search/retrieval** agent (Googlebot, Bingbot, OAI-SearchBot, Claude-SearchBot, PerplexityBot, user fetchers) is critical; blocking **training** agents (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, CCBot) is a policy choice with no direct search effect. WAF/CDN rules are not visible here.
2. **Referrals by assistant.** `data/ai_sources.json` (current + comparison window), filtered with the profile's AI hosts — to track a new assistant, add its host to the `AI assistants` channel rule in `seo/config/rules/<domain>.json`, never edit a call spec. Label totals a **lower bound** (some AI visits arrive as direct or unlisted referrers).
3. **Trend.** `data/ai_trend.json` — growth and spikes per assistant (a spike = something started citing a page; find which in step 4).
4. **Cited pages.** `data/ai_cited.json` and `computed/cited_top.json` — the landing pages assistants send people to, with key events: the proven-citable pages.
5. **Share and quality.** `computed/channels.json` → **AI share of organic** = `ai_share_of_organic` (headline, lower bound); `key_event_rate` of the AI vs the organic channel — when `key_events_recorded` is false there is no rate: say key events are not set up (`key_events_note`). If the user compares with the GA4 UI (default channel group, not the site rules), pull <!--cap:ga4.channels-->`analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges)<!--/cap--> for the same windows (recorded) and show both.
6. **AI-shaped queries (heuristic).** `data/genai.json` — the tool uses its own lookback to the latest data: set that section's `window` note. Patterns only — never the headline.
7. **Citation recipe.** `data/cited_facts.json` (top 3 cited pages): compare `first_45_words` (direct answer?), `tables`, `jsonld.types`, `has_sameAs`, `has_author_or_reviewer` — that pattern is this site's citation recipe. A page that could not be fetched → <!--cap:web.extract-->`tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls)<!--/cap--> (record it).
8. **Misses.** `computed/misses.json` → the 5 pages with the most organic clicks and zero AI referrals — restructure them toward the recipe.

## Determinism
- One window (28 days vs the previous 28) from `.run_state.json`; GA4 `date_ranges` use exactly those dates.
- The AI host list comes only from the profile (`--ga4-ai-filter`); the regex also matches subdomains.
- AI share and conversion comparisons are computed from the recorded GA4 rows, never estimated.

## Output
Provenance line first. **Verdict**: AI share of organic (lower bound), trend, top assistant. Then: crawler-access table (bot, purpose, allowed?), assistant table (sessions, key events, change), trend, cited-pages table, AI-shaped queries (heuristic, own window), citation recipe, and the top-5 pages to restructure — each with the exact change.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-ai-visibility`.

<!--/include-->

## Fallbacks
- GA4 unavailable → crawler access + AI-shaped queries + the citation recipe (step 7) on the top 3 pages by organic clicks (the plan switches to `computed/organic_top.json` by itself); the report is labelled **heuristic, not measured**. <!--cap:gsc.analytics_advanced-->`search-console` → `analytics_advanced` (supply: propertyId, metricType, startDate, endDate)<!--/cap--> (record it) may add aggregate GA4 context but has no source breakdown — never use it for AI attribution.
- Page fetch blocked → `web.extract` (record it); if both fail, list the page without recipe notes.

## Pending Data Sources
- **DataForSEO** (optional, not configured): AI Overview citation checks on live SERPs are not run.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| AI sessions = 0 but users report AI traffic | assistant strips the referrer, or host not in the `AI assistants` rule | keep the lower-bound label; add the host to that rule in the rules file |
| Robots verdict "VISIBILITY RISK" | a search/retrieval bot is disallowed | recommend allowing that token in robots.txt (and checking the CDN/WAF bot rules) |
| `facts` returns status 403/503 | bot protection on the site | use `web.extract` (record it); mention the protection, which may also block AI crawlers |

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

Skill-specific: `seo/site_crawl.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- General organic audit → `seo-audit`; schema/entity markup → `seo-technical`.
- Writing a citable page → `seo-content-brief`.
- PDF/email delivery → `report-export` (`--skill seo-ai-visibility`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `analytics`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; the account must be added to the GA4 property.
- `tavily`: `TAVILY_API_KEY` in `.roo/mcp.json` → `mcpServers.tavily.env`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the run folder outside git (`run_root` in `seo/config/settings.json`; `python3 seo/runs.py root`); `python3 seo/runs.py prune` (or `pipeline.py --prune`) deletes runs and cache entries older than `retention_days`.
- Third-party calls: target domains/keywords/URLs are sent to Tavily (`tavily`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.
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
