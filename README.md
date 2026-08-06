# automations

Node.js + Python automation services for PBServices.

## Structure

```
services/
├── nodejs/               ← Production: Telegram bot + cache warmer + WhatsApp bot (future)
│   ├── src/
│   │   ├── telegram-bot.js    ← Telegram bot: auto-reply, forwarding, Integrately webhook
│   │   └── cache-warmer.js    ← Daily sitemap-based cache warming for pbservices.ge
│   ├── config/
│   │   └── messages.json      ← EN/RU welcome + auto-reply messages
│   ├── index.js               ← Entry point: wires bot + cron scheduler
│   ├── package.json
│   └── .env.example
└── python/               ← Future: AI/NLP, data analytics, image processing
```

## Sevalla

| App | Build path | Pod | Cost |
|-----|-----------|-----|------|
| automations-nodejs | `services/nodejs` | h1 (0.3 CPU, 300 MB) | ~$5.83/mo |
| automations-python | `services/python` | h1 (future) | ~$5.83/mo |

## Local development

```bash
cd services/nodejs
npm install
cp .env.example .env   # edit with real token
npm run dev
```
