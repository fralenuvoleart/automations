const { Telegraf } = require("telegraf");

const INTEGRATELY_WEBHOOK =
  process.env.INTEGRATELY_WEBHOOK_URL ||
  "https://webhooks.integrately.com/a/webhooks/11e1f7e4cb3e4517abcea0d9cd833383";

// ── Helpers ──

/** Retry an async fn up to `retries` times with exponential backoff. */
async function withRetry(fn, retries = 2, label = "") {
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (err) {
      if (i < retries) {
        const ms = 2 ** i * 500;
        console.warn(`[retry ${i + 1}/${retries}] ${label}: ${err.message} — waiting ${ms}ms`);
        await new Promise((r) => setTimeout(r, ms));
      } else {
        console.error(`[failed] ${label}: ${err.message}`);
      }
    }
  }
}

// ── Rate limiter: max 3 messages per user per 10-second window ──
const rateLimitMap = new Map();
const RATE_WINDOW_MS = 10_000;
const RATE_MAX = 3;

function checkRateLimit(userId) {
  const now = Date.now();
  const entry = rateLimitMap.get(userId);
  if (!entry || now - entry.windowStart > RATE_WINDOW_MS) {
    rateLimitMap.set(userId, { windowStart: now, count: 1 });
    return true;
  }
  if (entry.count >= RATE_MAX) return false;
  entry.count++;
  return true;
}

// ── Bot factory ──

/**
 * Creates and configures the Telegram bot instance.
 * @param {string} token - Bot token from @BotFather
 * @param {string} adminChatId - Chat ID to forward messages to
 * @param {object} messages - Loaded messages.json content
 * @returns {Telegraf} configured bot instance
 */
function createBot(token, adminChatId, messages) {
  // Deep-clone to prevent env-var overrides from mutating the original require() cache
  const MSG = JSON.parse(JSON.stringify(messages));

  if (process.env.MSG_WELCOME) MSG.welcome.default = process.env.MSG_WELCOME;
  if (process.env.MSG_WELCOME_RU) MSG.welcome.ru = process.env.MSG_WELCOME_RU;
  if (process.env.MSG_AUTOREPLY) MSG.autoreply.default = process.env.MSG_AUTOREPLY;
  if (process.env.MSG_AUTOREPLY_RU) MSG.autoreply.ru = process.env.MSG_AUTOREPLY_RU;

  const t = (key, lang, name) => {
    const msg = MSG[key][lang] || MSG[key].default;
    return name ? msg.replace("{name}", name) : msg;
  };

  const bot = new Telegraf(token);

  // In-memory state: tracks first-contact users and /start deep-link payloads
  const repliedUsers = new Set();
  const startPayloads = new Map();
  const autoreplyTimers = new Map(); // userId → timeoutId for delayed auto-reply

  // Relay-mode state: hidden users (no @username) and active consultant sessions
  const relayUsers = new Set(); // Set<userId> — users flagged for relay mode
  const relaySessions = new Map(); // Map<consultantId, { targetUserId }> — active 1-1 relays

  bot.on("text", async (ctx) => {
    // ── Guard 1: only handle private chats ──
    if (ctx.chat.type !== "private") return;

    // ── Guard 2: consultant in active relay session → relay message to user ──
    const relaySession = relaySessions.get(ctx.from.id);
    if (relaySession) {
      if (ctx.message.text === "/close") {
        relaySessions.delete(ctx.from.id);
        await ctx.reply(MSG.relay.closed);
        return;
      }
      // Ignore other bot commands — only relay plain text
      if (ctx.message.text.startsWith("/")) return;
      const sent = await withRetry(
        () => ctx.telegram.sendMessage(relaySession.targetUserId, ctx.message.text),
        2,
        `relay consultant→user ${relaySession.targetUserId}`
      );
      await ctx.reply(sent ? MSG.relay.sent : "⚠️ Failed to send. The user may have blocked the bot.");
      return;
    }

    const text = ctx.message.text;
    const lang = ctx.from?.language_code;

    // /start — welcome message, no forward
    if (text === "/start" || text.startsWith("/start ")) {
      const payload = text.slice("/start".length).trim();
      if (payload) startPayloads.set(ctx.from.id, payload);
      await ctx.reply(t("welcome", lang));
      return;
    }

    // /reset — clear first-message flag and relay state for re-testing
    if (text === "/reset") {
      repliedUsers.delete(ctx.from.id);
      startPayloads.delete(ctx.from.id);
      relayUsers.delete(ctx.from.id);
      relaySessions.delete(ctx.from.id);
      await ctx.reply("State reset. Your next message will be treated as first contact.");
      return;
    }

    // Ignore other bot commands
    if (text.startsWith("/")) return;

    const user = ctx.from;
    const userId = user.id;

    // Rate-limit check
    if (!checkRateLimit(userId)) {
      console.warn(`[rate-limit] Dropping message from user ${userId}`);
      return;
    }

    const name = user.first_name || "User";
    const isFirstMessage = !repliedUsers.has(userId);

    // Reset delayed auto-reply timer on every new message (restarts the delay)
    if (autoreplyTimers.has(userId)) {
      clearTimeout(autoreplyTimers.get(userId));
      
      // Re-schedule the timer
      const autoReplyDelay = parseInt(process.env.AUTOREPLY_DELAY_MS || "10000", 10);
      const timerId = setTimeout(async () => {
        autoreplyTimers.delete(userId);
        await withRetry(
          () => ctx.telegram.sendMessage(userId, t("autoreply", lang, name)),
          2,
          `autoreply to ${userId}`
        );
      }, autoReplyDelay);
      autoreplyTimers.set(userId, timerId);
    }

    // ── Forward/copy to admin (critical — retry) ──
    const isHidden = !user.username;
    let fwdMsg;

    if (!isHidden) {
      // Normal user: forwardMessage with native header (existing behavior)
      fwdMsg = await withRetry(
        () => ctx.forwardMessage(adminChatId),
        2,
        `forward to admin from ${userId}`
      );

      // If Telegram hid the user's identity in the forward (privacy "Nobody"),
      // annotate with a clickable @username so admins can still identify them.
      if (fwdMsg?.forward_origin?.type === 'hidden_user' && user.username) {
        await withRetry(
          () =>
            ctx.telegram.sendMessage(adminChatId, `This user has forwarding privacy enabled`, {
              reply_markup: {
                inline_keyboard: [[
                  { text: `@${user.username}`, url: `https://t.me/${user.username}` }
                ]]
              }
            }),
          2,
          `hidden-user annotation for ${userId}`
        );
      }
    } else {
      // Hidden user (no @username): copyMessage + inline "💬 Reply" button
      relayUsers.add(userId);

      fwdMsg = await withRetry(
        () =>
          ctx.telegram.copyMessage(adminChatId, ctx.chat.id, ctx.message.message_id, {
            reply_markup: {
              inline_keyboard: [[
                { text: "💬 Reply", callback_data: `relay:${userId}` }
              ]]
            }
          }),
        2,
        `copyMessage to admin from ${userId}`
      );

      // Fire-and-forget: also relay to consultant DM if session targets this user
      for (const [consultantId, session] of relaySessions) {
        if (session.targetUserId === userId) {
          withRetry(
            () => ctx.telegram.sendMessage(consultantId, `📩 ${user.first_name || "User"}:\n${ctx.message.text}`),
            1,
            `relay user→consultant ${consultantId}`
          );
        }
      }
    }

    // Deep link to forwarded message in Staff Group Chat
    const cleanGroupId = adminChatId.startsWith("-100")
      ? adminChatId.slice(4)
      : adminChatId;
    const forwardedMessageLink = fwdMsg?.message_id
      ? `https://t.me/c/${cleanGroupId}/${fwdMsg.message_id}`
      : null;

    // Deep link to open chat with the user
    const userChatLink = user.username
      ? `https://t.me/${user.username}`
      : `tg://user?id=${userId}`;

    // ── First-message handling ──
    if (isFirstMessage) {
      repliedUsers.add(userId);

      // Fire-and-forget with retry: notify Integrately
      const payload = startPayloads.get(userId);
      if (payload !== undefined) startPayloads.delete(userId); // clean up

      const webhookBody = JSON.stringify({
        userId,
        firstName: user.first_name,
        lastName: user.last_name,
        username: user.username,
        language: lang,
        message: text,
        startPayload: payload || null,
        forwardedMessageLink,
        userChatLink,
        relayMode: isHidden || relayUsers.has(userId),
        timestamp: new Date().toISOString(),
      });

      // Non-blocking: retry webhook in background
      withRetry(
        () =>
          fetch(INTEGRATELY_WEBHOOK, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: webhookBody,
          }).then((res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            console.log(`[success] Integrately webhook for user ${userId}`);
          }),
        2,
        `Integrately webhook for user ${userId}`
      );

      // Schedule delayed auto-reply (configurable, resets on new messages)
      const autoReplyDelay = parseInt(process.env.AUTOREPLY_DELAY_MS || "10000", 10);
      const timerId = setTimeout(async () => {
        autoreplyTimers.delete(userId);
        await withRetry(
          () => ctx.telegram.sendMessage(userId, t("autoreply", lang, name)),
          2,
          `autoreply to ${userId}`
        );
      }, autoReplyDelay);
      autoreplyTimers.set(userId, timerId);
    }
  });

  // ── Callback handler: "💬 Reply" button for hidden users ──
  bot.action(/^relay:(.+)$/, async (ctx) => {
    const targetUserId = Number(ctx.match[1]);
    const consultantId = ctx.from.id;

    await ctx.answerCbQuery();

    // One session per consultant — overwrite any previous
    relaySessions.delete(consultantId);
    relaySessions.set(consultantId, { targetUserId });

    // Edit group button to show who claimed the conversation
    const consultantName = ctx.from.first_name || "A consultant";
    try {
      await ctx.editMessageReplyMarkup({
        inline_keyboard: [[
          { text: `🔄 ${consultantName} is replying`, callback_data: "relay:claimed" }
        ]]
      });
    } catch (_) { /* message may have been deleted */ }

    // DM the consultant to start the relay
    await ctx.telegram.sendMessage(
      consultantId,
      MSG.relay.sessionOpen.replace("{userId}", targetUserId),
      { parse_mode: "Markdown" }
    );
  });

  // Ignore taps on already-claimed buttons
  bot.action("relay:claimed", (ctx) => ctx.answerCbQuery("Already being handled"));

  // Global error handler to prevent unhandled rejections from crashing the bot
  bot.catch((err, ctx) => {
    console.error(`[bot.catch] Error for ${ctx.updateType}:`, err);
  });

  return bot;
}

module.exports = { createBot };
