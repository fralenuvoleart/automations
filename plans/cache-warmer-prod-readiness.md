# Cache-Warmer Production Readiness Plan

> **Status: ✅ IMPLEMENTED** — Rewritten in JS at [`services/nodejs/src/warmer.js`](../services/nodejs/src/warmer.js). All P0/P1/P2 fixes incorporated. P3 N/A (fast-xml-parser not vulnerable to billion laughs).

## Verdict: ~~Not production-ready~~ → Production-ready (JS rewrite complete).

## Architecture

The cache-warmer runs via `node-cron` inside the Telegram bot process (`services/nodejs/index.js`), scheduled daily at 03:00 UTC. No separate process needed.

On Sevalla: single `web` process in `automations-nodejs` app. No additional cost.

RAM: ~30-50 MB during warming within the bot's existing h1 tier (300 MB).

## Issues & Fixes (originally for cache-warmer.py, now in warmer.js)

### P0 — Crash Recovery ✅
**Fix:** `index.js:96` wraps `runWarmer()` in `.catch()`.

### P0 — Sitemap Discovery Concurrency ✅
**Fix:** `warmer.js:13-36` — `Semaphore` class with `DISCOVERY_CONCURRENCY = 3`.

### P1 — Graceful Shutdown ✅
**Fix:** `index.js:87-88` — SIGINT/SIGTERM handlers call `bot.stop()`.

### P2 — Retry on Failed URLs ✅
**Fix:** `warmer.js:99-121` — `RETRY_COUNT = 2` with exponential backoff.

### P2 — Timestamped Logging ✅
**Fix:** `warmer.js:38-40` — `log()` prefixes ISO timestamp.

### P2 — Redundant Semaphore ✅ (N/A in JS)
JS version uses sequential warming loop — no semaphore needed.

### P3 — XML Bomb Protection ✅ (N/A)
`fast-xml-parser` is not vulnerable to billion laughs attacks.

## Files Changed

| File | Change |
|------|--------|
| `services/nodejs/src/warmer.js` | Full JS rewrite with all fixes |
| `services/nodejs/index.js` | Cron schedule + error handling |
| `services/nodejs/package.json` | Added `fast-xml-parser`, `node-cron` |

## Cost

$0 additional. Runs within existing `automations-nodejs` Sevalla app ($5.83/mo).
