# Concept contract, version 1

## Learning-objective layout (preferred)

`assets/objectives-concepts.json` is a complete synthetic starter for the preferred bilingual profile. Copy it to a private work directory and replace its invented objective, content and sources with the selected curriculum. Keep `assets/minimal-concepts.json` for legacy-format compatibility.

Use root `layout: "objectives"` with the same schema version, source roles, issues and example arithmetic contract described below. Add `learning_objectives`: an ordered list of `{id, text_en, text_zh, short_zh, source, locator}`. Store the exact curriculum wording, a Chinese translation, the short visible Chinese description and a source locator. Local IDs such as `LO1` indicate source order, not invented official codes. Every selected objective must have slides, in objective order.

Each concept requires `id`, `module`, `los`, `objective_id`, `term_en`, `term_zh`, `review_blocks`, `trap`, `notes`, `expanded_notes`, `references` and `example`. The old `summary_en`, `summary_zh`, `formula`, `variables`, `conditions` and `expanded` slots are not required in this layout. For new reviews, set root `language_profile: "bilingual-knowledge-english-examples"`. Each knowledge statement needs parallel English and Simplified Chinese text, beyond bilingual technical names.

`review_blocks` contains ordered `{label, label_en, text?, text_en?, formula?, condition?}` records for the bilingual profile. `label` is Chinese and `label_en` English; pair every Chinese `text` with its English `text_en`. Formula-only blocks need no duplicated prose. Each needs a label and text or a formula. A formula requires a Simplified Chinese `condition`, displayed immediately before it. Multiline formulas support related calculations in the same block; explain variables in `text` or another block. `equation_terms[].text` must occur in at least one block formula. Colors also match block text and examples. Example `prompt`, `solution` and `interpretation` use English only, as do balance-sheet labels. Traps and formula conditions use Simplified Chinese only; standard symbols, acronyms, entity names, digits and units remain valid. The earlier objective layout without this language profile retains its Chinese-example contract for compatibility.

The two variants preserve ALL review blocks. The bilingual profile requires `recall_en` and `recall_zh` for the concise slide’s parallel recall section; `notes` remains the Chinese handout explanation. The earlier objective layout uses `notes` as its visible recall section. The expanded version uses the same space for the example. References and full outcome wording go into speaker notes. A compact balance sheet uses a dedicated expanded layout with fewer knowledge lines; see the balance-sheet contract below.

Group formulas by the comparison they serve. A group of three asset-life formulas can share conditions and variable definitions. Keep distinct framework assumptions explicit when comparing IFRS and US GAAP. Use roughly three knowledge blocks rather than a fixed count; fit depends on the measured lines. Split an overcrowded group in both variants, retaining the objective and coverage mapping.

## Legacy layout

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

The shared concise fields are reused verbatim in expanded slides. Expanded notes append to concise notes. Full references, scope, module and LOS are stored in speaker notes. Handouts use the explanatory note subset, preserving the concept ID next to the thumbnail. This avoids URLs crowding the handouts.

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

Optional `example.balance_sheet` is rendered as a native editable table in the expanded slide. Include `entity`, `date` (ISO date), `unit` (e.g. `USD m`), and up to five `rows`. Put the entity and readable reporting date in `example.prompt`. Each row has unique `id`, `label` (English for the bilingual profile; bilingual for earlier layouts), numeric `amount`, and semantic `role`. A subtotal additionally has `components`, a list of row IDs to sum. Root fields `assets`, `liabilities`, `equity` identify the corresponding total-row IDs. The validator checks every subtotal and the accounting identity.

This compact layout supports a header and five rows, for example current assets, noncurrent assets, total assets, liabilities, equity. Labels must fit 366 pixels at 24 px. Use a short expanded explanation (two lines), short example prompt (two lines), one solution line and one interpretation line. For a detailed statement, split it into additional concepts rather than shrink the table. State in notes that this is a simplified statement when totals replace detailed disclosures.
