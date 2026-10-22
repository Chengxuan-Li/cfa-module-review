# CFA bilingual review skills

An agent-skills repository for English–Simplified Chinese CFA review presentations. The `cfa-bilingual-review` skill reconciles curriculum, Chinese preparation slides and Kaplan material into paired concise and expanded decks, with editable text, verified numerical examples and three-slide Letter handouts.

Each invocation produces exactly:

- `review-concise.pptx`
- `review-expanded.pptx`
- `review-concise-handout.pdf`
- `review-expanded-handout.pdf`

The expanded deck preserves every concise slide's core content and order. Equations use consistent semantic colors matched to definitions and worked calculations, with neutral operators, clearly outlined knowledge cards and visible internal dividers. Expanded slides can include an editable balance-sheet illustration whose subtotals and accounting identity are checked automatically. The handouts use three vector slide thumbnails per page with clear outer frames and corresponding explanatory notes. A final partial page contains only the remaining slides.

Reviews follow curriculum learning objectives in source order, with the current objective visible on each page. Related rules and formulas share a page when comparison helps. Knowledge statements are paired in English and Simplified Chinese. Worked examples, answers and balance-sheet labels use English; formula conditions and common mistakes use Simplified Chinese. Use `layout: "objectives"` with `language_profile: "bilingual-knowledge-english-examples"` for this format. Earlier input layouts remain supported.

## Install with npx

Requires Node.js 22.20+ for the [Vercel skills CLI](https://github.com/vercel-labs/skills). Install from the public GitHub repository into your current project:

```sh
npx skills add Chengxuan-Li/cfa-module-review --skill cfa-bilingual-review --agent codex
```

Install specifically for Codex, globally:

```sh
npx skills add Chengxuan-Li/cfa-module-review --skill cfa-bilingual-review --agent codex --global
```

List the available skill before installing, or install for another supported agent by changing `--agent`:

```sh
npx skills add Chengxuan-Li/cfa-module-review --list
```

Add `--yes` for a noninteractive installation. For local development, clone this repository and use `npx skills add . --skill cfa-bilingual-review --agent codex` from its root. `npx skills` installs the skill files, not Python packages, the private Artifact Tool runtime, fonts or presentation software. This is a Git-hosted skill; no npm package publication is needed.

## Requirements

- Python 3.11+ and the skill's `requirements.txt`.
- Node.js 22.20+ and the Codex-provided `@oai/artifact-tool` runtime. Tested with 2.8.99. This private package is **not** available through a normal `npm install`; use Codex desktop's `load_workspace_dependencies` tool to locate it.
- Windows PowerPoint, or LibreOffice with `--renderer libreoffice`.
- An installed CJK TrueType font. Defaults: Microsoft YaHei and `C:/Windows/Fonts/msyh.ttc`. Pass both font family and file when using a different font. PPTX fonts are not embedded.

```sh
python -m venv .venv
# Activate the environment using the command appropriate for your shell.
python -m pip install -r SKILL_DIR/requirements.txt
```

Replace `SKILL_DIR` with the installed skill directory printed by the installer. In a clone it is `skills/cfa-bilingual-review`; project installations normally use `.agents/skills/cfa-bilingual-review`. Codex CLI users can install and read the skill, but running the supplied generator also requires access to the compatible Artifact Tool runtime. The repository does not bundle that runtime or the reference skills.

## Invoke

```text
Use $cfa-bilingual-review for the selected Financial Statement Analysis
Learning Modules from these files: curriculum.pdf, chinese-prep.pdf,
and kaplan.docx. Use the supplied curriculum year and LOS. Create both
review decks and both Letter handouts in an ignored output directory.
```

```text
Use $cfa-bilingual-review to make a public-source Financial Statement
Analysis demo without my source books. Use original examples, identify
unverified coverage, and keep all demo work outside Git.
```

Normal mode requires the curriculum PDF (scope and LOS authority), Chinese preparation PDF (terminology and explanations), and Kaplan PDF/DOCX/RTF/pasted text (secondary detail). Select one module, several modules, or an entire book. For a whole book, inventory every module and exact learning outcome first, maintain a coverage map, and keep the slides in curriculum order. Input extraction is local; the agent must visually verify formulas, reconcile conflicts and author the intermediate concepts. Scanned PDFs need a separate OCR step. No official coverage is inferred from absent sources.

See [source handling](skills/cfa-bilingual-review/references/sources.md) and the [concept contract](skills/cfa-bilingual-review/references/concept-format.md). Start new concept records from the [bilingual objective fixture](skills/cfa-bilingual-review/assets/objectives-concepts.json). The [legacy fixture](skills/cfa-bilingual-review/assets/minimal-concepts.json) remains for compatibility. Both contain invented arithmetic only, with no curriculum coverage claimed.

## Run the generator directly

After preparing private concept JSON, set `ARTIFACT_TOOL_MODULE` to the runtime's `@oai/artifact-tool/dist/artifact_tool.mjs`, then run:

```sh
python SKILL_DIR/scripts/pipeline.py inputs/concepts.json --out output/run-01 --work build/run-01
```

Use `--node`, `--artifact-module`, `--renderer`, `--soffice`, `--font-file`, and `--font-family` to customize dependencies. Both destination directories must be fresh and separate. Source hierarchy, formulas, notes and examples are controlled by JSON; colors by `assets/theme.json`; layout slots by `make_plan()` in the pipeline. Read [generation and troubleshooting](skills/cfa-bilingual-review/references/generation.md) before changing the grid.

## Repository structure

```text
skills/cfa-bilingual-review/
  SKILL.md                 Discoverable workflow
  agents/openai.yaml       Codex display metadata
  assets/                  Theme and tiny synthetic format fixture
  references/              Source rules, concept contract, generation guide
  scripts/                 Extraction, validation, authoring, rendering, handouts
  requirements.txt         Python dependencies
  package.json             Node engine/runtime information
tests/                     Synthetic regression tests
docs/                      Provenance and engineering decisions
demo/                      Local demonstration only; ignored
```

All source PDFs, Word/RTF inputs, generated PPTX/PDF/images, demo work, caches and local environments are ignored. Put pasted source text and concept JSON under `inputs/`, `sources/`, `demo/` or `.work/`, which are ignored as directories. Arbitrary `.txt`/`.json` files elsewhere are not blanket ignored because the skill uses reusable JSON assets. Never force-add private material.

## Validation

```sh
python -m unittest discover -s tests -v
npx skills add . --list
```

The pipeline checks arithmetic, required roles, traceable references, glyph coverage, font-sized text capacity, PowerPoint package integrity, slide correspondence, concise-content preservation, notes, native rendering and handout geometry/order. It writes private `validation.json` and PNGs. Inspect every slide and every handout page before delivery. Automated success is not a visual or curriculum accuracy guarantee.

The current layout was exercised on the supplied 2026 Level I Financial Statement Analysis book: 12 modules and 53 learning outcomes, producing two 133-slide decks and two 45-page handouts. That private run, source books, extraction, examples and QA evidence remain under ignored `demo/` and are not distributed. These counts describe that run; the skill derives scope and page count from each user's selected curriculum. Installation alone does not supply CFA study content.

## Limits and reuse

This version supports compact text/formula concepts and numeric or qualitative examples. Equations are editable linear Unicode text, not Office Math/LaTeX. Large tables and complex derivations require extending the renderer or splitting concepts. Qualitative example validity requires source review, rather than arithmetic checks. Three-up print thumbnails necessarily reduce type size; notes remain 9.5 pt. Rendering and fonts can vary across computers. LibreOffice support requires local validation on the deployment platform.

The reference repository was read only. Its implementation was not copied because no reuse license was found; see [design provenance](docs/design-provenance.md). Proprietary preparation content is not included. No repository redistribution license has been selected. CFA Institute has not endorsed this project.
