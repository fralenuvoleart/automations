# Action history — pbservices.ge

Append-only log. Each entry is `- **YYYY-MM-DD** [recommended|done] <action>`.
- `[done]` = the action was actually carried out (confirmed by the user). Skills
  never re-recommend a `[done]` action.
- `[recommended]` = a skill proposed it; skills mention it as "previously
  recommended, still open" instead of presenting it as new.
Write with `python3 seo/site_profile.py --site pbservices.ge --append-history "<action>" --status done|recommended`.
