const { Telegraf } = require("telegraf");

const BOT_TOKEN = process.env.BOT_TOKEN;
const ADMIN_CHAT_ID = process.env.ADMIN_CHAT_ID || "546485204";

if (!BOT_TOKEN) {
  console.error("Missing BOT_TOKEN environment variable");
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// Track users who already received the auto-reply
const repliedUsers = new Set();

bot.on("text", async (ctx) => {
  const text = ctx.message.text;

  // /start — welcome message, no forward
  if (text === "/start" || text.startsWith("/start ")) {
    await ctx.reply(
      "Welcome to PBS Services! 👋\n\nA member of our team will personally respond to your inquiry. Please type your message below and we'll get back to you as soon as possible.",
    );
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
      await ctx.reply(
        `Hi ${name}, your message has been forwarded to our team. A human support member will get back to you shortly — this is not an automated conversation.`,
      );
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
