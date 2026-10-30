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
| `ga4.properties` | `analytics` → `get_account_summaries` | GA4 accounts/properties (connection check) |
| `ga4.ai_sources` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter) | AI-assistant referral sessions (filter from `site_profile.py --ga4-ai-filter`) |
| `ga4.ai_time_series` | `analytics` → `run_report` {"dimensions": ["date", "sessionSource"], "metrics": ["sessions"]} (supply: property_id, date_ranges, dimension_filter) | Daily AI-assistant referral sessions (same AI filter) |
| `ga4.ai_cited_pages` | `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "keyEvents"]} (supply: property_id, date_ranges, dimension_filter) | Landing pages AI assistants send visitors to (same AI filter) |
| `ga4.channels` | `analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges) | Sessions/key events by channel and source (organic baseline) |
| `gsc.genai` | `search-console` → `genai_query_insights` {"engine": "google", "includePages": true} (supply: siteUrl, days) | AI-prompt-shaped GSC queries (heuristic; `days` = window length) |
| `web.extract` | `tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls) | Extract page content when `site_crawl.py facts` cannot fetch a page (JS-rendered/blocked) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.analytics_advanced` | `search-console` → `analytics_advanced` (supply: propertyId, metricType, startDate, endDate) | Aggregate GA4 metrics via search-console (no source breakdown) |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`robots`, `facts`), [`seo/site_profile.py`](../../../seo/site_profile.py) (`--ga4-ai-filter`).

## Workflow
<!--include:evidence days=28 flags=--compare-->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-ai-visibility --days 28 --compare --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap--> (required); <!--cap:ga4.properties-->`analytics` → `get_account_summaries`<!--/cap--> (optional — if it fails, skip steps 4–7 and add a GA4 `unavailable` entry).
2. **Crawler access.** `python3 seo/site_crawl.py robots --site https://<domain>` (record `--source site_crawl --name robots`). Blocking a **search/retrieval** agent (Googlebot, Bingbot, OAI-SearchBot, Claude-SearchBot, PerplexityBot, user fetchers) is critical; blocking **training** agents (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, CCBot) is a policy choice with no direct search effect. Note that WAF/CDN rules are not visible here.
3. **AI filter.** `python3 seo/site_profile.py --site <domain> --ga4-ai-filter` (record `--source site_profile --name ai_filter`) → the `dimension_filter` for steps 4–6. To track a new assistant, add its host to the profile — never edit a call spec.
4. **Referrals by assistant.** <!--cap:ga4.ai_sources-->`analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter)<!--/cap--> with `date_ranges` = current + comparison window. Label totals a **lower bound** (some AI visits arrive as direct or unlisted referrers).
5. **Trend.** <!--cap:ga4.ai_time_series-->`analytics` → `run_report` {"dimensions": ["date", "sessionSource"], "metrics": ["sessions"]} (supply: property_id, date_ranges, dimension_filter)<!--/cap--> (current window) — growth and spikes per assistant (a spike = something started citing a page; find which in step 6).
6. **Cited pages.** <!--cap:ga4.ai_cited_pages-->`analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "keyEvents"]} (supply: property_id, date_ranges, dimension_filter)<!--/cap--> — the landing pages assistants send people to, with key events: the proven-citable pages.
7. **Share and quality.** <!--cap:ga4.channels-->`analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges)<!--/cap--> (current + comparison) → **AI share of organic** = AI sessions ÷ `Organic Search` sessions (headline, lower bound); key-event rate of AI vs organic sessions.
8. **AI-shaped queries (heuristic).** <!--cap:gsc.genai-->`search-console` → `genai_query_insights` {"engine": "google", "includePages": true} (supply: siteUrl, days)<!--/cap--> with `days` = the window length (28). This tool uses its own lookback to the latest data: set that section's `window` note. Patterns only — never the headline.
9. **Citation recipe.** `python3 seo/site_crawl.py facts --url <top 3 cited pages>` (record). Compare `first_45_words` (direct answer?), `tables`, `jsonld.types`, `has_sameAs`, `has_author_or_reviewer` — that pattern is this site's citation recipe. If a page cannot be fetched, use <!--cap:web.extract-->`tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls)<!--/cap-->.
10. **Misses.** <!--cap:gsc.page-->`search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (current) → the 5 pages with the most organic clicks and zero AI referrals in step 6 (same paths) — restructure toward the recipe.

## Determinism
- One window (28 days vs the previous 28) from `.run_state.json`; GA4 `date_ranges` use exactly those dates.
- The AI host list comes only from the profile (`--ga4-ai-filter`); the regex also matches subdomains.
- AI share and conversion comparisons are computed from the recorded GA4 rows, never estimated.

## Output
Provenance line first. **Verdict**: AI share of organic (lower bound), trend, top assistant. Then: crawler-access table (bot, purpose, allowed?), assistant table (sessions, key events, change), trend, cited-pages table, AI-shaped queries (heuristic, own window), citation recipe, and the top-5 pages to restructure — each with the exact change.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-ai-visibility`.

<!--/include-->

## Fallbacks
- GA4 unavailable → crawler access + AI-shaped queries + citation recipe from step 9 on pages chosen by organic clicks; the report is labelled **heuristic, not measured**. <!--cap:gsc.analytics_advanced-->`search-console` → `analytics_advanced` (supply: propertyId, metricType, startDate, endDate)<!--/cap--> may add aggregate GA4 context but has no source breakdown — never use it for AI attribution.
- Page fetch blocked → `web.extract`; if both fail, list the page without recipe notes.

## Pending Data Sources
- **DataForSEO** (optional, not configured): AI Overview citation checks on live SERPs are not run.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| AI sessions = 0 but users report AI traffic | assistant strips the referrer, or host not in the `AI assistants` rule | keep the lower-bound label; add the host to that rule in the rules file |
| Robots verdict "VISIBILITY RISK" | a search/retrieval bot is disallowed | recommend allowing that token in robots.txt (and checking the CDN/WAF bot rules) |
| `facts` returns status 403/503 | bot protection on the site | use `web.extract`; mention the protection, which may also block AI crawlers |

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

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: target domains/keywords/URLs are sent to Tavily (`tavily`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.
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
