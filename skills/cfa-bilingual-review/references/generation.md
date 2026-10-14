# Generation and QA

## Dependencies

Python 3.11+ with `pip install -r SKILL_DIR/requirements.txt`; Node 22+; Codex's bundled `@oai/artifact-tool` (tested with 2.8.93); and a native presentation renderer. The package is private and is not installed through npm. In Codex desktop call `load_workspace_dependencies` and locate `@oai/artifact-tool/dist/artifact_tool.mjs` under the returned Node packages directory. Supply its path with `--artifact-module` or `ARTIFACT_TOOL_MODULE`. Outside that environment an authorized compatible artifact-tool runtime is required; installation of the skill alone does not provide it.

Windows: Microsoft PowerPoint automation, accessed read-only without a visible document window. macOS/Linux: install LibreOffice, select `--renderer libreoffice`, and supply `--soffice` if it is not on PATH. LibreOffice is an implemented alternative but the initial demonstration was validated with PowerPoint. Font substitution and rendering can differ between applications.

Use a legally installed CJK TrueType font. Default Windows settings are Microsoft YaHei at `C:/Windows/Fonts/msyh.ttc`. For other systems pass both `--font-file` and `--font-family`, ensuring the family is actually installed. CFF-only OTF fonts may not work in ReportLab; choose a TrueType alternative. Fonts are not embedded in PPTX and are never redistributed by this repository. PDF notes embed a subset of the selected font when permitted by the font; respect its license.

## Command

```sh
python SKILL_DIR/scripts/pipeline.py inputs/concepts.json \
  --out output/run-01 --work build/run-01 \
  --node /path/to/node \
  --artifact-module /path/to/@oai/artifact-tool/dist/artifact_tool.mjs \
  --font-file /path/to/installed-cjk.ttf --font-family "Installed CJK Family" \
  --renderer libreoffice
```

Use normal PowerShell backticks or a single line on Windows. Both directories must be fresh and separate; the command will not overwrite an existing run. The final directory contains exactly the four requested files. The work directory contains drafts, renderings, a layout plan and `validation.json`. The pipeline publishes only after both variants pass automated checks. Visual approval remains a separate human/agent review.

## Layout and editability

`assets/theme.json` contains color and font defaults. `make_plan()` owns fixed 1280×720 geometry and the content slots. Changes to the grid must be accompanied by regenerated visual checks and updates to handout assumptions if the aspect ratio changes. CLI font settings override the default family. Body text is 24 CSS pixels (18 pt), equations 28 pixels, English titles 38 pixels. All slide content is native editable text, including Unicode linear equations. This version does not author native Office Math fractions, matrices or LaTeX; use explicit parentheses and simple notation, or extend the authoring script for complex equations. Do not substitute raster text.

Handouts use US Letter portrait, 30 pt horizontal margins, three 238 pt rows, 396×222.75 pt vector thumbnails, and a 144 pt notes column at 9.5 pt. Final pages contain the remaining one or two slides without duplicates or filler. Main slide text scales to approximately 7.4 pt on paper: use a full-slide view for projection and the paired notes for print study. Never squeeze a fourth slide onto a page. Long notes fail clearly.

## Validation boundaries

Automated checks cover arithmetic, source IDs, required input roles, unique concepts, glyph availability in the selected font file, text capacity, editable text preservation, XML/ZIP integrity, slide count, concept order, notes, off-slide geometry, renderer output, Letter size, pagination, thumbnail IDs and note placement. PowerPoint additionally checks actual text bounds. Rendering every slide verifies that the native application opens the package.

Every rendered PNG and every handout page still needs visual inspection. Neither XML checks nor font metrics prove factual accuracy, correct official LOS mapping, typography under another renderer, absence of all visual overlaps, or reliable OCR. Check formula semantics and every example independently. Record visual review separately from automated results, including what was inspected and any fixes.

Troubleshooting: missing module → locate Codex runtime; missing renderer → install PowerPoint/LibreOffice; absent CJK glyphs → select an installed complete font; capacity/notes overflow → split both variants or shorten notes; absent PDF text → check renderer fonts; source conflict → resolve using the requested curriculum. Never mark a partially failed run complete.
