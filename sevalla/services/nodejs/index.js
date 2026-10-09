const cron = require("node-cron");
const fs = require("fs");
const { createBot } = require("./src/telegram-bot");
const { runWarmer } = require("./src/cache-warmer");
const { createServer } = require("./src/warmer-server");

const BOT_TOKEN = process.env.BOT_TOKEN; // set only on Sevalla, never in code
if (!BOT_TOKEN) console.warn("[bot] BOT_TOKEN is not set, Telegram bot is disabled");
const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID || "-1003837689636";
const MSG = require("./config/messages.json");

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

// ── Telegram ──
// DISABLE_TELEGRAM_BOT=true   keeps the previous bot (welcome / auto reply) off
// ENABLE_BUSINESS_LEADS=true  runs the Telegram Business lead capture
// Both are independent: with DISABLE_TELEGRAM_BOT=true and ENABLE_BUSINESS_LEADS=true
// only the lead capture runs, on a clean bot instance without the previous handlers.
const PREVIOUS_BOT_ON = process.env.DISABLE_TELEGRAM_BOT !== "true";
const BUSINESS_LEADS_ON = process.env.ENABLE_BUSINESS_LEADS === "true";

if (BOT_TOKEN && (PREVIOUS_BOT_ON || BUSINESS_LEADS_ON)) {
  const business = require("./src/business-bot");
  let bot;
  let allowedUpdates;

  if (PREVIOUS_BOT_ON) {
    bot = createBot(BOT_TOKEN, ADMIN_CHAT_ID, MSG);
    if (BUSINESS_LEADS_ON) allowedUpdates = business.ALLOWED_UPDATES;
  } else {
    const { Telegraf } = require("telegraf");
    bot = new Telegraf(BOT_TOKEN);
    bot.catch((err) => console.error("[business] handler error:", err.message));
    allowedUpdates = business.ALLOWED_UPDATES.filter((u) => u.includes("business"));
    console.log("Previous bot disabled via DISABLE_TELEGRAM_BOT, running business lead capture only");
  }

  if (BUSINESS_LEADS_ON) business.attachBusinessHandlers(bot);

  process.once("SIGINT", () => bot.stop("SIGINT"));
  process.once("SIGTERM", () => bot.stop("SIGTERM"));

  // Launch with retry on 409 conflict (race with old pod during deploy)
  async function launchBot(retries = 5, delayMs = 3000) {
    for (let i = 0; i <= retries; i++) {
      try {
        await bot.launch(allowedUpdates ? { allowedUpdates } : {}, () =>
          console.log("Bot started — polling for messages")
        );
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
} else {
  console.log("Bot disabled via DISABLE_TELEGRAM_BOT env var — warmer-only mode");
}

// ── Cache Warmer (daily at 01:00 and 13:00 UTC) ──
cron.schedule("0 1,13 * * *", () => {
  console.log("[cron] Starting cache warmer...");
  runWarmer()
    .then(() => console.log("[cron] Cache warmer finished."))
    .catch((err) => console.error("[cron] Cache warmer failed:", err.message));
}, { timezone: "UTC" });

console.log("Cache warmer scheduled daily at 01:00 and 13:00 UTC");

// ── HTTP server for public warmer trigger (Sevalla ingress on port 8080) ──
createServer().listen(8080, () => {
  console.log("HTTP server listening on :8080 — warmer trigger enabled");
});
