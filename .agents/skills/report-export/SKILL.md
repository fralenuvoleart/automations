---
name: report-export
description: Render a Markdown report to PDF and optionally email it — the shared delivery step for any report-producing skill (SEO reports, Kinsta log reports). Use when asked to "export report as PDF", "email the report", "send the report", or after generating a report that needs delivery.
license: MIT
compatibility: Python 3.8+. PDF via npx md-to-pdf (Chromium) with a WeasyPrint fallback. Email via SMTP. No MCP server required.
---

# Report Export

> **Mechanical steps** (rendering, attachment, sending) must be followed exactly; **analytical steps** (subject/summary wording) use judgment within the guardrails in [`references/delivery.md`](references/delivery.md).

## Scope & Audience
- **Scope**: turn a finished Markdown report into a PDF and/or email it. Does not generate or edit report content. Does not read or write `memory-bank/`.
- **Audience**: the report author/operator — a delivery step, not an analysis.

## Report Audience & Purpose
- **Audience**: whoever receives the report (management, client, owner).
- **Purpose**: deliver the already-validated report unchanged — never rewrite its content.

## Memory-Bank Isolation
This skill is a standalone delivery tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md).

## When to Use
- "export report as PDF", "make a PDF of the report"
- "email the report", "send the report"
- As the final step after any report-producing skill (SEO reports, `kinsta-logs`)

## When NOT to Use
- The report is not yet generated/validated (run the producing skill first)
- Converting a *webpage* to PDF (use `web-to-pdf`)

## Requires
- Python 3.8+.
- A PDF engine: **npx + Chromium** (primary, `md-to-pdf`) or **WeasyPrint** (fallback). Override the browser with `CHROMIUM_BIN`.
- For email: SMTP credentials in `~/.config/report-export/email.json`.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Markdown → PDF | [`scripts/export_pdf.py`](scripts/export_pdf.py) | available |
| Email with attachment | [`scripts/send_email.py`](scripts/send_email.py) | available (needs SMTP creds) |
| Stylesheet | [`scripts/report.css`](scripts/report.css) | available |

## Workflow
1. **Locate the report.** The producing skill prints the Markdown path (e.g. `{run_dir}/report.md` or `~/Downloads/kinsta-logs/reports/report_*.md`). Use that exact path.
2. **Export PDF.**
   ```bash
   python3 .agents/skills/report-export/scripts/export_pdf.py \
     --md "$REPORT_PATH" --out "${REPORT_PATH%.md}.pdf" --title "Report"
   ```
   Engine order: `npx md-to-pdf` (Chromium) → WeasyPrint → Chromium. Override the browser with `CHROMIUM_BIN`.
3. **Email (user-initiated only).** Ask the user before sending. If yes:
   ```bash
   python3 .agents/skills/report-export/scripts/send_email.py \
     --attachment "${REPORT_PATH%.md}.pdf" --skill <calling-skill>
   ```
   **One config** ([`config/email.json`](config/email.json)) holds the recipients and a `subjects` map; `--skill <name>` picks the subject, `--subject`/`--to` override. SMTP credentials from `~/.config/report-export/email.json`. Add `--dry-run` to verify login + recipients without sending.
4. **Report the output paths** (PDF, and "emailed to …" if sent).

## Determinism
- The Markdown → HTML step is a pure function; the PDF is a deterministic render of the input Markdown + CSS.
- Never edit the report content during export — deliver it byte-for-byte.

## Output
The PDF path (and, if emailed, the recipient list). No report content is produced or changed.

## Fallbacks
- If WeasyPrint is unavailable, use Chromium; if neither is available, state it and leave the Markdown as the deliverable (it is valid on its own).
- If SMTP credentials are missing, state it and skip email — never fail the whole run.

## Pending Data Sources
- None. This skill has no external data dependency beyond the local PDF engine and SMTP.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `no PDF engine available` | no npx/Chromium and no WeasyPrint | install Chromium (or set `CHROMIUM_BIN`) or `pip install weasyprint` |
| PDF export fails/skipped | Chromium missing or npx/network unavailable | set `CHROMIUM_BIN`; the Markdown is still valid |
| Email not sent | missing `~/.config/report-export/email.json` | copy [`config/email.json.example`](config/email.json.example) and fill credentials |
| Attachment missing | PDF not generated first | run step 2 before step 3 |

## Files

| File | Purpose | Action |
|---|---|---|
| [`scripts/export_pdf.py`](scripts/export_pdf.py) | Markdown → PDF (WeasyPrint default, Chromium fallback) | Execute |
| [`scripts/send_email.py`](scripts/send_email.py) | Email the PDF via SMTP | Execute (user-initiated) |
| [`scripts/report.css`](scripts/report.css) | Report stylesheet | Used automatically |
| [`config/email.json`](config/email.json) | Non-sensitive email fields (recipients, subject, signature) | Edit |
| [`config/email.json.example`](config/email.json.example) | Template for `~/.config/report-export/email.json` (SMTP creds) | Copy + fill |
| [`references/delivery.md`](references/delivery.md) | Delivery conventions (subject/summary wording) | Read |
| [`tests/test_export_pdf.py`](tests/test_export_pdf.py) | Tests for the pure Markdown → HTML step | Execute after changes |
| [`tests/test_send_email.py`](tests/test_send_email.py) | Tests for subject resolution (one config, per-skill subjects) | Execute after changes |

## Related / Delegation
- Producing skills delegate here as their final step: the SEO skills (`seo-audit`, …) and `kinsta-logs`.
- Webpage → PDF (not a report) → run `web-to-pdf`.

## Configuration
- **One config**: [`config/email.json`](config/email.json) (version-controlled) — `from_email`, `to_emails`, `body_signature`, a default `subject`, and a `subjects` map (per-skill subjects).
- `--skill <name>` selects the subject from `subjects`; `--subject` overrides it; `--to` overrides recipients.
- SMTP credentials: `~/.config/report-export/email.json` (not version-controlled) — `smtp_host`, `smtp_port`, `username`, `password`.
- PDF engine override: `CHROMIUM_BIN` env var.

## Privacy & Retention
- The PDF embeds the report's content (which may contain the site's data or visitor IPs) — treat it like the source report.
- Email sends the PDF to the configured recipients; no other data leaves the machine.

## Output Structure
```
<report_dir>/
  report.md          # input (from the producing skill)
  report.pdf         # output (this skill)
```
