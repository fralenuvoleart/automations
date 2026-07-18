const { Telegraf } = require("telegraf");

const INTEGRATELY_WEBHOOK =
  "https://webhooks.integrately.com/a/webhooks/11e1f7e4cb3e4517abcea0d9cd833383";

/**
 * Creates and configures the Telegram bot instance.
 * @param {string} token - Bot token from @BotFather
 * @param {string} adminChatId - Chat ID to forward messages to
 * @param {object} messages - Loaded messages.json content
 * @returns {Telegraf} configured bot instance
 */
function createBot(token, adminChatId, messages) {
  const MSG = { ...messages };
  // Env var overrides for emergencies
  if (process.env.MSG_WELCOME) MSG.welcome.default = process.env.MSG_WELCOME;
  if (process.env.MSG_WELCOME_RU) MSG.welcome.ru = process.env.MSG_WELCOME_RU;
  if (process.env.MSG_AUTOREPLY) MSG.autoreply.default = process.env.MSG_AUTOREPLY;
  if (process.env.MSG_AUTOREPLY_RU) MSG.autoreply.ru = process.env.MSG_AUTOREPLY_RU;

  const t = (key, lang, name) => {
    const msg = MSG[key][lang] || MSG[key].default;
    return msg.replace("{name}", name);
  };

  const bot = new Telegraf(token);

  // In-memory state: tracks first-contact users and /start deep-link payloads
  const repliedUsers = new Set();
  const startPayloads = new Map();

  bot.on("text", async (ctx) => {
    const text = ctx.message.text;
    const lang = ctx.from?.language_code;

    // /start — welcome message, no forward
    if (text === "/start" || text.startsWith("/start ")) {
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
        }).catch((err) =>
          console.error("Integrately webhook failed:", err.message)
        );

        await ctx.reply(t("autoreply", lang, name));
      }

      // Always forward to admin
      await ctx.forwardMessage(adminChatId);
    } catch (err) {
      console.error("Error handling message:", err.message);
    }
  });

  return bot;
}

module.exports = { createBot };
