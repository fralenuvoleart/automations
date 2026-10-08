'use strict';

/**
 * Telegram Business lead capture for @pbservicesGeorgia
 *
 * Customers chat with the business account as usual. The bot is connected in
 * Telegram Business > Chatbots and is never visible to them.
 *
 * Per new conversation:
 *   1. The first customer message opens a collection window (default 30 s).
 *   2. Every customer message in that window is collected.
 *   3. When the window closes:
 *        - if nobody from the team replied, the auto reply is sent from the
 *          business account;
 *        - one webhook is sent to Integrately with all collected messages,
 *          the PIN reference ID, name, username and language.
 *   4. Further messages from the same customer do not create a new lead for
 *      LEAD_COOLDOWN_HOURS (default 24 h).
 *
 * Environment:
 *   INTEGRATELY_BUSINESS_WEBHOOK_URL  webhook of the Integrately flow (required)
 *   BUSINESS_WINDOW_MS                collection window, default 30000
 *   LEAD_COOLDOWN_HOURS               default 24
 *   MSG_AUTOREPLY / MSG_AUTOREPLY_RU  auto reply texts (EN / RU)
 *   BUSINESS_TEST_CHAT_IDS            optional comma separated Telegram user IDs;
 *                                     when set, ONLY these chats are processed
 *                                     (safe testing before going live)
 */

const REF_REGEX = /PIN-([A-Z0-9]{4,20})-PBS/i;

const DEFAULT_AUTOREPLY_EN =
  'Thank you for your message! Someone from our team will contact you shortly.';
const DEFAULT_AUTOREPLY_RU =
  'Спасибо за ваше сообщение! Наш специалист свяжется с вами в ближайшее время.';

function detectLanguage(text, languageCode) {
  if (/[\u0400-\u04FF]/.test(text)) return 'RU';
  if (/[\u10A0-\u10FF]/.test(text)) return 'GE';
  if (/[\u0600-\u06FF]/.test(text)) return 'AR';
  if (/[\u4E00-\u9FFF]/.test(text)) return 'ZH';
  const code = String(languageCode || '').toLowerCase();
  if (code.startsWith('ru')) return 'RU';
  if (code.startsWith('ka')) return 'GE';
  if (code.startsWith('ar')) return 'AR';
  if (code.startsWith('zh')) return 'ZH';
  return 'EN';
}

function messageText(msg) {
  if (msg.text) return msg.text;
  if (msg.caption) return msg.caption;
  if (msg.photo) return '[photo]';
  if (msg.document) return '[file: ' + (msg.document.file_name || 'document') + ']';
  if (msg.voice) return '[voice message]';
  if (msg.video) return '[video]';
  if (msg.sticker) return '[sticker]';
  if (msg.contact) return '[contact: ' + (msg.contact.phone_number || '') + ']';
  if (msg.location) return '[location]';
  return '[message]';
}

async function postWebhook(url, payload, log, attempts = 3) {
  for (let i = 1; i <= attempts; i++) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) return true;
      log.warn(`[business] webhook HTTP ${res.status} (attempt ${i})`);
    } catch (err) {
      log.warn(`[business] webhook error (attempt ${i}): ${err.message}`);
    }
    await new Promise((r) => setTimeout(r, 2000 * i));
  }
  log.error('[business] webhook failed after retries');
  return false;
}

/**
 * Attach the business handlers to an existing Telegraf bot instance.
 * Call this before bot.launch().
 */
function attachBusinessHandlers(bot, opts = {}) {
  const log = opts.logger || console;
  const env = process.env;
  const webhookUrl = env.INTEGRATELY_BUSINESS_WEBHOOK_URL;
  const windowMs = parseInt(env.BUSINESS_WINDOW_MS || '30000', 10);
  const cooldownMs = parseFloat(env.LEAD_COOLDOWN_HOURS || '24') * 3600 * 1000;
  const testIds = String(env.BUSINESS_TEST_CHAT_IDS || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  if (!webhookUrl) {
    log.warn('[business] INTEGRATELY_BUSINESS_WEBHOOK_URL not set, business lead capture disabled');
    return;
  }

  // business_connection_id -> { ownerId, canReply }
  const connections = new Map();
  // chatId -> session { connectionId, messages[], firstAt, from, teamReplied, timer }
  const sessions = new Map();
  // chatId -> timestamp of last lead sent
  const recentLeads = new Map();

  function rememberConnection(conn) {
    if (!conn || !conn.id) return;
    const canReply =
      conn.can_reply === true ||
      (conn.rights && conn.rights.can_reply === true);
    connections.set(conn.id, { ownerId: conn.user && conn.user.id, canReply, enabled: conn.is_enabled !== false });
    log.info(`[business] connection ${conn.id} enabled=${conn.is_enabled !== false} canReply=${canReply}`);
  }

  async function getConnection(telegram, id) {
    if (connections.has(id)) return connections.get(id);
    try {
      const conn = await telegram.callApi('getBusinessConnection', { business_connection_id: id });
      rememberConnection(conn);
    } catch (err) {
      log.warn(`[business] getBusinessConnection failed: ${err.message}`);
    }
    return connections.get(id);
  }

  async function closeWindow(telegram, chatId) {
    const s = sessions.get(chatId);
    if (!s) return;
    sessions.delete(chatId);

    const lang = detectLanguage(s.messages.join('\n'), s.from.language_code);
    let autoReplySent = false;

    if (!s.teamReplied) {
      const conn = connections.get(s.connectionId);
      const text =
        lang === 'RU'
          ? env.MSG_AUTOREPLY_RU || DEFAULT_AUTOREPLY_RU
          : env.MSG_AUTOREPLY || DEFAULT_AUTOREPLY_EN;
      if (conn && conn.canReply === false) {
        log.warn('[business] bot has no permission to reply, auto reply skipped');
      } else {
        try {
          await telegram.sendMessage(chatId, text, { business_connection_id: s.connectionId });
          autoReplySent = true;
        } catch (err) {
          log.error(`[business] auto reply failed: ${err.message}`);
        }
      }
    }

    const combined = s.messages.join('\n');
    const refMatch = combined.match(REF_REGEX);
    const payload = {
      source: 'telegram_business',
      reference_id: refMatch ? refMatch[1].toUpperCase() : '',
      reference_full: refMatch ? refMatch[0] : '',
      telegram_user_id: s.from.id,
      username: s.from.username || '',
      first_name: s.from.first_name || '',
      last_name: s.from.last_name || '',
      full_name: [s.from.first_name, s.from.last_name].filter(Boolean).join(' '),
      language: lang,
      first_message: s.messages[0] || '',
      messages: combined,
      message_count: s.messages.length,
      first_message_at: new Date(s.firstAt).toISOString(),
      team_replied_within_window: s.teamReplied,
      auto_reply_sent: autoReplySent,
    };

    const ok = await postWebhook(webhookUrl, payload, log);
    if (ok) recentLeads.set(chatId, Date.now());
    log.info(`[business] lead chat=${chatId} msgs=${s.messages.length} ref=${payload.reference_id || '-'} webhook=${ok}`);
  }

  bot.on('business_connection', (ctx) => {
    rememberConnection(ctx.update.business_connection);
  });

  bot.on('business_message', async (ctx) => {
    const msg = ctx.update.business_message;
    if (!msg || !msg.chat || msg.chat.type !== 'private') return;

    const chatId = msg.chat.id;
    const connectionId = msg.business_connection_id;

    if (testIds.length && !testIds.includes(String(chatId))) return;

    const conn = await getConnection(ctx.telegram, connectionId);
    const ownerId = conn && conn.ownerId;
    const fromOwner = msg.from && ownerId && msg.from.id === ownerId;

    // A message written by the team in this chat.
    if (fromOwner) {
      const s = sessions.get(chatId);
      if (s) s.teamReplied = true;
      return;
    }

    // Customer message.
    const last = recentLeads.get(chatId);
    if (!sessions.has(chatId) && last && Date.now() - last < cooldownMs) return;

    let s = sessions.get(chatId);
    if (!s) {
      s = {
        connectionId,
        messages: [],
        firstAt: Date.now(),
        from: msg.from || {},
        teamReplied: false,
        timer: null,
      };
      sessions.set(chatId, s);
      s.timer = setTimeout(() => {
        closeWindow(ctx.telegram, chatId).catch((e) => log.error('[business] ' + e.message));
      }, windowMs);
    }
    s.messages.push(messageText(msg));
  });

  // Clean up the cooldown map once an hour.
  setInterval(() => {
    const now = Date.now();
    for (const [id, ts] of recentLeads) if (now - ts > cooldownMs) recentLeads.delete(id);
  }, 3600 * 1000).unref();

  log.info(`[business] lead capture ready (window ${windowMs} ms, cooldown ${cooldownMs / 3600000} h${testIds.length ? ', TEST MODE' : ''})`);
}

/**
 * Update types to request when launching the bot. Telegram keeps the
 * allowed_updates list from the last webhook/polling call (respond.io may have
 * set a narrower one), so we pass it explicitly to make sure business updates
 * are delivered.
 */
const ALLOWED_UPDATES = [
  'message',
  'edited_message',
  'callback_query',
  'my_chat_member',
  'business_connection',
  'business_message',
  'edited_business_message',
  'deleted_business_messages',
];

module.exports = { attachBusinessHandlers, detectLanguage, REF_REGEX, ALLOWED_UPDATES };
