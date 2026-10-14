# Concept contract, version 1

The executable contract is `validate()` in `scripts/pipeline.py`. `assets/minimal-concepts.json` is a small copyright-free example. Use UTF-8 JSON. The root has:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `mode` | `curriculum` requires curriculum, chinese and kaplan sources; `public-demo` is explicitly limited |
| `title`, `scope` | Human title and honest coverage statement |
| `curriculum_year`, `level` | Verified scope or an explicit unverified/demo label |
| `sources` | Unique `id`, `role`, `title`, `location`; add `edition` and `retrieved` where useful |
| `issues` | Source conflicts with resolution and evidence; unresolved items stop the build |
| `concepts` | Ordered list described below |

Every concept requires nonempty strings: `id`, `module`, `los`, `term_en`, `term_zh`, `summary_en`, `summary_zh`, `formula`, `variables`, `conditions`, `trap`, `expanded`, `notes`, `expanded_notes`. Use a short explicit "Not applicable" for a truly inapplicable field; do not invent a formula for a qualitative concept. Qualitative examples set `kind: "qualitative"` and may use empty `checks`; verify their scenario and explanation against cited sources. Numeric examples use `kind: "numeric"` (the default) and require checks.

`references` is a nonempty array of `{source, locator}`. Source IDs must resolve. `example` contains `origin` (`original` or `source`), `prompt`, `solution`, `interpretation`, and `checks`. Sourced examples additionally require `reference: {source, locator}`.

Each check contains `expression`, numeric `inputs`, numeric `expected`, and `display` (the result token appearing in the solution). Optional absolute `tolerance` defaults to `1e-8` and cannot exceed `0.01`. Expressions allow numeric constants, variables, parentheses, `+ - * / **`; no functions, attributes or code. Check ALL displayed calculations. Percentages are normally stored as fractions: expected `0.15` with display `15%`. The agent must verify that display formatting and formula semantics match the calculation.

The concise fields are reused verbatim in expanded slides. Expanded notes append to concise notes. Full references, scope, module and LOS are stored in speaker notes. Handouts use the explanatory note subset, preserving the concept ID next to the thumbnail. This avoids URLs crowding the handouts.

Content budgets are layout-dependent, not arbitrary word limits. The two-column expanded deck is the tighter constraint: approximately three lines of English definition, two lines of Chinese, two formula lines, two variable lines, two condition lines, two trap lines. Additions allow four explanation lines, three example lines, two solution lines and two interpretation lines. Font metrics enforce fit and reject overflow. Split a concept in both decks instead of dropping concise content.
