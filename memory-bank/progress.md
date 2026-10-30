# Project Progress

## Completed

### Platform (`services/nodejs/`)
- Repo restructured to the `automations/` layout.
- Telegram bot operational — auto-reply, forwarding, relay mode for hidden-profile users, Integrately webhook, per-user rate limiting, retries.
- Cache warmer rewritten in JS — granular per-status stats, redirect tracking, concurrency guard, retries, persisted last-run summary.
- `docs/WARMER.md` documents warmer logic, cache-header semantics, and the warmer-vs-Kinsta-Analytics discrepancy.

### SEO/GEO skills toolkit (`.agents/skills/` + `seo/`)
- 12 consolidated `seo-*` power skills + `kinsta-logs` + `report-export` + `web-to-pdf`.
- Capability registry + resolver (`{{cap:}}` / `{{site:}}` tokens), live-schema validation, semantic dimension/metric checks.
- Site Profile layer — per-site criteria (`config/sites/<domain>.json`) + append-only action history (`.history.md`); per-language priority keywords.
- Deterministic coverage (`coverage.py`) rendered as a per-language report block.
- Report pipeline — findings JSON → `build_report.py` → mandatory `validate_report.py`; `unavailable` + `coverage` blocks for graceful degradation; hardened against missing `lag`, missing `compareEndDate`, missing `context.json`, and table pipe/newline injection.
- Shared `report-export` — Markdown→PDF (`npx md-to-pdf`/Chromium, WeasyPrint fallback) + SMTP email; one config with per-skill subjects.
- Senior SEO & GEO enhancements — AI crawler accessibility audits, Schema `sameAs` entity disambiguation, `hreflang` reciprocity checks, Cannibalization Decision Matrix, Quotability Scorecard, and anchor distribution profiles.
- Physical Portfolio Consolidation (18 to 12 Power Skills) & Capability registry v6 — decoupled GSC dimensions (`gsc.query`, `gsc.page_query`, `gsc.query_full`, `gsc.geo_query`, `gsc.time_series`, `gsc.device_performance`); created `seo-keyword-strategy` and `seo-paid-organic`; absorbed `seo-serp-features`, `seo-competitor-gap`, `seo-local`, `seo-cross-engine`, and `seo-opportunity`; pruned `seo-monetisation`; removed legacy `adsense.*` capabilities; isolated `google-ads` server strictly to `seo-paid-organic`.
- CI gate `seo/check.sh` (`--check` + `--validate-live` + all tests) — 14 test suites green.
- **2026-10-30 audit fixes applied (all 51 issues + optional items)** — evidence recording + gate, deterministic GSC/crawl/DFS/Ads analysis modules, registry v7 (rowLimit/engine pinned, `keyEvents`, profile-driven AI filter), marker-based re-rendering with shared includes, planner API limits + historical metrics, offline-portable CI (`--validate-cached`). 18 SEO test suites + report-export green.

## In Progress

_None_

## Upcoming

- **Security**: rotate the Sevalla, Tavily and Kinsta API keys exposed in tracked `.roo/mcp.json`; untrack the file.
- **SEO profile data** — `ads_customer_id`, `priority_pages` and `competitors` filled (2026-10-30); `serp_locations` deliberately unset until DataForSEO is connected; confirm the added brand variants (`pb service`, `пб сервис`).
- **Tavily schema cache** — run `python3 seo/mcp_client.py tavily` locally so `--validate-cached` covers `web.*`.
- WhatsApp bot integration (future).
- Python AI/NLP services (future).
- **DataForSEO** (optional) — connect to unlock backlink / competitor / SERP enrichment.
- **Google Business Profile** — connect to unlock map-pack analysis for local markets (`seo-audit`).
