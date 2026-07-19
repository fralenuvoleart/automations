const { XMLParser } = require("fast-xml-parser");
const fs = require("fs");
const path = require("path");

// CONFIGURATION
const SITEMAP_URL = "https://pbservices.ge/sitemap-index.xml";
const REQUEST_DELAY_MS = 2000; // 2s between requests
const DISCOVERY_CONCURRENCY = 3;
const RETRY_COUNT = 2;
const USER_AGENT = "SevallaCacheWarmerSafe-SecureToken-99x";
const SUMMARY_FILE = path.join(__dirname, "..", "cache-warmer-last-run.json");

const parser = new XMLParser({ ignoreAttributes: false });

// ── Concurrency guard: prevent overlapping runs ──
let isRunning = false;

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

/**
 * Warms a single URL. Returns { ok, status, error, kinsta, cdn, edge }.
 */
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
      const cdn = res.headers.get("CF-Cache-Status") || "UNKNOWN";
      const edge = res.headers.get("Ki-Cf-Cache-Status") || "UNKNOWN";
      log(`[${res.status}] Kinsta: ${kinsta} | CDN: ${cdn} | Edge: ${edge} | Time: ${duration}s -> ${url}`);
      return { ok: true, status: res.status, kinsta, cdn, edge };
    } catch (e) {
      if (attempt < RETRY_COUNT) {
        const backoff = 2 ** attempt;
        log(`[RETRY ${attempt + 1}/${RETRY_COUNT}] ${url} — ${e.message}. Waiting ${backoff}s...`);
        await sleep(backoff * 1000);
      } else {
        log(`[ERROR] Failed to warm page ${url}: ${e.message}`);
        return { ok: false, status: null, error: e.message, url };
      }
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Stats helpers ──

function initStats() {
  return { hit: 0, miss: 0, bypass: 0, unknown: 0 };
}

function tallyStats(stats, value) {
  const v = (value || "").toLowerCase();
  if (v === "hit") stats.hit++;
  else if (v === "miss") stats.miss++;
  else if (v === "bypass") stats.bypass++;
  else stats.unknown++;
}

function formatStats(label, stats, total) {
  const pct = (n) => total > 0 ? ` (${((n / total) * 100).toFixed(1)}%)` : "";
  return `${label}: ${stats.hit} HIT${pct(stats.hit)}, ${stats.miss} MISS${pct(stats.miss)}, ${stats.bypass} BYPASS${pct(stats.bypass)}` +
    (stats.unknown ? `, ${stats.unknown} UNKNOWN` : "");
}

async function runWarmer() {
  if (isRunning) {
    log("[SKIP] Warmer is already running — concurrent run prevented.");
    return;
  }
  isRunning = true;

  const startTime = new Date().toISOString();
  // Stats accumulators
  const kinstaStats = initStats();
  const cdnStats = initStats();
  const edgeStats = initStats();
  const failedUrls = [];

  try {
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
      const result = await warmUrl(url);
      if (result.ok) {
        tallyStats(kinstaStats, result.kinsta);
        tallyStats(cdnStats, result.cdn);
        tallyStats(edgeStats, result.edge);
      } else {
        failedUrls.push({ url, error: result.error });
      }
      await sleep(REQUEST_DELAY_MS);
    }

    // ── Summary ──
    const endTime = new Date().toISOString();
    const total = allPages.length;
    const ok = total - failedUrls.length;
    const fail = failedUrls.length;

    const summaryLines = [
      "",
      "═══════════════════════════════════════════",
      "           CACHE WARMER — SUMMARY           ",
      "═══════════════════════════════════════════",
      `Started:     ${startTime}`,
      `Finished:    ${endTime}`,
      `Total URLs:  ${total}`,
      `Successful:  ${ok}`,
      `Failed:      ${fail}`,
      "",
      "── Cache Status ──",
      formatStats("Kinsta", kinstaStats, ok),
      formatStats("CDN   ", cdnStats, ok),
      formatStats("Edge  ", edgeStats, ok),
    ];

    if (failedUrls.length > 0) {
      summaryLines.push("", "── Failed URLs ──");
      failedUrls.forEach((f) =>
        summaryLines.push(`  ✗ ${f.url}\n    Reason: ${f.error}`)
      );
    }

    summaryLines.push(
      "",
      "═══════════════════════════════════════════",
      ""
    );

    const summaryText = summaryLines.join("\n");
    console.log(summaryText);

    // Persist summary to disk for `npm run logs`
    const summaryJson = {
      started: startTime,
      finished: endTime,
      total,
      successful: ok,
      failed: fail,
      kinsta: kinstaStats,
      cdn: cdnStats,
      edge: edgeStats,
      failedUrls,
    };
    fs.writeFileSync(SUMMARY_FILE, JSON.stringify(summaryJson, null, 2));
    log(`Summary saved to ${SUMMARY_FILE}`);

    log("Cache warming cycle completed cleanly.");
  } finally {
    isRunning = false;
  }
}

module.exports = { runWarmer };
