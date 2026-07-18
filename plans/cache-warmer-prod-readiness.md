# Cache-Warmer Production Readiness Plan

## Verdict: Not production-ready. 8 issues. All fixable self-contained.

## Architecture

The cache-warmer runs as a **self-contained long-lived process** with its own `while True` / 24h sleep loop. No changes needed to the Telegram bot. No additional Sevalla cost.

On Sevalla: deploy as a **second process** in the same app (`cron` type is ideal, but `web` type works too if you keep the loop). Or deploy as a separate app.

RAM: ~30 MB idle, ~30-50 MB during warming. Fits easily in h1 tier (300 MB).

## Issues & Fixes (cache-warmer.py only)

### P0 — Crash Recovery
**Problem:** `main()` line 88 calls `run_warmer()` without try/except. Any exception kills the process.
**Fix:** Wrap in try/except with error logging and continue the loop.

### P0 — Sitemap Discovery Concurrency  
**Problem:** `fetch_and_parse_sitemap()` line 30-31 uses `asyncio.gather(*tasks)` with no concurrency limit. 50 sub-sitemaps = 50 simultaneous HTTP requests.
**Fix:** Add `asyncio.Semaphore(3)` around the HTTP call inside `fetch_and_parse_sitemap`.

### P1 — Graceful Shutdown
**Problem:** No SIGTERM/SIGINT handling. Sevalla sends SIGTERM on deploy; in-flight requests abandoned.
**Fix:** Add signal handler that cancels pending tasks and closes httpx client.

### P2 — No Retry on Failed URLs
**Problem:** Transient 503/timeout = page misses cache warm.
**Fix:** 2 retries with exponential backoff in `warm_url()`.

### P2 — Timestamped Logging
**Problem:** Print statements have no timestamps.
**Fix:** Prefix all output with ISO timestamp.

### P2 — Redundant Semaphore
**Problem:** `Semaphore(1)` + `asyncio.sleep(2)` inside critical section is redundant when CONCURRENT_REQUESTS=1.
**Fix:** Remove semaphore. Keep the sleep.

### P3 — XML Bomb Protection
**Problem:** `ET.fromstring()` vulnerable to billion laughs (low risk: trusted source).
**Fix:** Replace `xml.etree.ElementTree` with `defusedxml.ElementTree`.

## Files Changed

| File | Change |
|------|--------|
| `cache-warmer/cache-warmer.py` | All fixes above |
| `cache-warmer/requirements.txt` | Add `defusedxml` |

## Cost

$0 additional. Self-contained script. Deploy however you want.
