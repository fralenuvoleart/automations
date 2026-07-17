import asyncio
import xml.etree.ElementTree as ET
import httpx
import time

# CONFIGURATION
SITEMAP_URL = "https://pbservices.ge/sitemap-index.xml" 
CONCURRENT_REQUESTS = 1     
REQUEST_DELAY_SECONDS = 2.0  
LOOP_INTERVAL_HOURS = 24    
CUSTOM_USER_AGENT = "SevallaCacheWarmerSafe-SecureToken-99x"

async def fetch_and_parse_sitemap(client, target_url, urls_set):
    """Recursively parses sitemap indexes and extracts flat page URLs."""
    try:
        response = await client.get(target_url, timeout=15.0)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        
        locs = []
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 'loc' and elem.text:
                locs.append(elem.text.strip())
        
        if root_tag == 'sitemapindex':
            print(f"[Index] Scanning directory: {target_url}")
            tasks = [fetch_and_parse_sitemap(client, loc, urls_set) for loc in locs]
            await asyncio.gather(*tasks)
            
        elif root_tag == 'urlset':
            for loc in locs:
                urls_set.add(loc)
                
    except Exception as e:
        print(f"[ERROR] Failed processing sitemap target {target_url}: {e}")

async def warm_url(client, url):
    """Hits a single URL and reads the Kinsta/Cloudflare cache state."""
    try:
        start_time = time.time()
        response = await client.get(url, timeout=10.0)
        duration = time.time() - start_time
        
        kinsta_cache = response.headers.get("X-Kinsta-Cache", "UNKNOWN")
        edge_cache = response.headers.get("Ki-Cf-Cache-Status", "UNKNOWN")
        
        print(f"[{response.status_code}] Kinsta: {kinsta_cache} | Edge: {edge_cache} | Time: {duration:.2f}s -> {url}")
    except Exception as e:
        print(f"[ERROR] Failed to warm page {url}: {e}")

async def run_warmer():
    headers = {"User-Agent": CUSTOM_USER_AGENT}
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        print("--- Starting Sitemap Discovery Phase ---")
        urls_set = set()
        await fetch_and_parse_sitemap(client, SITEMAP_URL, urls_set)
        
        all_pages = list(urls_set)
        total_pages = len(all_pages)
        
        if not total_pages:
            print("[Warning] No page URLs discovered.")
            return
            
        print(f"--- Discovery Finished: Unique Pages Found: {total_pages} ---")
        print("--- Beginning Safe Sequential Warming Loop ---")
        
        # Explicitly processes 1 by 1 using the safe default semaphore
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        async def throttled_warm(url):
            async with semaphore:
                await warm_url(client, url)
                # Hard coded delay to prevent back-to-back hits
                await asyncio.sleep(REQUEST_DELAY_SECONDS) 
                
        for url in all_pages:
            await throttled_warm(url)
            
        print("Cache warming cycle completed cleanly.")

async def main():
    while True:
        await run_warmer()
        print(f"Sleeping for {LOOP_INTERVAL_HOURS} hours...")
        await asyncio.sleep(LOOP_INTERVAL_HOURS * 3600)

if __name__ == "__main__":
    asyncio.run(main())