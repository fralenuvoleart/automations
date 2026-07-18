import asyncio
import signal
import httpx
import time
from datetime import datetime, timezone
from defusedxml import ElementTree as ET

# CONFIGURATION
SITEMAP_URL = "https://pbservices.ge/sitemap-index.xml"
CONCURRENT_REQUESTS = 1
REQUEST_DELAY_SECONDS = 2.0
RUN_AT_HOUR_UTC = 3  # Fixed UTC hour for daily run (0-23)
CUSTOM_USER_AGENT = "SevallaCacheWarmerSafe-SecureToken-99x"
DISCOVERY_CONCURRENCY = 3  # Max simultaneous sitemap requests
RETRY_COUNT = 2  # Retries per URL on transient failure

# Global flags
_shutdown = False
_force_run = False

def log(msg):
    """Timestamped print."""
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}")


def handle_shutdown(sig, frame):
    """Set shutdown flag on SIGTERM/SIGINT."""
    global _shutdown
    log(f"Received signal {sig}, shutting down gracefully...")
    _shutdown = True


def handle_force_run(sig, frame):
    """Set force-run flag on SIGUSR1."""
    global _force_run
    log("Received SIGUSR1, forcing immediate cache warm cycle.")
    _force_run = True


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGUSR1, handle_force_run)

discovery_semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)


async def fetch_and_parse_sitemap(client, target_url, urls_set):
    """Recursively parses sitemap indexes and extracts flat page URLs."""
    async with discovery_semaphore:
        try:
            response = await client.get(target_url, timeout=15.0)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

            locs = []
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "loc" and elem.text:
                    locs.append(elem.text.strip())

            if root_tag == "sitemapindex":
                log(f"[Index] Scanning directory: {target_url}")
                tasks = [fetch_and_parse_sitemap(client, loc, urls_set) for loc in locs]
                await asyncio.gather(*tasks)

            elif root_tag == "urlset":
                for loc in locs:
                    urls_set.add(loc)

        except Exception as e:
            log(f"[ERROR] Failed processing sitemap target {target_url}: {e}")


async def warm_url(client, url):
    """Hits a single URL with retries. Reads cache state from headers."""
    for attempt in range(1 + RETRY_COUNT):
        if _shutdown:
            return
        try:
            start_time = time.time()
            response = await client.get(url, timeout=10.0)
            duration = time.time() - start_time

            kinsta_cache = response.headers.get("X-Kinsta-Cache", "UNKNOWN")
            edge_cache = response.headers.get("Ki-Cf-Cache-Status", "UNKNOWN")

            log(f"[{response.status_code}] Kinsta: {kinsta_cache} | Edge: {edge_cache} | Time: {duration:.2f}s -> {url}")
            return  # success, exit retry loop
        except Exception as e:
            if attempt < RETRY_COUNT:
                backoff = 2 ** attempt
                log(f"[RETRY {attempt+1}/{RETRY_COUNT}] {url} — {e}. Waiting {backoff}s...")
                await asyncio.sleep(backoff)
            else:
                log(f"[ERROR] Failed to warm page {url}: {e}")


async def run_warmer():
    headers = {"User-Agent": CUSTOM_USER_AGENT}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        log("--- Starting Sitemap Discovery Phase ---")
        urls_set = set()
        await fetch_and_parse_sitemap(client, SITEMAP_URL, urls_set)

        all_pages = list(urls_set)
        total_pages = len(all_pages)

        if not total_pages:
            log("[Warning] No page URLs discovered.")
            return

        log(f"--- Discovery Finished: Unique Pages Found: {total_pages} ---")
        log("--- Beginning Safe Sequential Warming Loop ---")

        for url in all_pages:
            if _shutdown:
                log("Shutdown requested, stopping warming early.")
                break
            await warm_url(client, url)
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

        log("Cache warming cycle completed cleanly.")


def _seconds_until_next_run(hour_utc):
    """Seconds until the next occurrence of hour_utc (0-23) in UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target.replace(day=now.day + 1)  # handles month rollover
    return (target - now).total_seconds()


async def main():
    # Run immediately on startup
    try:
        await run_warmer()
    except Exception as e:
        log(f"[FATAL] Warmer cycle crashed: {e}")

    while True:
        wait_seconds = _seconds_until_next_run(RUN_AT_HOUR_UTC)
        log(f"Next run scheduled at {RUN_AT_HOUR_UTC:02d}:00 UTC "
            f"({wait_seconds / 3600:.1f} hours from now). "
            f"Send SIGUSR1 (kill -USR1 {__import__('os').getpid()}) to force run.")

        # Sleep in 30-second chunks so SIGUSR1 is responsive
        waited = 0.0
        while waited < wait_seconds and not _shutdown and not _force_run:
            chunk = min(30, wait_seconds - waited)
            await asyncio.sleep(chunk)
            waited += chunk

        if _shutdown:
            break

        if _force_run:
            global _force_run
            _force_run = False
            log("Manual trigger — starting cache warm cycle now.")

        try:
            await run_warmer()
        except Exception as e:
            log(f"[FATAL] Warmer cycle crashed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
