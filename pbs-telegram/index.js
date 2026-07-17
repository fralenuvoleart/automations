const { Telegraf } = require("telegraf");

const BOT_TOKEN = process.env.BOT_TOKEN;
const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID || "546485204";
const INTEGRATELY_WEBHOOK = "https://webhooks.integrately.com/a/webhooks/11e1f7e4cb3e4517abcea0d9cd833383";

if (!BOT_TOKEN) {
  console.error("Missing BOT_TOKEN environment variable");
  process.exit(1);
}

// Load messages from file; env vars override for emergencies
const MSG = require("./messages.json");
if (process.env.MSG_WELCOME) MSG.welcome.default = process.env.MSG_WELCOME;
if (process.env.MSG_WELCOME_RU) MSG.welcome.ru = process.env.MSG_WELCOME_RU;
if (process.env.MSG_AUTOREPLY) MSG.autoreply.default = process.env.MSG_AUTOREPLY;
if (process.env.MSG_AUTOREPLY_RU) MSG.autoreply.ru = process.env.MSG_AUTOREPLY_RU;

// Pick message by user language, fallback to default
const t = (key, lang, name) => {
  const msg = MSG[key][lang] || MSG[key].default;
  return msg.replace("{name}", name);
};

const bot = new Telegraf(BOT_TOKEN);

// Track users who already received the auto-reply
const repliedUsers = new Set();
// Store /start deep-link payload per user
const startPayloads = new Map();

bot.on("text", async (ctx) => {
  const text = ctx.message.text;
  const lang = ctx.from?.language_code;

  // /start — welcome message, no forward
  if (text === "/start" || text.startsWith("/start ")) {
    // Capture deep-link payload (e.g. /start REF123)
    const payload = text.slice("/start".length).trim();
    if (payload) startPayloads.set(ctx.from.id, payload);

    await ctx.reply(t("welcome", lang));
    return;
  }

  // Ignore other bot commands
  if (text.startsWith("/")) return;

  const user = ctx.from;
  const userId = user.id;
  const name = user.first_name || "User";
  const isFirstMessage = !repliedUsers.has(userId);

  try {
    // Reply only on first message
    if (isFirstMessage) {
      repliedUsers.add(userId);

      // Fire-and-forget: notify Integrately
      fetch(INTEGRATELY_WEBHOOK, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId,
          firstName: user.first_name,
          lastName: user.last_name,
          username: user.username,
          language: lang,
          message: text,
          startPayload: startPayloads.get(userId) || null,
          timestamp: new Date().toISOString(),
        }),
      }).catch((err) => console.error("Integrately webhook failed:", err.message));

      await ctx.reply(t("autoreply", lang, name));
    }

    // Always forward to admin
    await ctx.forwardMessage(ADMIN_CHAT_ID);
  } catch (err) {
    console.error("Error handling message:", err.message);
  }
});

// Graceful shutdown
process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));

bot.launch();
console.log("Bot started — polling for messages");
