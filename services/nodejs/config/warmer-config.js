// Cache warmer configuration — single source of truth.
// All values can be overridden via environment variables.

const path = require("path");

module.exports = {
  SITEMAP_URL:
    process.env.WARMER_SITEMAP_URL || "https://pbservices.ge/sitemap-index.xml",

  REQUEST_DELAY_MS:
    parseInt(process.env.WARMER_REQUEST_DELAY_MS, 10) || 2000,

  DISCOVERY_CONCURRENCY:
    parseInt(process.env.WARMER_DISCOVERY_CONCURRENCY, 10) || 3,

  RETRY_COUNT:
    parseInt(process.env.WARMER_RETRY_COUNT, 10) || 2,

  USER_AGENT:
    process.env.WARMER_USER_AGENT ||
    "SevallaCacheWarmer/1.0 (+https://pbservices.ge; token:cache-warmer)",

  PROGRESS_INTERVAL:
    parseInt(process.env.WARMER_PROGRESS_INTERVAL, 10) || 10,

  SUMMARY_FILE:
    process.env.WARMER_SUMMARY_FILE ||
    path.join(__dirname, "..", "cache-warmer-last-run.json"),

  PROGRESS_FILE:
    process.env.WARMER_PROGRESS_FILE ||
    path.join(__dirname, "..", "cache-warmer-progress.json"),
};
