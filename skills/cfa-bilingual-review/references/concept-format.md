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

## Equation colors

Add `equation_terms` to each mathematical concept, for example:

```json
[
  {"text":"A","role":"assets","aliases":["assets","资产","900"]},
  {"text":"L","role":"liabilities","aliases":["liabilities","负债","540"]},
  {"text":"E","role":"equity","aliases":["equity","权益","360"]}
]
```

The `text` must appear in the formula. Available roles and colors are in `assets/theme.json`. Aliases are case-sensitive, longest-first and bounded for Latin words; `A` will not color the A in `Average`. Assign numeric aliases only when unambiguous within that concept. Operators remain neutral. Matching colors apply to formula text, variable definitions, example inputs and solutions. All colored text remains editable.

## Balance-sheet example

Optional `example.balance_sheet` is rendered as a native editable table in the expanded slide. Include `entity`, `date` (ISO date), `unit` (e.g. `USD m`), and up to five `rows`. Put the entity and readable reporting date in `example.prompt`. Each row has unique `id`, bilingual `label`, numeric `amount`, and semantic `role`. A subtotal additionally has `components`, a list of row IDs to sum. Root fields `assets`, `liabilities`, `equity` identify the corresponding total-row IDs. The validator checks every subtotal and the accounting identity.

This compact layout supports a header and five rows, for example current assets, noncurrent assets, total assets, liabilities, equity. Labels must fit 366 pixels at 24 px. Use a short expanded explanation (two lines), short example prompt (two lines), one solution line and one interpretation line. For a detailed statement, split it into additional concepts rather than shrink the table. State in notes that this is a simplified statement when totals replace detailed disclosures.
