# Delivery Conventions

Guidance for the `report-export` skill. Mechanical steps (render, attach, send)
are fixed; the wording below is judgment.

## Subject line
- Include the subject and the period: `"<Subject> — <window>"` (e.g. `"SEO Audit — 2026-08-01→2026-10-27"`).
- Keep it under ~80 characters.

## Body
- One or two sentences: what the report covers and the single most important finding.
- Do not paste the whole report into the email body — the PDF is the deliverable.

## Recipients
- Default to `config/email.json` → `to_emails`.
- Only override with `--to` when the user explicitly names recipients.

## Never
- Never edit the report content during export.
- Never send without the user's confirmation.
- Never attach a report that failed its producing skill's validation step.
