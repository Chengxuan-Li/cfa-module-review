# Design and engineering decisions

The user designated `C:\github\Energy-Atlas\dev-skills` read-only. The technical-pptx-design entry point, layout and QA references, and Python helper/auditor scripts were inspected. No LICENSE or COPYING file was found among tracked files during the initial review (2026-10-14). The reference has not been modified, vendored, linked as a runtime dependency, or added as a submodule. No reference source code or template files were copied.

The independently implemented design follows its general academic conventions: white widescreen canvas, consistent margins, minimal accent color, editable text, equations with nearby definitions, and visual inspection of every slide. CFA-specific adaptations add paired bilingual definitions, stable concept identifiers, an example column, source-rich speaker notes, and dedicated three-up print pages. Microsoft YaHei replaces the reference's default Calibri to cover Simplified Chinese consistently.

Architecture: extracted private evidence → agent-authored validated concept JSON → deterministic layout plan → Artifact Tool editable PPTX → native application rendering → vector handout imposition with shared notes. Both decks are created from the same concept list. Concise text is not independently regenerated for the expanded version. Large concepts must split in both variants.

Python handles validation, font measurement, PDF imposition and tests. JavaScript performs PowerPoint authoring. A small PowerShell adapter renders read-only through PowerPoint. LibreOffice is an alternative renderer. ReportLab supplies real PDF note text and PyMuPDF imports vector slide pages. Input synthesis remains an agent task: the code does not claim to infer authoritative LOS or reconcile accounting conflicts automatically.

The artifact-tool runtime is supplied externally by Codex, not redistributed. This is a deliberate deployment constraint documented in the README. All implementation files here were newly written. No open-source license for this repository is asserted on the user's behalf; select a repository license before public redistribution.
