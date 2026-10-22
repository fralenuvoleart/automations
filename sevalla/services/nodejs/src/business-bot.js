'use strict';

/**
 * Telegram Business lead capture for @pbservicesGeorgia
 *
 * Customers chat with the business account as usual. The bot is connected in
 * Telegram Business > Chat Automation and is never visible to them.
 *
 * Per new conversation:
 *   1. Every customer message is collected until the customer has been
 *      quiet for BUSINESS_WINDOW_MS (default 45 s after the last message).
 *   2. When the window closes, the auto reply is sent from the business
 *      account, only if nobody from the team has replied in the meantime
 *      (working hours or after hours text, Russian for Russian speakers,
 *      English for everyone else).
 *   3. One webhook is sent to Integrately with all
 *      collected messages, the PIN reference ID, name, username, language,
 *      lead source ("Internet" when a PIN is found, otherwise empty) and a
 *      Telegram link.
 *   4. Further messages from the same customer do not trigger a new reply or
 *      lead for LEAD_COOLDOWN_HOURS (default 24 h).
 *
 * Texts come from config/messages.json ("autoreply", "autoreply_after_hours")
 * and can be overridden with environment variables.
 *
 * Environment:
 *   INTEGRATELY_BUSINESS_WEBHOOK_URL  webhook of the Integrately flow (required)
 *   RESPOND_CUSTOM_CHANNEL_ID         optional, respond.io Custom Channel ID
 *   RESPOND_CUSTOM_CHANNEL_TOKEN      optional, respond.io Custom Channel API token
 *                                     when both are set, every customer message is
 *                                     also posted to respond.io as an incoming message
 *   RESPOND_CUSTOM_CHANNEL_URL        default https://webhook.respond.io/custom/channel/webhook/
 *   BUSINESS_CONNECTION_ID            optional, business connection id used for replies sent
 *                                     from respond.io right after a redeploy (it is also
 *                                     saved to business-connection.json once seen)
 *   RESPOND_API_TOKEN                 optional, respond.io Developer API token: adds the
 *                                     "Telegram" tag and the telegram / contact_details fields
 *   BUSINESS_WINDOW_MS                wait after the last message, default 45000
 *   BUSINESS_MAX_WINDOW_MS            max wait after the first message, default 180000
 *   LEAD_COOLDOWN_HOURS               default 24
 *   BUSINESS_NO_COOLDOWN_IDS          team Telegram IDs without cooldown (testing),
 *                                     default "636546162,7521179737" (Rati, Francesco)
 *   BUSINESS_HOURS                    default "Mon-Fri 10:00-18:00",
 *                                     e.g. "Mon-Fri 10:00-19:00; Sat 10:00-14:00"
 *   BUSINESS_TIMEZONE                 default Asia/Tbilisi
 *   MSG_AUTOREPLY / MSG_AUTOREPLY_RU  optional overrides of the texts
 *   MSG_AUTOREPLY_AFTER_HOURS / MSG_AUTOREPLY_AFTER_HOURS_RU
 *   BUSINESS_TEST_CHAT_IDS            optional comma separated Telegram user IDs;
 *                                     when set, ONLY these chats are processed
 */

const REF_REGEX = /PIN-([A-Z0-9]{4,20})-PBS/i;

let FILE_MSG = {};
try {
  FILE_MSG = require('../config/messages.json');
} catch (_) {
  FILE_MSG = {};
}

const FALLBACK = {
  autoreply: {
    default: 'Thank you, {name}.\nYour message has been received. A member of our team will contact you shortly.',
    ru: 'Спасибо, {name}.\nВаше сообщение получено. Наш специалист свяжется с вами в ближайшее время.',
  },
};

const DAYS = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };

function detectLanguage(text, languageCode) {
  if (/[Ѐ-ӿ]/.test(text)) return 'RU';
  if (/[Ⴀ-ჿ]/.test(text)) return 'GE';
  if (/[؀-ۿ]/.test(text)) return 'AR';
  if (/[一-鿿]/.test(text)) return 'ZH';
  const code = String(languageCode || '').toLowerCase();
  if (code.startsWith('ru')) return 'RU';
  if (code.startsWith('ka')) return 'GE';
  if (code.startsWith('ar')) return 'AR';
  if (code.startsWith('zh')) return 'ZH';
  return 'EN';
}

/**
 * Parse "Mon-Fri 10:00-19:00; Sat 10:00-14:00" into
 * [{ days: Set<number>, from: minutes, to: minutes }]. Invalid parts are ignored.
 */
function parseBusinessHours(spec) {
  const rules = [];
  String(spec || '')
    .split(';')
    .map((s) => s.trim())
    .filter(Boolean)
    .forEach((part) => {
      const m = part.match(/^([a-z]{3})(?:\s*-\s*([a-z]{3}))?\s+(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$/i);
      if (!m) return;
      const a = DAYS[m[1].toLowerCase()];
      const b = m[2] ? DAYS[m[2].toLowerCase()] : a;
      if (a === undefined || b === undefined) return;
      const days = new Set();
      for (let d = a; ; d = (d + 1) % 7) {
        days.add(d);
        if (d === b) break;
      }
      rules.push({ days, from: +m[3] * 60 + +m[4], to: +m[5] * 60 + +m[6] });
    });
  return rules;
}

function isWithinHours(rules, timeZone, date = new Date()) {
  if (!rules.length) return true;
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const get = (t) => (parts.find((p) => p.type === t) || {}).value;
  const day = DAYS[String(get('weekday')).toLowerCase()];
  const minutes = parseInt(get('hour'), 10) * 60 + parseInt(get('minute'), 10);
  return rules.some((r) => r.days.has(day) && minutes >= r.from && minutes < r.to);
}

function fillName(template, name) {
  const clean = String(name || '').trim();
  if (clean) return template.split('{name}').join(clean);
  return template.replace(/,?\s*\{name\}/g, '');
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

function telegramLink(user) {
  if (user.username) return 'https://t.me/' + user.username;
  return user.id ? 'tg://user?id=' + user.id : '';
}

/**
 * Post one customer message to a respond.io Custom Channel as an incoming
 * message, so the conversation shows the real message at the top of the inbox.
 * The contact is identified by the Telegram user ID (Custom ID).
 */
async function pushToRespond(cfg, from, msg, text, log, type = 'message') {
  if (!cfg.channelId || !cfg.token || !from || !from.id) return;
  const body = {
    channelId: cfg.channelId,
    contactId: String(from.id),
    events: [
      {
        type,
        mId: ('tg' + msg.chat.id + '_' + msg.message_id).slice(0, 50),
        timestamp: (msg.date ? msg.date * 1000 : Date.now()),
        message: { type: 'text', text: String(text).slice(0, 7000) },
      },
    ],
    contact: type !== 'message' ? undefined : {
      firstName: from.first_name || '',
      lastName: from.last_name || '',
      language: from.language_code || '',
      email: from.id + '@noemail.com',
    },
  };
  try {
    const res = await fetch(cfg.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', authorization: 'Bearer ' + cfg.token },
      body: JSON.stringify(body),
    });
    if (!res.ok) log.warn('[respond] HTTP ' + res.status + ' for contact ' + from.id);
  } catch (err) {
    log.warn('[respond] error for contact ' + from.id + ': ' + err.message);
  }
}

// State used to send replies written in respond.io back to Telegram.
const outbound = { telegram: null, connectionId: null, log: console };

// Keep the business connection id across restarts, so replies from respond.io
// work before the next customer message arrives.
const CONNECTION_FILE = require('path').join(process.cwd(), 'business-connection.json');
try {
  outbound.connectionId = JSON.parse(require('fs').readFileSync(CONNECTION_FILE, 'utf8')).id || null;
} catch (_) { /* no saved id yet */ }
if (!outbound.connectionId && process.env.BUSINESS_CONNECTION_ID) outbound.connectionId = process.env.BUSINESS_CONNECTION_ID;

function setOutboundConnection(id) {
  if (!id || id === outbound.connectionId) return;
  outbound.connectionId = id;
  outbound.log.info('[respond] business connection for replies: ' + id);
  try {
    require('fs').writeFileSync(CONNECTION_FILE, JSON.stringify({ id }));
  } catch (err) {
    outbound.log.warn('[respond] could not save business connection: ' + err.message);
  }
}

async function respondApi(cfg, method, path, body, log) {
  const res = await fetch('https://api.respond.io/v2' + path, {
    method,
    headers: { 'Content-Type': 'application/json', authorization: 'Bearer ' + cfg.apiToken },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) log.warn('[respond] API ' + method + ' ' + path + ' HTTP ' + res.status);
  return res.ok;
}

/**
 * Add the "Telegram" tag and the telegram / contact_details fields to the
 * respond.io contact (identified by ID@noemail.com). Runs once per contact.
 */
const enriched = new Set();
async function enrichRespondContact(cfg, from, log) {
  if (!cfg.apiToken || !from || !from.id || enriched.has(from.id)) return;
  enriched.add(from.id);
  const id = 'email:' + from.id + '@noemail.com';
  const body = {
    firstName: from.first_name || String(from.id),
    lastName: from.last_name || '',
    custom_fields: [
      { name: 'telegram', value: from.username ? '@' + from.username : '' },
      { name: 'contact_details', value: telegramLink(from) },
    ],
  };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    for (const delay of [5000, 15000]) {
      await wait(delay); // give respond.io time to create the contact
      const ok = await respondApi(cfg, 'PUT', '/contact/' + id, body, log);
      if (ok) {
        await respondApi(cfg, 'POST', '/contact/' + id + '/tag', ['Telegram'], log);
        return;
      }
    }
    enriched.delete(from.id);
  } catch (err) {
    enriched.delete(from.id);
    log.warn('[respond] enrich error for contact ' + from.id + ': ' + err.message);
  }
}

/**
 * Send a reply written in respond.io to the customer, from the business
 * account. Called by the HTTP server (POST /respond/outgoing).
 * Returns the Telegram message id.
 */
async function sendFromRespond(contactId, message) {
  if (!outbound.telegram || !outbound.connectionId) throw new Error('business connection not ready');
  let text = '';
  if (message && message.type === 'text') text = message.text || '';
  else if (message && message.type === 'attachment' && message.attachment) text = message.attachment.url || '';
  else if (message && message.text) text = message.text;
  if (!text) throw new Error('unsupported message type');
  const sent = await outbound.telegram.sendMessage(contactId, text, { business_connection_id: outbound.connectionId });
  return 'tg' + contactId + '_' + sent.message_id;
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
  const windowMs = parseInt(env.BUSINESS_WINDOW_MS || '45000', 10);
  const maxWindowMs = parseInt(env.BUSINESS_MAX_WINDOW_MS || '180000', 10);
  const cooldownMs = parseFloat(env.LEAD_COOLDOWN_HOURS || '24') * 3600 * 1000;
  const timeZone = env.BUSINESS_TIMEZONE || 'Asia/Tbilisi';
  const hoursSpec = env.BUSINESS_HOURS || 'Mon-Fri 10:00-18:00';
  const hours = parseBusinessHours(hoursSpec);
  const testIds = String(env.BUSINESS_TEST_CHAT_IDS || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const respondCfg = {
    url: env.RESPOND_CUSTOM_CHANNEL_URL || 'https://webhook.respond.io/custom/channel/webhook/',
    channelId: env.RESPOND_CUSTOM_CHANNEL_ID || '',
    token: env.RESPOND_CUSTOM_CHANNEL_TOKEN || '',
    apiToken: env.RESPOND_API_TOKEN || '',
  };
  outbound.telegram = bot.telegram;
  outbound.log = log;
  // Team accounts that are never blocked by the cooldown (for testing).
  const noCooldownIds = new Set(
    String(env.BUSINESS_NO_COOLDOWN_IDS || '636546162,7521179737')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  );

  if (!webhookUrl) {
    log.warn('[business] INTEGRATELY_BUSINESS_WEBHOOK_URL not set, business lead capture disabled');
    return;
  }
  if (!hours.length) {
    log.warn('[business] BUSINESS_HOURS could not be parsed, working hours text is always used');
  }

  function replyText(lang, afterHours) {
    const isRu = lang === 'RU';
    const pick = (key, envName) => {
      const fromEnv = env[envName + (isRu ? '_RU' : '')];
      if (fromEnv) return fromEnv.replace(/\\n/g, '\n');
      const block = FILE_MSG[key] || {};
      return isRu ? block.ru || block.default : block.default;
    };
    if (afterHours) {
      const t = pick('autoreply_after_hours', 'MSG_AUTOREPLY_AFTER_HOURS');
      if (t) return t;
    }
    return pick('autoreply', 'MSG_AUTOREPLY') || (isRu ? FALLBACK.autoreply.ru : FALLBACK.autoreply.default);
  }

  // business_connection_id -> { ownerId, canReply }
  const connections = new Map();
  // chatId -> session { connectionId, messages[], firstAt, from, teamReplied, autoReplySent }
  const sessions = new Map();
  // chatId -> timestamp of last conversation start
  const recent = new Map();

  function rememberConnection(conn) {
    if (!conn || !conn.id) return;
    const canReply =
      conn.can_reply === true ||
      (conn.rights && conn.rights.can_reply === true);
    connections.set(conn.id, { ownerId: conn.user && conn.user.id, canReply, enabled: conn.is_enabled !== false });
    if (conn.is_enabled !== false && canReply) setOutboundConnection(conn.id);
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

  async function sendAutoReply(telegram, chatId, s) {
    const conn = connections.get(s.connectionId);
    if (conn && conn.canReply === false) {
      log.warn('[business] bot has no permission to reply, auto reply skipped');
      return;
    }
    const lang = detectLanguage(s.messages.join('\n'), s.from.language_code);
    const afterHours = !isWithinHours(hours, timeZone);
    const text = fillName(replyText(lang, afterHours), s.from.first_name);
    try {
      await telegram.sendMessage(chatId, text, { business_connection_id: s.connectionId });
      s.autoReplySent = true;
      s.afterHours = afterHours;
    } catch (err) {
      log.error(`[business] auto reply failed: ${err.message}`);
    }
  }

  async function closeWindow(telegram, chatId) {
    const s = sessions.get(chatId);
    if (!s) return;
    sessions.delete(chatId);

    if (!s.teamReplied) await sendAutoReply(telegram, chatId, s);

    const combined = s.messages.join('\n');
    const lang = detectLanguage(combined, s.from.language_code);
    const refMatch = combined.match(REF_REGEX);
    const payload = {
      source: 'telegram_business',
      lead_source: refMatch ? 'Internet' : '',
      reference_id: refMatch ? refMatch[1].toUpperCase() : '',
      reference_full: refMatch ? refMatch[0] : '',
      telegram_user_id: s.from.id,
      username: s.from.username || '',
      telegram_link: telegramLink(s.from),
      first_name: s.from.first_name || '',
      last_name: s.from.last_name || '',
      full_name: [s.from.first_name, s.from.last_name].filter(Boolean).join(' '),
      language: lang,
      first_message: s.messages[0] || '',
      messages: combined,
      message_count: s.messages.length,
      first_message_at: new Date(s.firstAt).toISOString(),
      team_replied_within_window: s.teamReplied,
      auto_reply_sent: s.autoReplySent,
      after_hours: !!s.afterHours,
    };

    const ok = await postWebhook(webhookUrl, payload, log);
    log.info(`[business] lead chat=${chatId} msgs=${s.messages.length} source=${payload.lead_source || '-'} ref=${payload.reference_id || '-'} webhook=${ok}`);
  }

  bot.on('business_connection', (ctx) => {
    rememberConnection(ctx.update.business_connection);
  });

  bot.on('business_message', async (ctx) => {
    const msg = ctx.update.business_message;
    if (!msg || !msg.chat || msg.chat.type !== 'private') return;

    const chatId = msg.chat.id;
    const connectionId = msg.business_connection_id;
    if (connectionId) setOutboundConnection(connectionId);

    if (testIds.length && !testIds.includes(String(chatId))) return;

    const conn = await getConnection(ctx.telegram, connectionId);
    const ownerId = conn && conn.ownerId;
    const fromOwner = msg.from && ownerId && msg.from.id === ownerId;

    // A message written by the team in this chat.
    if (fromOwner) {
      // Mirror replies written in the Telegram app (not those sent from respond.io).
      if (!msg.sender_business_bot) pushToRespond(respondCfg, { id: chatId }, msg, messageText(msg), log, 'message_echo');
      const s = sessions.get(chatId);
      if (s) s.teamReplied = true;
      return;
    }

    // Customer message: mirror it to respond.io (if configured).
    pushToRespond(respondCfg, msg.from, msg, messageText(msg), log);
    enrichRespondContact(respondCfg, msg.from, log);

    // Customer message.
    // The reply is sent windowMs after the customer's LAST message
    // (never later than maxWindowMs after the first one).
    const schedule = (sess) => {
      clearTimeout(sess.timer);
      const wait = Math.max(0, Math.min(windowMs, sess.firstAt + maxWindowMs - Date.now()));
      sess.timer = setTimeout(() => {
        closeWindow(ctx.telegram, chatId).catch((e) => log.error('[business] ' + e.message));
      }, wait);
    };

    let s = sessions.get(chatId);
    if (s) {
      s.messages.push(messageText(msg));
      schedule(s);
      return;
    }

    const last = recent.get(chatId);
    if (last && Date.now() - last < cooldownMs && !noCooldownIds.has(String(chatId))) return;
    recent.set(chatId, Date.now());

    s = {
      connectionId,
      messages: [messageText(msg)],
      firstAt: Date.now(),
      from: msg.from || {},
      teamReplied: false,
      autoReplySent: false,
      afterHours: false,
    };
    sessions.set(chatId, s);
    schedule(s);
  });

  // Clean up the cooldown map once an hour.
  setInterval(() => {
    const now = Date.now();
    for (const [id, ts] of recent) if (now - ts > cooldownMs) recent.delete(id);
  }, 3600 * 1000).unref();

  log.info(
    `[business] lead capture ready (window ${windowMs} ms, cooldown ${cooldownMs / 3600000} h, hours ${hours.length ? hoursSpec + ' ' + timeZone : 'not set'}${respondCfg.channelId && respondCfg.token ? ', respond.io ON' : ''}${testIds.length ? ', TEST MODE' : ''})`
  );
}

/**
 * Update types to request when launching the bot. Telegram keeps the
 * allowed_updates list from the last webhook/polling call, so we pass it
 * explicitly to make sure business updates are delivered.
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

module.exports = {
  sendFromRespond,
  attachBusinessHandlers,
  detectLanguage,
  parseBusinessHours,
  isWithinHours,
  fillName,
  REF_REGEX,
  ALLOWED_UPDATES,
};
