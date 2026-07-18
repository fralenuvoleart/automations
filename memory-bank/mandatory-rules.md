# Mandatory Operational Rules — BOTS Workspace

## 🧠 MEMORY & PERSISTENCE
- **Context Synchronization:** You MUST read the `/memory-bank` directory before every task. Use it as the primary source of truth over your general training data.
- **Auto-Update Protocol:** Update `activeContext.md` and `progress.md` after every significant change without being prompted.
- **Deep Scan Initialization:** If no `memory-bank/` exists, you must offer to initialize it by scanning `docs/` and the codebase to preserve legacy architectural decisions.
- **MCP Memory:** The global knowledge graph (`mcp--memory--*`) is for cross-file plugin facts only, not for bot state.

## 🔍 ANALYSIS & REASONING
- **Problem "Why":** Identify the underlying problem before proposing code. Do not rely solely on comments or assumptions.
- **Chain of Thought:** Before writing code, explicitly state which `systemPatterns.md` rule you are following.
- **Evidence:** All feedback and suggestions must include specific file/line references.
- **Verification via Ripgrep:** Before asserting that a pattern is followed or a regression is avoided, you MUST use `grep` or `ripgrep` to search the codebase for conflicting logic or existing implementations. Never rely on your internal "guess" of the file structure.

## 🛠️ DEVELOPMENT & QUALITY
- **Zero Regression Policy:** This is production code. Check `systemPatterns.md` before every file write to ensure zero violations of established architecture.
- **Design Principles:** Prioritize KISS, Modularity, Performance.
- **Concise Comments:** Docblocks and inline comments must be short and to the point — state what/why in 1-2 lines. No multi-paragraph rationale essays inside code comments; longer design rationale belongs in `systemPatterns.md`, not the file itself.

## 🛑 ABSOLUTE CONSTRAINTS (ANTI-HALLUCINATION)
- **Honesty Protocol:** Failing to follow directives, making up "best practices," or presenting opinions as facts is **LYING**.
- **The "I Don't Know" Rule:** If context is missing or you are unsure, say "I don't know" rather than hallucinating.
- **No Placeholders:** Never use `// ... rest of code here`. Provide complete, functional snippets or targeted diffs.

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
