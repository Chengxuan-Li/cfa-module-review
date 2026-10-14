# Source reconciliation

Normal input roles:

| Role | Authority and treatment |
| --- | --- |
| `curriculum` | Requested exam year and level; governs module scope, LOS, definitions and requirements. |
| `chinese` | Terminology and explanatory reference; never silently overrides curriculum. |
| `kaplan` | Secondary explanations, worked examples and exam interpretation. |
| `public` | Supplemental public evidence or explicitly authorized demonstration. |

Record title, edition/year, local private path or URL, and exact PDF page or section. Distinguish PDF page index from printed page number. For public sources, record retrieval date. Do not conflate accounting rules for different periods or IFRS and US GAAP. Reconcile differences using the requested curriculum, then the relevant standard setter's primary source. Keep unresolved conflicts out of slides.

Extraction manifest example (store under ignored `inputs/`):

```json
[
  {"id":"CFA","role":"curriculum","path":"curriculum.pdf"},
  {"id":"CN","role":"chinese","path":"chinese-slides.pdf"},
  {"id":"KAP","role":"kaplan","path":"kaplan.docx"}
]
```

```sh
python SKILL_DIR/scripts/extract_inputs.py inputs/manifest.json --out .work/extracted.json
```

DOCX extraction includes table paragraphs but does not preserve table geometry or Office Math. RTF needs `striprtf`; paste text into a UTF-8 `.txt` file. Legacy `.doc` must first be converted by Word or LibreOffice. Scanned PDFs are flagged, not automatically OCRed. The agent must inspect rendered source pages and transcribe/verify equations. Extraction never sends material to an external service.

Before building, prepare an LOS coverage map: requested LOS, concept IDs covering them, omissions and reason. `los` fields preserve the supplied identifiers and a short paraphrase. Avoid extensive copying of curriculum prose or preparation questions. Original examples should use fictitious values and be labeled. This skill does not grant redistribution rights to supplied materials.

Issues use `{ "status": "resolved", "claim": "...", "resolution": "...", "evidence": "..." }`. Missing inputs, ambiguous formulas, and uncertain scope remain visible in the private source record even when the related claims are omitted. Do not turn omitted claims into purportedly verified coverage.
