# Product Context

## What this is

`automations` — a small operations repo with two service runtimes and a shared Agent-Skills toolkit.

## Runtimes

- **`services/nodejs/`** — a Telegram bot (customer messaging, forwarding, relay for hidden-profile users, Integrately webhook) and a cache warmer that pre-warms the site's sitemap URLs and reports cache/status stats. Deployed on Sevalla.
- **`services/python/`** — placeholder for future AI/NLP services.

## SEO/GEO skills toolkit

A set of Agent Skills (`.agents/skills/`) that produce SEO/GEO reports from the site's own data (Google Search Console, GA4, Google Ads) plus optional third-party sources. The toolkit is **deterministic** (capability registry + resolver, site profiles, coverage) and **degrades gracefully** when a source is missing. Reports target the site owner/marketer, not developers.

## Audience

- The Telegram bot serves the business's customers.
- The SEO/GEO reports serve the site owner/marketer.

---

*This file describes durable product context, not a changelog. When the product's purpose or a core subsystem's role changes, update the relevant section in place.*
