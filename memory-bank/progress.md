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
- Site rules (`seo/config/rules/<domain>.json` + `seo/rules.py`) — classification shared with the SEO sheet (2026-10-30).
- Scripted data pulls (`seo/pipeline.py` + `seo/plans/`) and the number check in `validate_report.py` — the agent only interprets (2026-10-30).
- Run folder + cache + structured actions + weekly `seo-brief` (2026-10-30).
- SEO-sheet practices ported (2026-10-30): target pages + wrong-page check, top countries per keyword, Monday–Sunday weekly mode with 8-week trends, GA4 by the site rules + Search Console vs GA4 check, report definitions.
- CI gate `seo/check.sh` (`--check` + `--validate-live` + all tests) — 14 test suites green.
- **2026-10-30 architecture audit** — [`plans/seo-architecture-audit-2026-10-30.md`](../plans/seo-architecture-audit-2026-10-30.md): 8.1/10 systems-design grade; taxonomy matrix (44 caps / 6 servers / T0–T6 tiers), per-domain scores, anti-pattern teardown, P0–P3 refactor blueprint.
- **2026-10-30 audit fixes applied (all 51 issues + optional items)** — evidence recording + gate, deterministic GSC/crawl/DFS/Ads analysis modules, registry v7 (rowLimit/engine pinned, `keyEvents`, profile-driven AI filter), marker-based re-rendering with shared includes, planner API limits + historical metrics, offline-portable CI (`--validate-cached`). 18 SEO test suites + report-export green.
- **Fresh architecture audit on registry v8** — [`plans/seo-architecture-audit-v8.md`](../plans/seo-architecture-audit-v8.md): 8.1/10 weighted on a new rubric; 44 capabilities × 6 servers × function-class matrix, 13-skill pull-overlap matrix, 9 anti-patterns (A1–A9) with file references, P0–P3 blueprint, residual risk register. Supersedes the 2026-10-30 audit.

## In Progress

_None_

## Upcoming

- **Security**: rotate the Sevalla, Tavily and Kinsta API keys exposed in tracked `.roo/mcp.json`; untrack the file.
- **SEO profile data** — `ads_customer_id`, `priority_pages` and `competitors` filled (2026-10-30); `serp_locations` deliberately unset until DataForSEO is connected; brand rule confirmed by the owner (2026-10-30): `пб сервис` and `gecrypto` are not brand terms.
- **SEO sheet Apps Script** — switch it to read `seo/config/rules/pbservices.ge.json` (needs the script code).
- **Tavily schema cache** — run `python3 seo/mcp_client.py tavily` locally so `--validate-cached` covers `web.*`.
- WhatsApp bot integration (future).
- Python AI/NLP services (future).
- **DataForSEO** (optional) — connect to unlock backlink / competitor / SERP enrichment.
- **Google Business Profile** — connect to unlock map-pack analysis for local markets (`seo-audit`).
