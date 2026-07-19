# Active Context

## Current Focus

Project is `automations` — two service runtimes:
- `services/nodejs/` — Telegram bot + cache warmer (production, deployed on Sevalla)
- `services/python/` — placeholder for future AI/NLP services

## Recent Changes

- **2026-07-19**: Patched [`telegram-bot.js`](../services/nodejs/src/telegram-bot.js) — 6 fixes applied:
  1. `t()` helper no longer coerces missing `name` to `"undefined"` string
  2. Deep-clone via `JSON.parse(JSON.stringify())` prevents env-var overrides from mutating the `require()`-cached messages
  3. `startPayloads` Map entries now deleted after first use (memory leak fixed)
  4. `forwardMessage` and auto-reply now retry on failure (2 retries, exponential backoff)
  5. Integrately webhook `fetch` now retries on failure
  6. Per-user rate limiting added: max 3 messages per 10-second window
- Extracted bot logic from `index.js` → [`src/telegram-bot.js`](../services/nodejs/src/telegram-bot.js) for self-documenting structure
- Renamed `src/warmer.js` → [`src/cache-warmer.js`](../services/nodejs/src/cache-warmer.js)
- [`index.js`](../services/nodejs/index.js) is now a thin wiring layer: imports bot + warmer, starts cron
- Removed old `pbs-telegram/` directory — fully migrated

## Prior Tasks (Completed)

- Cache warmer JS rewrite (from Python)
- Repo restructuring to `automations/` layout
- Production readiness fixes (concurrency limiting, retries, graceful shutdown, timestamped logging)
- Descriptive file naming for discoverability
