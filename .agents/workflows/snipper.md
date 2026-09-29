---
description: "Execute the Snipper pipeline on a Word document: resolve concepts, discover verbatim answer snippets, determine keywords, and mutate the document in-place."
---

# /snipper Workflow

Execute semantic answer snippet discovery, concept resolution, keyword determination, and in-place document mutation on a Word document (`.docx`).

**Input**: Path to a target `.docx` file (e.g., `/snipper "Gerenciamento de Acesso do Postgresql.docx"`). If omitted, prompt the user for the document path or check active editor files.

---

## Steps

### 0. Mandatory Prerequisites & Constraints Ingestion
1. Read the normative skill specifications:
   - [SKILL.md](file:///c:/Dev/Highliter/.agents/skills/snipper/SKILL.md) (or [test-skill-directory/SKILL.md](file:///c:/Dev/Highliter/test-skill-directory/SKILL.md)): Core sequential protocol, RFC 2119 constraints, and interactive procedures.
   - `references/CustomConstraints.md`: Runtime parameters and language configuration.
   - `references/Definitions.md`: Entity taxonomy, overlap rules, and mutation model.
   - `assets/palette.md`: Active 15-color hex palette.
   - `references/findings.schema.json`: Formal findings payload schema.
2. Verify that the active color palette and configuration defined in `CustomConstraints.md` and `palette.md` are loaded and enforced during pipeline execution.

### 1. Document Ingestion, Backup & Section Parsing
1. Identify the target `.docx` file. Ensure the file is not currently locked by Microsoft Word.
2. **Duplicate & Conserve Backup**: Prior to mutation, ensure a duplicate copy of the target document is conserved (e.g. `<filename>.backup.docx` or in `Docs Backup/`) so that an untouched original is preserved.
3. Ingest the document using `DocumentParser`:
   - Identify `Questions` and `Body` boundaries.
   - Parse questions and any sub-bullet metadata:
     - `- Keywords: <comma-separated terms>`
     - `- Concepts: <concept name> [(web: true)]`
   - Generate/sync the lightweight text companion `<filename>.snipper.txt` via:
     ```bash
     python .agents/skills/snipper/scripts/cli.py dump "<path/to/document.docx>"
     ```

### 2. Stage 1: Concept Resolution & Interactive Source Selection
1. For each concept associated with a question:
   - **Internal Concept**: If `web_search == False`, extract factual definitions directly from the document `Body`.
   - **External Concept (web: true)**:
     - Search the web for clear, authoritative definitions.
     - **Interactively prompt the user** using `ask_question`:
       ```
       Found candidate sources for concept '<Concept Name>':
       1. [Source 1](url1) - Summary
       2. [Source 2](url2) - Summary
       Which source would you like to approve?
       ```
     - Record the approved `source_url` and final `definition`.

### 3. Stage 2: Answers & Exhaustive Multi-Snippet Gathering
1. Read the lightweight `<filename>.snipper.txt` companion file via `view_file` (100% full-text scan).
2. For each question, extract **all** verbatim sentences or paragraphs containing factual evidence.
3. **Mandatory Invariant**: Do NOT stop after a single sentence or clause. Comprehensive multi-snippet coverage is required across the full document text (`C-EXE-04`).
4. **Paragraph Markers (`[P#]`)**: Do NOT copy `[P#]` markers into `snippet_text`. Text in `snippet_text` must match the source document character-for-character (`C-TXT-02`).

### 4. Stage 3: Keywords Determination
1. For each question:
   - If the user provided `- Keywords:` sub-bullets, use and validate them.
   - If omitted by the user, **deduce the essential keywords** required to answer each question from context (`C-EXE-05`).
2. Format the findings payload conforming to `references/findings.schema.json` and save to a temporary findings JSON file (e.g. `findings_<doc_slug>.json`).

### 5. Stage 4: Highlighter & Document Mutation
1. Execute the document mutation:
   ```bash
   python .agents/skills/snipper/scripts/cli.py run "<path/to/document.docx>" --findings "<path/to/findings.json>"
   ```
2. Verify the document was mutated in-place and backup conserved:
   - Backup copy `<filename>.backup.docx` exists and is intact (`C-DOC-04`).
   - Summary block inserted before `Body` detailing questions, keywords, concept definitions, sources, and snippets with superscript citations.
   - Keywords highlighted across the body text with question colors, and bolded inside answering snippets.
3. Report completion to the user with a summary of answered questions, resolved concepts, and generated findings.
