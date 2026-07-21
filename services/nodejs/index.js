const cron = require("node-cron");
const fs = require("fs");
const { createBot } = require("./src/telegram-bot");
const { runWarmer } = require("./src/cache-warmer");

const BOT_TOKEN = process.env.BOT_TOKEN;
const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID || "546485204";
const MSG = require("./config/messages.json");

if (!BOT_TOKEN) {
  console.error("Missing BOT_TOKEN environment variable");
  process.exit(1);
}

// Check for interrupted warmer run from previous crash
const PROGRESS_FILE = "cache-warmer-progress.json";
if (fs.existsSync(PROGRESS_FILE)) {
  try {
    const p = JSON.parse(fs.readFileSync(PROGRESS_FILE, "utf8"));
    if (p.running) {
      console.warn(
        `[warmer] Interrupted run detected: was at ${p.current}/${p.total} URLs when process crashed`
      );
    }
  } catch (_) { /* ignore malformed JSON */ }
}

// Global safety net: log unhandled rejections instead of crashing
process.on("unhandledRejection", (reason) => {
  console.error("[fatal] Unhandled rejection:", reason);
});

// ── Telegram Bot ──
const bot = createBot(BOT_TOKEN, ADMIN_CHAT_ID, MSG);

process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));

// Launch with retry on 409 conflict (race with old pod during deploy)
async function launchBot(retries = 5, delayMs = 3000) {
  for (let i = 0; i <= retries; i++) {
    try {
      await bot.launch();
      console.log("Bot started — polling for messages");
      return;
    } catch (err) {
      if (err?.response?.error_code === 409 && i < retries) {
        console.warn(
          `[bot] 409 conflict (old instance still running) — retrying in ${delayMs / 1000}s (${i + 1}/${retries})...`
        );
        await new Promise((r) => setTimeout(r, delayMs));
      } else {
        throw err; // Not a 409 or out of retries — fatal
      }
    }
  }
}

launchBot().catch((err) => {
  console.error("Bot failed to start:", err.message);
  process.exit(1);
});

// ── Cache Warmer (daily at 01:00 UTC) ──
cron.schedule("0 1 * * *", () => {
  console.log("[cron] Starting cache warmer...");
  runWarmer()
    .then(() => console.log("[cron] Cache warmer finished."))
    .catch((err) => console.error("[cron] Cache warmer failed:", err.message));
});

console.log("Cache warmer scheduled daily at 01:00 UTC");
