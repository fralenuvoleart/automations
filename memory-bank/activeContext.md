# Active Context

## Current Focus

Project is `automations` — two service runtimes:
- `services/nodejs/` — Telegram bot + cache warmer (production, deployed on Sevalla)
- `services/python/` — placeholder for future AI/NLP services

## Recent Changes

- Extracted bot logic from `index.js` → [`src/telegram-bot.js`](../services/nodejs/src/telegram-bot.js) for self-documenting structure
- Renamed `src/warmer.js` → [`src/cache-warmer.js`](../services/nodejs/src/cache-warmer.js)
- [`index.js`](../services/nodejs/index.js) is now a thin wiring layer: imports bot + warmer, starts cron
- Removed old `pbs-telegram/` directory — fully migrated

## Prior Tasks (Completed)

- Cache warmer JS rewrite (from Python)
- Repo restructuring to `automations/` layout
- Production readiness fixes (concurrency limiting, retries, graceful shutdown, timestamped logging)
- Descriptive file naming for discoverability
