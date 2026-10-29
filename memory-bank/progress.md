# Project Progress

## Completed

- [x] Repo restructuring to `automations/` layout
- [x] Cache warmer rewritten from Python to JavaScript
- [x] All production-readiness fixes applied (P0/P1/P2)
- [x] Telegram bot operational (auto-reply, forwarding, Integrately webhook)
- [x] Descriptive file naming: `telegram-bot.js`, `cache-warmer.js`
- [x] `index.js` simplified to wiring layer (imports + cron)
- [x] Old `pbs-telegram/` directory cleaned up
- [x] Cache warmer documentation created: `docs/WARMER.md` — covers logic, cache headers, analytics discrepancy explanation
- [x] Cache warmer granular stats: HTTP status code breakdown, redirect tracking, uppercase cache labels
- [x] Forwarded message deep link in Integrately webhook (captures `message_id` from `forwardMessage`, constructs `https://t.me/c/` link, added `forwardedMessageLink` + `userChatLink` fields)
- [x] Delayed second auto-reply: configurable delay (default 20s), resets on new user messages, `secondAutoreply` message template with env var overrides
- [x] CDN/Edge cache tracking clarified as diagnostic-only — `npm run status` now shows UNKNOWN counts; WARMER.md documents why CDN/Edge can't be warmed from Sevalla
- [x] Fixed script naming: `sevalla-summary.sh` → formatted summary, `sevalla-status.sh` → live progress only
- [x] Relay mode for hidden-profile users — implemented in [`telegram-bot.js`](../services/nodejs/src/telegram-bot.js), plan at [`plans/relay-mode-hidden-users.md`](../plans/relay-mode-hidden-users.md)
- [x] `sevalla-summary.sh` — AM/PM (UTC) time format + failed URLs list with reason
- [x] Warmer status — `YYYY-MM-DD hh:mm AM/PM (UTC)` time format in [`sevalla-status.sh`](../services/nodejs/scripts/sevalla-status.sh) and `npm run status` ([`package.json`](../services/nodejs/package.json))
- [x] Merged collaborator commit `bcc9ab7` (respond.io outgoing `/respond/outgoing/message` path) into `main` and pushed to `origin/main`
- [x] Installed Ryze SEO MCP connector (`ryze`, streamable-http) in [`.roo/mcp.json`](../.roo/mcp.json) + 8 SEO/GEO skills in [`.agents/skills/`](../.agents/skills/) from `Ryze-AI-Adgent/open-seo-mcp-skills`
- [x] Removed `ryze` connector from [`.roo/mcp.json`](../.roo/mcp.json) (superseded by direct `search-console` GSC/GA4); kept the 8 Ryze skills as reference only
- [x] Connected Google data via `search-console-mcp` — GSC (`pbservices.ge`) + GA4 (property `353738640`); verified with `diagnostics`
- [x] Ported all 8 SEO/GEO skills to the `search-console` MCP tool surface (methodology preserved; Google Ads + DataForSEO sections marked pending)
- [x] Connected Google Ads via `googleads/google-ads-mcp` (service account, Explorer access); verified `list_accessible_customers` → `customers/5963609731`
- [x] Ported the Google Ads skill sections to the `google-ads` MCP tool surface: `seo-vs-ads` (full paid-half GAQL workflow on `search_term_view`), `seo-keyword-research` (first-party actual CPC enrichment; Keyword Planner noted as not exposed by the GAQL-only server), `seo-audit` (pending pointer → live reference). DataForSEO sections remain pending.
- [x] Built + registered `google-ads-planner` MCP server ([`mcp-servers/google-ads-planner/server.py`](../mcp-servers/google-ads-planner/server.py)) exposing `generate_keyword_ideas` after user upgraded to Basic API access; `seo-keyword-research` updated to use real planner metrics. Live call verification pending (persistent per-method 429 since the upgrade — expected to clear; tool retries internally).
- [x] Prefixed all 8 SEO skills with `seo-` — 6 renamed via `git mv` (`ai-visibility`, `backlink-check`, `competitor-gap`, `content-brief`, `keyword-research`, `rank-tracking`) + frontmatter `name` updated to match directory; cross-references between skills updated; flat discovery layout preserved
- [x] Patched SEO skills for MCP tool accuracy — replaced 9 non-existent `search-console` tool names with real registered equivalents (verified against search-console-mcp v2.1.4), marked `analytics_traffic_sources` as not-exposed, fixed the broken `google-ads-planner` relative link in `seo-keyword-research`, and cleaned stale unprefixed names in memory-bank history
- [x] Implemented MCP-stack proposal — added official GA4 MCP (`analytics-mcp`, `analytics` entry) + official DataForSEO MCP (`dataforseo` entry) to `.roo/mcp.json`; created `seo/tool-map.md`; repointed GA4 (3 skills) and DataForSEO (4 skills) to the new servers
- [x] Built `seo/` home + capability-ID resolver — `seo/capabilities.json` (capability → server/tool/full `call` spec), `seo/resolve.py` (`--check`/`--write`/`--list`), moved `google-ads-planner` to `seo/mcp-servers/`, removed `docs/mcp-tool-map.md`; skills now carry deterministic call specs (zero-touch server swap = edit registry + `--write`)
- [x] Removed optional `dataforseo` server from `.roo/mcp.json`; marked it `"configured": false` in `seo/capabilities.json`; 7 skills now degrade gracefully without it (GA4/GSC/web-search fallbacks, skipped part stated explicitly)
- [x] Applied SEO review findings — fixed broken `google-ads-planner` link, tokenized `seo-keyword-research` + `seo-vs-ads`, aligned compatibility/pending wording, fixed GA4 verification to use the `analytics` server; registry v3 (per-server `tools` manifest + `args`), added `resolve.py --validate`; all checks pass
- [x] Schema-level validation of args — added `seo/mcp_client.py` (live `tools/list`), registry v4 (structured JSON `args` + `runtime`, enum-typed tools split per value), `resolve.py --validate-live` (tool + args vs live `inputSchema`) and `--map`; re-expanded all 8 skills; `--check` + `--validate-live` pass
- [x] Applied the full SEO-skills review — fixed `seo-ai-visibility` cited-pages query (AI filter) + funnel step, `seo-audit`/`seo-rank-tracking` dimension contradiction, planner reconciliation, `seo-content-brief` Output; removed copy-pasted planner/GSC-lag rows; added `## Fallbacks`/`## Pending Data Sources` to all skills + enforced in `test_skill_docs.py`; added `## Report Audience & Purpose`/`## Memory-Bank Isolation`/`## Configuration` sections; added `seo/references/domain-knowledge.md`; made `--data` mandatory; added semantic dimension/metric check to `resolve.py --check`; registry +`ga4.ai_cited_pages`/`ga4.conversions_by_source`; `--check` clean, 54/54 tests pass

## In Progress

_None_

## Upcoming

- WhatsApp bot integration (future)
- Python AI/NLP services (future)
