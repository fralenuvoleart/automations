# System Patterns


## 🛠️ Developer Working Method
- **Standard:** Modular, elegant, SEO-performant.
- **Verification:** Trace every claim through the full call chain before asserting a pattern is followed or a regression is avoided — use `search_files`/grep, never assume from a function name or comment alone.
- **Zero Regression Policy:** Check this file before every file write to ensure changes don't violate an established architectural invariant above.

---

*This file describes durable architectural rules, not a changelog. When a pattern changes, update the entry in place.*
