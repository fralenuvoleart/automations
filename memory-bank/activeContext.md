# Active Context

## Current Focus

`automations` — two service runtimes plus a shared Agent-Skills toolkit:

- `services/nodejs/` — Telegram bot + cache warmer (production, deployed on Sevalla).
- `services/python/` — placeholder for future AI/NLP services.
- `.agents/skills/` — Agent Skills (SEO/GEO toolkit, `kinsta-logs`, `report-export`, `web-to-pdf`).

## SEO/GEO skills toolkit (current state)

**21 skills** in `.agents/skills/`:
- **18 `seo-*` skills** — `seo-audit`, `seo-ai-visibility`, `seo-backlink-check`, `seo-brand-split`, `seo-competitor-gap`, `seo-content-brief`, `seo-content-refresh`, `seo-cross-engine`, `seo-indexation`, `seo-internal-links`, `seo-keyword-research`, `seo-local`, `seo-monetisation`, `seo-opportunity`, `seo-rank-tracking`, `seo-serp-features`, `seo-technical`, `seo-vs-ads`.
- **`kinsta-logs`** — Kinsta server-log analysis.
- **`report-export`** — shared Markdown→PDF + email delivery; every report skill delegates to it.
- **`web-to-pdf`** — webpage→PDF.

**Non-skill SEO tooling** lives in `seo/`:
- `capabilities.json` — single source of truth (capability → server + tool + `args` + `runtime`).
- `resolve.py` — expands `{{cap:<id>}}` / `{{site:<key>}}` tokens; `--check` / `--validate-live` / `--write` / `--map`.
- `site_profile.py` — per-site profile + action history (`config/sites/<domain>.json` / `.history.md`).
- `coverage.py` — deterministic coverage block (flattened + per-language).
- `window.py` / `orchestrate.py` — deterministic windows + run seeding.
- `report/` — `build_report.py` (findings JSON → Markdown) + `validate_report.py` (mandatory).
- `references/` — shared contracts: `report-structure.md`, `conciseness-directives.md`, `data-source-map.md`, `capability-usage.md`, `domain-knowledge.md`, `findings-schema.json`.
- `check.sh` — CI gate (`--check` + `--validate-live` + all tests).

**MCP servers** (`.roo/mcp.json`): `search-console` (GSC/GA4/Bing/AdSense, OAuth), `analytics` (official GA4, service account), `google-ads` (service account), `google-ads-planner` (local, `seo/mcp-servers/`), `tavily`. **`dataforseo` is optional and not configured** — skills degrade gracefully and the report states the missing source.

**Credentials:** service account via `GOOGLE_APPLICATION_CREDENTIALS`; `search-console` OAuth in `~/.search-console-mcp-config.enc`; report email SMTP in `~/.config/report-export/email.json`.

## Sevalla services (current state)

- `services/nodejs/` — Telegram bot (`src/telegram-bot.js`) + cache warmer (`src/cache-warmer.js`), wired by `index.js`; shell scripts in `scripts/`; docs in `docs/WARMER.md`.
- Deployed on Sevalla — see `systemPatterns.md` for the Sevalla API rules (exec endpoint, backgrounding, bot 409 handling).

## Conventions

- Plan files → `plans/`.
- Read this memory bank before every task; update `activeContext.md` + `progress.md` after significant changes.
- Skill contract + CI: see `systemPatterns.md` and [`seo/README.md`](../seo/README.md).

## Recent Changes

- **2026-10-29**: Built out the SEO/GEO toolkit — 18 `seo-*` skills, the Site Profile layer (per-site criteria + action history), deterministic coverage, the report `unavailable`/`coverage` blocks, and the shared `report-export` skill (PDF + email, one config with per-skill subjects). CI gate `seo/check.sh` is green.
