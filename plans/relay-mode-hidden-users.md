# Relay Mode for Hidden-Profile Users

## Summary

When a Telegram user has no `@username`, the bot cannot provide a clickable `t.me/username` link for consultants. Instead of forwarding with a useless "Hidden User" header, the bot switches to **relay mode**: copies the message to the group with a "💬 Reply" button, and when tapped, opens a private 1-1 relay session between consultant and bot — the bot bridges messages in both directions.

All existing flows (forward, webhook, auto-reply) remain **untouched** for users WITH a `@username`.

---

## Files Changed

| File | Scope |
|---|---|
| `services/nodejs/src/telegram-bot.js` | ~90 lines added/modified |
| `services/nodejs/config/messages.json` | 3 new strings |

No new dependencies. No DB. All state in-memory (same pattern as existing `repliedUsers` Set).

---

## State (New, All In-Memory)

```js
// Hidden users flagged for relay mode — persists across messages within same process lifetime
const relayUsers = new Set();   // Set<userId>

// Active relay sessions: consultantId → { targetUserId }
// One consultant can have at most one active session at a time
const relaySessions = new Map(); // Map<consultantId, { targetUserId }>
```

---

## Detection

```js
const isHidden = !ctx.from.username;
```

**Rationale**: No `@username` means:
- [`userChatLink`](services/nodejs/src/telegram-bot.js:140) falls back to `tg://user?id=xxx` (unreliable)
- `forwardMessage` shows "Hidden User" in the header — no actionable link
- Consultant cannot DM the user directly

This is a simple heuristic that may include reachable no-username users as false positives, but the cost is negligible (they get the same relay UX, which is still usable).

---

## Message Handler Restructure

The current [`bot.on("text")`](services/nodejs/src/telegram-bot.js:72) handles all text messages uniformly. The restructure adds two guards at the top:

```
bot.on("text")
  │
  ├─ [NEW] Chat type guard: if group/supergroup → return (group messages ignored)
  │
  ├─ [NEW] Consultant relay check: if relaySessions.has(userId)
  │    → relay to target user, handle /close, return
  │
  └─ Existing user-message logic (modified at forward step only)
```

### Guard 1: Ignore Group Messages (~3 lines)

```js
// Only handle private chats — group messages are not processed
if (ctx.chat.type !== "private") return;
```

This prevents the bot from accidentally forwarding group messages to the admin group (latent bug fix).

### Guard 2: Consultant Relay (~15 lines)

```js
// Consultant in active relay session → relay message to target user
const relaySession = relaySessions.get(ctx.from.id);
if (relaySession) {
  if (ctx.message.text === "/close") {
    relaySessions.delete(ctx.from.id);
    await ctx.reply("🔒 Relay session closed.");
    return;
  }
  await withRetry(
    () => ctx.telegram.sendMessage(relaySession.targetUserId, ctx.message.text),
    2,
    `relay consultant→user ${relaySession.targetUserId}`
  );
  await ctx.reply("✅ Sent");
  return;
}
```

---

## Forward/Copy Branch (Replaces Lines 124–129)

The existing [`forwardMessage`](services/nodejs/src/telegram-bot.js:125) call is replaced with a conditional:

```js
let fwdMsg;

if (!isHidden) {
  // ── Normal user: forwardMessage (existing behavior) ──
  fwdMsg = await withRetry(
    () => ctx.forwardMessage(adminChatId),
    2,
    `forward to admin from ${userId}`
  );
} else {
  // ── Hidden user: copyMessage + inline "💬 Reply" button ──
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

  // Also relay to consultant's DM if an active session targets this user
  for (const [consultantId, session] of relaySessions) {
    if (session.targetUserId === userId) {
      await withRetry(
        () => ctx.telegram.sendMessage(consultantId, `📩 *${user.first_name || "User"}*:\n${ctx.message.text}`, { parse_mode: "Markdown" }),
        1,
        `relay user→consultant ${consultantId}`
      );
    }
  }
}
```

**Key behaviors**:
- `relayUsers.add(userId)` — flags the user so subsequent messages follow the same path (already satisfied by `isHidden` check, but explicit flag is self-documenting)
- The inline keyboard is attached **only** via `copyMessage` — `forwardMessage` cannot carry `reply_markup`
- Active session relay: if a consultant already has a session targeting this user, the message also goes to their DM

---

## Callback Handler: "💬 Reply" Button (~20 lines)

New handler added **before** `return bot`:

```js
bot.action(/^relay:(.+)$/, async (ctx) => {
  const targetUserId = ctx.match[1];
  const consultantId = ctx.from.id;

  // Acknowledge callback to stop loading spinner
  await ctx.answerCbQuery();

  // Delete any previous session for this consultant (one session at a time)
  relaySessions.delete(consultantId);

  // Create new session
  relaySessions.set(consultantId, { targetUserId });

  // Edit the group message to show who claimed it
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
    `🔄 *Relay session open*\nReplying to user \`${targetUserId}\`.\nType your messages here — they will be sent to the user.\nSend /close to end the session.`,
    { parse_mode: "Markdown" }
  );
});

// Ignore taps on already-claimed buttons
bot.action("relay:claimed", (ctx) => ctx.answerCbQuery("Already being handled"));
```

---

## Webhook Payload Enhancement (~1 line)

Add `relayMode: true` to the Integrately webhook body when the user is hidden:

```js
const webhookBody = JSON.stringify({
  // ... existing fields unchanged ...
  relayMode: isHidden || relayUsers.has(userId),  // NEW
  // ... rest unchanged ...
});
```

---

## `/reset` Enhancement (~1 line)

Extend `/reset` to also clear relay state:

```js
if (text === "/reset") {
  repliedUsers.delete(ctx.from.id);
  startPayloads.delete(ctx.from.id);
  relayUsers.delete(ctx.from.id);          // NEW
  relaySessions.delete(ctx.from.id);        // NEW (in case consultant resets)
  await ctx.reply("State reset. Your next message will be treated as first contact.");
  return;
}
```

---

## `messages.json` Additions

```json
{
  "relay": {
    "sessionOpen": "🔄 *Relay session open*\nReplying to user `{userId}`.\nType your messages here — they will be sent to the user.\nSend /close to end the session.",
    "sent": "✅ Sent",
    "closed": "🔒 Relay session closed."
  }
}
```

---

## What Does NOT Change

| Component | Status |
|---|---|
| `/start` handler | Untouched |
| `/reset` handler | +2 lines (clear relay state) |
| Rate limiter | Untouched (applies to all users equally) |
| Auto-reply timer | Untouched (fires for hidden users too) |
| Integrately webhook | +1 field (`relayMode`), otherwise identical |
| `forwardedMessageLink` / `userChatLink` | Built from `fwdMsg` the same way for both branches |
| `bot.catch()` | Untouched |
| `withRetry()` | Untouched (used in new code paths) |

---

## Flow Diagram

```
USER SENDS MESSAGE (private chat)
  │
  ├─ Consultant in relay session? → Relay to target user → DONE
  │
  ├─ /start, /reset, other /cmd → Existing handling → DONE
  │
  ├─ Rate limit check → Pass/fail
  │
  ├─ Auto-reply timer reset (unchanged)
  │
  ├─ isHidden = !user.username
  │
  ├─ FORWARD/COPY TO GROUP:
  │    ├─ Has @username → forwardMessage (existing)
  │    └─ No @username  → copyMessage + "💬 Reply" button
  │                        + relay to consultant DM if session active
  │
  ├─ Build deep links (forwardedMessageLink, userChatLink)
  │
  └─ First message?
       ├─ YES → Mark replied, Integrately webhook (+relayMode), schedule auto-reply
       └─ NO  → Only timer reset

CONSULTANT TAPS "💬 Reply" (callback query)
  │
  ├─ Create relay session: consultantId → targetUserId
  ├─ Edit group button → "🔄 Name is replying"
  └─ DM consultant: "Session open. Type here. /close to end."

CONSULTANT TYPES IN BOT DM (private chat, relay session active)
  │
  ├─ /close → End session → DONE
  └─ Any text → sendMessage to target user → reply "✅ Sent"
```

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Bot restarts mid-session | Sessions lost (in-memory). Consultant re-taps "💬 Reply" on next user message. |
| Two consultants tap "💬 Reply" for same user | Second tap overwrites first session. Group button updates. First consultant's messages no longer relayed. |
| Consultant taps "💬 Reply" but never started the bot | `sendMessage` to consultant fails. Bot logs error. Consultant must `/start` the bot once. |
| Hidden user sends `/start` | Welcome reply only — no forward/copy to group. Consistent with existing behavior. |
| User sends sticker/photo (non-text) | Not handled by `bot.on("text")`. Falls through to `bot.catch()`. Out of scope for this feature. |
| `callback_data` exceeds 64 bytes | User IDs are integers well within limit. No risk. |
