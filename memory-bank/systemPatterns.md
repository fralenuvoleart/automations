# System Patterns


## 🛠️ Developer Working Method
- **Standard:** Modular, elegant, SEO-performant.
- **Verification:** Trace every claim through the full call chain before asserting a pattern is followed or a regression is avoided — use `search_files`/grep, never assume from a function name or comment alone.
- **Zero Regression Policy:** Check this file before every file write to ensure changes don't violate an established architectural invariant above.

---

## 🌐 Sevalla API Rules (Hard-Learned)

### Exec endpoint (`POST /v3/applications/{id}/processes/{pid}/exec`)

| Rule | Detail |
|---|---|
| **Always check OpenAPI spec first** | `curl -s https://api.sevalla.com/v3/openapi.json` — search for the endpoint path. Never guess the schema. |
| `command` is an **array of strings** | `["npm","run","warmer"]` not `"npm run warmer"` |
| `timeout` is **1–60 seconds** (integer) | Default 15. Sending 300 returns 400. Max is 60. |
| **No shell features** | No pipes, redirects, `&`, `nohup`, globbing. Use `sh -c "..."` as workaround. |
| **Long-running commands need backgrounding** | Use `["sh","-c","nohup <cmd> &"]` with `timeout:5`. Otherwise command gets killed at timeout. |
| **Short commands** (`ls`, `npm run logs`, `echo`) | Fine to run directly with default timeout. |
| Response format | `{"stdout":"...","stderr":"...","exit_code":0}` — not `"output"` or `"error"` |

### Deployment & Process behavior

| Rule | Detail |
|---|---|
| **Bot 409 conflict on deploy** | Old pod + new pod both poll Telegram. Fix: retry `bot.launch()` on 409 with delay. |
| **`bot.launch()` is a Promise** | Must be `await`ed or `.catch()`ed. Unhandled rejection crashes process in Node.js v24. |
| **Warmer & bot share process** | Cron warmer dies if bot crashes. Manual `npm run warmer` spawns separate process. |
| **Exec into crashed pod fails** | If the main process crashes, there's nothing to exec into. Exec requires a running container. |

---

## 🔎 SEO Skills — architecture & invariants

The 13 `seo-*` skills in `.agents/skills/` (12 reports + the weekly `seo-brief`) run on a multi-server MCP stack; every non-skill SEO file lives in [`seo/`](../seo/) ([README](../seo/README.md)).

**Registry + rendering.** [`seo/capabilities.json`](../seo/capabilities.json) is the single source of truth (server, tool, fixed `args`, `runtime`, `desc`, `policy`). Skills are authored with `{{cap:id}}`, `{{site:key}}` and `{{include:name}}` tokens; `python3 seo/resolve.py --write` renders them into `<!--cap:…-->…<!--/cap-->` blocks and **re-renders every block on each run** (registry edits and tool renames propagate). Never edit inside a block or hard-code tool names. Shared skill sections live in `seo/references/skill-common/`.

**Run pipeline (mandatory).** `seo/pipeline.py --skill S --site D` runs the skill's data plan (`seo/data-plans/<skill>[.<mode>].json`): seeds the run (`orchestrate.py`, window in `.run_state.json`), makes every MCP call cache-first through `mcp_client.Session` and records it (`record.py`: `context.json` + `data/`), runs the analysis scripts into `computed/`, writes `pipeline.json` and the `unavailable` list. The agent only interprets: findings JSON → `validate_report.py --data context.json` (URLs and every figure checked against `data/` + `computed/`) → `build_report.py` → validate the report. Extra (judgment) calls and derived figures are recorded with `record.py`.

| Concern | Server | Notes |
|---|---|---|
| GSC (queries, pages, compare, anomalies, inspection, sitemaps, keyword estimates, AI-query heuristic, PageSpeed/schema) | `search-console` | every `analytics_query` pins `rowLimit 25000` + `engine google`; `seo_audit` is not used (ignores windows) |
| GA4 (AI referrals, channels, organic landing pages, referrals) | `analytics` | metric `keyEvents` (not `conversions`); AI filter from the rules' `AI assistants` channel via `site_profile.py --ga4-ai-filter` |
| Google Ads (GAQL) | `google-ads` | only `seo-paid-organic` |
| Keyword Planner (ideas + historical metrics) | `google-ads-planner` | ≤20 seeds, ≤10 geos, first page only; retries only inside the server (`policy.retry 0`) |
| SERP / backlinks / labs | `dataforseo` | optional, not configured; payloads in `seo/references/dataforseo-payloads.md` |
| Web search / extract fallback | `tavily` | approximate; never Google's order |
| Link graph, hreflang, robots, page facts | local `seo/site_crawl.py` | stdlib, no key |

Rules:
- GSC: page metrics from `page` rows (include anonymized clicks), query metrics from `query` rows, `query×page` only for attribution; positions impression-weighted; truncated pulls (= row limit) never produce "lost/new".
- Windows: GSC ends `today − 3`, GA4 `today − 2`; tools without a window get a per-section `window` note. Weekly runs use Monday–Sunday weeks (`--weeks N`, listed in `window.weeks`, one pull per week — 8-week date-dimension pulls truncate on this site).
- Run folders are fixed: `<run_root>/<site>/<date>/<skill>[-<tag>]/` (`run_root` in `seo/config/settings.json` = `/home/francesco/Documents/seo-reports`, outside the repo; a root inside the repo must be git-ignored — `orchestrate.py` refuses one that could be committed). `seo/runs.py` lists, finds the latest report and prunes by `retention_days`.
- Shared cache (`record.py`): keyed by capability + full args per site; dated windows immutable, live tools per `policy.cache_ttl_days`, errors and undated live data never cached; `--from-cache` before each call.
- Findings actions are objects (`action`, `impact`, `effort`, `page`/`keyword`, `why`, `est_clicks`); `seo-brief` (`seo/digest.py`) merges the latest report of every skill, drops `[done]` history items, ranks impact × effort and tracks first-seen dates in `brief_state.json`.
- Page-level analyses merge `#fragment` jump links into their page (clicks summed, impressions from the largest variant) — `rules.collapse_fragments`.
- Classification has one source: `seo/config/rules/<domain>.json` (ported from the SEO sheet, which should read the same file). Brand, query category, page tag/language, channel and tracked keywords come only from `seo/rules.py`; the site profile holds facts only and derives `languages`/`sections`/`services`/`priority_keywords` from the rules. Rule regexes stay RE2/JS-portable. GA4 channels/page types/languages are classified with the same rules (`ga4_metrics.py`, capability `ga4.landing_source`).
- One degradation rule ([`data-source-map.md`](../seo/references/data-source-map.md)): required missing → stop; optional missing → `findings.unavailable`; never substitute estimates or memory.
- Side effects (Indexing API submissions, `[done]` history entries) only after explicit user confirmation.
- CI: `bash seo/check.sh` (offline, portable); `--live` adds live schema validation on the workstation.

---

*This file describes durable architectural rules, not a changelog. When a pattern changes, update the entry in place.*
