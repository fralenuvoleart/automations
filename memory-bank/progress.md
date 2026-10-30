# Project Progress

## Completed

### Platform (`services/nodejs/`)
- Repo restructured to the `automations/` layout.
- Telegram bot operational — auto-reply, forwarding, relay mode for hidden-profile users, Integrately webhook, per-user rate limiting, retries.
- Cache warmer rewritten in JS — granular per-status stats, redirect tracking, concurrency guard, retries, persisted last-run summary.
- `docs/WARMER.md` documents warmer logic, cache-header semantics, and the warmer-vs-Kinsta-Analytics discrepancy.

### SEO/GEO skills toolkit (`.agents/skills/` + `seo/`)
- 13 `seo-*` skills (12 reports + weekly `seo-brief`) + `kinsta-logs` + `report-export` + `web-to-pdf`.
- Capability registry v8 + resolver (rendered cap/site/include blocks, generated Data Sources tables, live/cached schema validation, semantic dimension/metric checks).
- Scripted data layer: `seo/pipeline.py` + `seo/data-plans/` — cache-first pulls, evidence recording, analysis into `computed/`; row limits completed (split/page), temporary failures retried, write guard, fail-closed `requires_servers`.
- Report gate: findings validated against `findings-schema.json` (jsonschema) + cross-field rules; every URL and figure checked against evidence and computed outputs (`number_check.py`); figures from data still cut at the row limit refused.
- Site rules (`seo/config/rules/<domain>.json` + `seo/rules.py`) — classification shared with the SEO sheet; site profiles + status-tagged action history. Profile data filled (`ads_customer_id`, `priority_pages`, `competitors`, `gsc_property`, `ga4_property`); brand rule confirmed by the owner: `пб сервис` and `gecrypto` are not brand terms.
- Analysis modules: GSC (movers, striking distance, low CTR with own-data CTR curve, cannibalization, decay classes, brand/language split, value model, totals, inspection summary), GA4 by the rules (channels, page types, languages, AI share, Search Console vs GA4), crawler (robots per path, sitemaps, link graph, hreflang, canonicals, page facts; robots.txt respected), DataForSEO and Ads helpers, coverage.
- Fixed run folders + shared cache in `~/Documents/seo-reports`; weekly `seo-brief` merges and ranks actions across reports.
- Shared `report-export` — Markdown→PDF (`npx md-to-pdf`/Chromium, WeasyPrint fallback) + SMTP email; one config with per-skill subjects.
- CI gate `seo/check.sh`: resolve check, cached schemas, data plans, CTR-benchmark age (warning), profiles, compile, all test suites (incl. repo-wide Markdown links).
- Reviews actioned: 2026-10-29 audit, 2026-10-30 audit (C/H/M/L), architecture audit v8 (A1–A4, A8, A9), external findings A-01…A-08 — status table in `activeContext.md`.

## In Progress

- None.

## Upcoming

- **Security**: rotate the Sevalla, Tavily and Kinsta API keys exposed in tracked `.roo/mcp.json`; untrack the file. Review its auto-approve lists (`sevalla.deployments.start` is auto-approved).
- **DataForSEO** — connect (`.roo/mcp.json` + `servers.dataforseo.configured` in `seo/capabilities.json`) to enable `seo-backlink-check` and the SERP/competitor sections; then set `serp_locations` in the profile.
- **Search Console bulk export to BigQuery** — owner decision; only route to history beyond 16 months (no backfill: starts when enabled).
- **Move earlier runs** from the repo's `.output/seo/` into `~/Documents/seo-reports` to keep their cache and history.
- **SEO sheet Apps Script** — switch it to read `seo/config/rules/pbservices.ge.json` (needs the script code).
- **Tavily schema cache** — run `python3 seo/mcp_client.py tavily` locally so `--validate-cached` covers `web.*`.
- **Google Business Profile** — connect to unlock map-pack analysis for local markets (`seo-audit`).
- WhatsApp bot integration (future); Python AI/NLP services (future).
