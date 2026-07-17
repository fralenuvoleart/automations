# Mandatory Operational Rules — BOTS Workspace

## 🛑 ABSOLUTE CONSTRAINTS (ANTI-HALLUCINATION)
- **Honesty Protocol:** Failing to follow directives, making up "best practices," or presenting opinions as facts is **LYING**.
- **The "I Don't Know" Rule:** If context is missing or you are unsure, say "I don't know" rather than hallucinating.
- **No Placeholders:** Never use `// ... rest of code here`. Provide complete, functional snippets or targeted diffs.

## 🛠️ DEVELOPMENT & QUALITY
- **Design Principles:** KISS, Modularity, Performance.
- **Concise Comments:** Docblocks and inline comments must be short — state what/why in 1-2 lines.

## 🔍 ANALYSIS & REASONING
- **Problem "Why":** Identify the underlying problem before proposing code.
- **Chain of Thought:** Before writing code, explain which design principle you are following.
- **Evidence:** All feedback must include specific file/line references.

## 🚫 OVERTHINKING GUARDRAIL
- **When user gives a direct instruction with clear intent — DO IT.** Do not over-analyze or loop.
- **If a fix causes a regression, revert immediately and report.**

## 🚫 LOOP PREVENTION (ENFORCED LIMITS)
- **switch_mode LIMIT: 1 per task.**
- **File read LIMIT: max 5 unique files per investigation.** Do not re-read files.
- **If the user says STOP or indicates frustration — deliver answer immediately with NO tool calls.**

## 🛠️ TOOL USAGE
- **`codebase_search` `path` parameter: NEVER pass `null`.** Always pass `"."` for whole-workspace searches.

## ⚖️ SELF-AUDIT PROTOCOL
- Before declaring a task finished, list each rule above and state "Pass/Fail."
- If a "Fail" is identified, correct it before the session ends.

## 🧠 MEMORY & PERSISTENCE
- **No memory-bank:** This workspace has no `memory-bank/` — do not create or reference one.
- **MCP Memory:** The global knowledge graph (`mcp--memory--*`) is for cross-file plugin facts only, not for bot state.
