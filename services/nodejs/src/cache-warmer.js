const { XMLParser } = require("fast-xml-parser");

// CONFIGURATION
const SITEMAP_URL = "https://pbservices.ge/sitemap-index.xml";
const REQUEST_DELAY_MS = 2000; // 2s between requests
const DISCOVERY_CONCURRENCY = 3;
const RETRY_COUNT = 2;
const USER_AGENT = "SevallaCacheWarmerSafe-SecureToken-99x";

const parser = new XMLParser({ ignoreAttributes: false });

// Concurrency limiter for sitemap discovery
class Semaphore {
  constructor(max) {
    this.max = max;
    this.running = 0;
    this.queue = [];
  }
  async acquire() {
    if (this.running < this.max) {
      this.running++;
      return;
    }
    return new Promise((resolve) => this.queue.push(resolve));
  }
  release() {
    this.running--;
    const next = this.queue.shift();
    if (next) {
      this.running++;
      next();
    }
  }
}

const discoverySem = new Semaphore(DISCOVERY_CONCURRENCY);

function log(msg) {
  console.log(`[${new Date().toISOString()}] ${msg}`);
}

function extractLocs(root) {
  const locs = [];
  function walk(node) {
    if (!node || typeof node !== "object") return;
    const keys = Object.keys(node);
    for (const key of keys) {
      if (key.endsWith("loc") && typeof node[key] === "string") {
        locs.push(node[key].trim());
      } else if (typeof node[key] === "object") {
        walk(node[key]);
      } else if (Array.isArray(node[key])) {
        node[key].forEach((item) => walk(item));
      }
    }
  }
  walk(root);
  return locs;
}

async function fetchSitemap(url, urlsSet) {
  await discoverySem.acquire();
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const parsed = parser.parse(text);

    // Determine root tag: sitemapindex or urlset
    const rootKey = Object.keys(parsed).find(
      (k) => k.includes("sitemapindex") || k.includes("urlset")
    );

    if (rootKey && rootKey.includes("sitemapindex")) {
      log(`[Index] Scanning directory: ${url}`);
      const locs = extractLocs(parsed[rootKey]);
      const results = await Promise.allSettled(
        locs.map((loc) => fetchSitemap(loc, urlsSet))
      );
      results.forEach((r, i) => {
        if (r.status === "rejected")
          log(`[ERROR] Sub-sitemap failed: ${locs[i]} — ${r.reason}`);
      });
    } else if (rootKey && rootKey.includes("urlset")) {
      const locs = extractLocs(parsed[rootKey]);
      locs.forEach((loc) => urlsSet.add(loc));
    }
  } catch (e) {
    log(`[ERROR] Failed processing sitemap ${url}: ${e.message}`);
  } finally {
    discoverySem.release();
  }
}

async function warmUrl(url) {
  for (let attempt = 0; attempt <= RETRY_COUNT; attempt++) {
    try {
      const start = Date.now();
      const res = await fetch(url, {
        headers: { "User-Agent": USER_AGENT },
        signal: AbortSignal.timeout(10000),
      });
      const duration = ((Date.now() - start) / 1000).toFixed(2);
      const kinsta = res.headers.get("X-Kinsta-Cache") || "UNKNOWN";
      const edge = res.headers.get("Ki-Cf-Cache-Status") || "UNKNOWN";
      log(`[${res.status}] Kinsta: ${kinsta} | Edge: ${edge} | Time: ${duration}s -> ${url}`);
      return;
    } catch (e) {
      if (attempt < RETRY_COUNT) {
        const backoff = 2 ** attempt;
        log(`[RETRY ${attempt + 1}/${RETRY_COUNT}] ${url} — ${e.message}. Waiting ${backoff}s...`);
        await sleep(backoff * 1000);
      } else {
        log(`[ERROR] Failed to warm page ${url}: ${e.message}`);
      }
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runWarmer() {
  log("--- Starting Sitemap Discovery Phase ---");
  const urlsSet = new Set();
  await fetchSitemap(SITEMAP_URL, urlsSet);

  const allPages = [...urlsSet];
  if (!allPages.length) {
    log("[Warning] No page URLs discovered.");
    return;
  }

  log(`--- Discovery Finished: Unique Pages Found: ${allPages.length} ---`);
  log("--- Beginning Safe Sequential Warming Loop ---");

  for (const url of allPages) {
    await warmUrl(url);
    await sleep(REQUEST_DELAY_MS);
  }

  log("Cache warming cycle completed cleanly.");
}

module.exports = { runWarmer };
