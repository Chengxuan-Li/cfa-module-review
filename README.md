# CFA bilingual review skills

An agent-skills repository for English–Simplified Chinese CFA review presentations. The `cfa-bilingual-review` skill reconciles curriculum, Chinese preparation slides and Kaplan material into paired concise and expanded decks, with editable text, verified numerical examples and three-slide Letter handouts.

Each invocation produces exactly:

- `review-concise.pptx`
- `review-expanded.pptx`
- `review-concise-handout.pdf`
- `review-expanded-handout.pdf`

The expanded deck preserves every concise slide's core content and order. Equations use consistent semantic colors matched to definitions and worked calculations, with neutral operators and clear section rules. Expanded slides can include an editable balance-sheet illustration whose subtotals and accounting identity are checked automatically. The handouts use three vector slide thumbnails per page with corresponding explanatory notes. A final partial page contains only the remaining slides.

## Install with npx

Node.js 22+ is recommended. From this repository, discover or install the skill using the [official skills CLI](https://github.com/vercel-labs/skills):

```sh
npx skills add . --list
npx skills add . --skill cfa-bilingual-review
```

Install specifically for Codex, globally:

```sh
npx skills add . --skill cfa-bilingual-review --agent codex --global
```

For a project installation, run from the target project and pass the repository's absolute path:

```powershell
npx skills add C:/github/cfa-module-review --skill cfa-bilingual-review --agent codex
```

No Git remote is configured initially. These examples use the actual local repository. After publishing, substitute its real Git URL for the local path; no GitHub owner is assumed. `npx skills` installs the skill files, not Python packages or presentation software.

## Requirements

- Python 3.11+ and the skill's `requirements.txt`.
- Node.js 22+ and the Codex-provided `@oai/artifact-tool` runtime. Tested with 2.8.93. This private package is **not** available through a normal `npm install`; use Codex desktop's `load_workspace_dependencies` tool to locate it.
- Windows PowerPoint, or LibreOffice with `--renderer libreoffice`.
- An installed CJK TrueType font. Defaults: Microsoft YaHei and `C:/Windows/Fonts/msyh.ttc`. Pass both font family and file when using a different font. PPTX fonts are not embedded.

```sh
python -m venv .venv
# Activate the environment using the command appropriate for your shell.
python -m pip install -r skills/cfa-bilingual-review/requirements.txt
```

Codex CLI users can install and read the skill, but running the supplied generator also requires access to the compatible Artifact Tool runtime. The repository does not bundle that runtime or the reference skills.

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

Normal mode requires the curriculum PDF (scope and LOS authority), Chinese preparation PDF (terminology and explanations), and Kaplan DOCX/RTF/pasted text (secondary detail). One or several selected modules are supported. Input extraction is local; the agent must visually verify formulas, reconcile conflicts and author the intermediate concepts. Scanned PDFs need a separate OCR step. No official coverage is inferred from absent sources.

See [source handling](skills/cfa-bilingual-review/references/sources.md) and the [concept contract](skills/cfa-bilingual-review/references/concept-format.md). The [small synthetic fixture](skills/cfa-bilingual-review/assets/minimal-concepts.json) is a format example, not a demo book.

## Run the generator directly

After preparing private concept JSON, set `ARTIFACT_TOOL_MODULE` to the runtime's `@oai/artifact-tool/dist/artifact_tool.mjs`, then run:

```sh
python skills/cfa-bilingual-review/scripts/pipeline.py inputs/concepts.json --out output/run-01 --work build/run-01
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

The initial public-source demonstration covers ten foundational Financial Statement Analysis concepts with original examples. It is stored under ignored `demo/`; it is not distributed with the skill. Public sources include the [SEC guide](https://www.sec.gov/about/reports-publications/investorpubsbegfinstmtguide), [CFA Institute's financial analysis techniques overview](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-analysis-techniques), and OpenStax's [liquidity](https://openstax.org/books/principles-finance-2e/pages/6-3-liquidity-ratios) and [profitability](https://openstax.org/books/principles-finance-2e/pages/6-6-profitability-ratios-and-the-dupont-method) chapters. It is not a substitute for the complete book or verified exam-year LOS coverage.

## Limits and reuse

This version supports compact text/formula concepts and numeric or qualitative examples. Equations are editable linear Unicode text, not Office Math/LaTeX. Large tables and complex derivations require extending the renderer or splitting concepts. Qualitative example validity requires source review, rather than arithmetic checks. Three-up print thumbnails necessarily reduce type size; notes remain 9.5 pt. Rendering and fonts can vary across computers. LibreOffice support requires local validation on the deployment platform.

The reference repository was read only. Its implementation was not copied because no reuse license was found; see [design provenance](docs/design-provenance.md). Proprietary preparation content is not included. No repository redistribution license has been selected. CFA Institute has not endorsed this project.
