---
description: "Extract exhaustive verbatim answer snippets for Questions & Objectives from companion text into findings payload."
---

# /snipper-snip Workflow

Execute semantic answer snippet and evidence discovery on a document entry, extracting verbatim snippets for Questions (`Q#`) and Objectives (`O#`) into `<name>.findings.json`.

**Input**: Path to target `<name>.docx` (or `<name>.txt`).
Optional: `--q <path/to/questions.txt>`, `--out <path/to/findings.json>`.

---

## Steps

### 1. Ingestion & Companion Text Setup
1. Identify the target document `<name>.docx`.
2. Ensure `<name>.txt` companion file exists with spatial paragraph coordinates `[P#]`. If missing, generate it:
   ```bash
   python .agents/skills/snipper/scripts/cli.py dump "<path/to/document.docx>"
   ```
3. Locate `<name>.questions.txt` (or `--q <path>`). Parse all Questions (`Q#`) and Objectives (`O#`) with `- Keywords:` and `- Concepts:` sub-bullets.

### 2. Concept Disambiguation (if applicable)
1. For any concept marked `(web: true)`:
   - Search the web for authoritative definitions.
   - If multiple definitions exist, interactively prompt the user with candidates.
   - Record approved URL and definition.

### 3. Exhaustive Evidence Extraction (100% Full-Text Scan)
1. Read the lightweight `<name>.txt` companion file via `view_file`.
2. Extract **all** verbatim sentences or paragraphs containing answering context for each question and objective.
3. Invariants:
   - Comprehensive multi-snippet coverage is required (`C-EXE-04`). Do not stop early.
   - Never copy `[P#]` markers into `snippet_text` (`C-TXT-02`).
   - Verbatim character-for-character matching with source body.

### 4. Keywords Determination & Payload Emission
1. Validate user-specified `- Keywords:` or deduce essential keywords from context (`C-EXE-05`).
2. Format the findings payload conforming to `references/findings.schema.json` using string `target_ids: ["Q1", "O1"]`.
3. Save to `<name>.findings.json`.
