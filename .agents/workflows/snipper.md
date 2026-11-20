---
description: "Execute Snipper v0.4 workflows on Word documents: extract answer snippets (/snipper:snip), mutate documents in-place (/snipper:hlt), or query scoped findings (/snipper:lookup)."
---

# /snipper Workflow (v0.4)

Execute the decoupled Snipper v0.4 pipeline: extract semantic answer snippets for Questions & Objectives, mutate Word documents in-place with idempotent summary blocks and highlights, or perform scoped evidence retrieval across findings files.

**Subcommands**:
- `/snipper snip <path/to/doc.docx>`: Answer & Evidence Extraction (generates `<name>.findings.json`)
- `/snipper hlt <path/to/doc.docx>`: Idempotent In-Place Document Highlighter (mutates `<name>.docx`)
- `/snipper lookup "<query>" [--dir <path>] [--scope local|hierarchical|global] [--limit N]`: Scoped Findings Retrieval

---

## Workflow 1: Answer & Evidence Extraction (`/snipper snip`)

### 1. Ingestion & Companion Text Setup
1. Identify the target `<name>.docx` file.
2. Ensure `<name>.txt` companion exists with paragraph coordinates `[P#]`. If missing or out of date:
   ```bash
   python .agents/skills/snipper/scripts/cli.py dump "<path/to/document.docx>"
   ```
3. Locate `<name>.questions.txt` (or explicit `--q <path>`).
   - If user provided a legacy single document with embedded `Questions:` / `Body:`, parse both sections directly.
   - Parse all Questions (`Q#`) and Objectives (`O#`) along with `- Keywords:` and `- Concepts:` sub-bullets.

### 2. Concept Resolution & Interactive Disambiguation
1. For each concept marked with `(web: true)`:
   - Search the web for authoritative definitions.
   - If multiple candidates exist, interactively prompt the user:
     ```
     Found candidate sources for concept '<Concept Name>':
     1. [Source 1](url1) - Summary
     2. [Source 2](url2) - Summary
     Which source would you like to approve?
     ```
   - Record approved source URLs and definitions.

### 3. Exhaustive Multi-Snippet Gathering (Agent Protocol)
1. Read the lightweight `<name>.txt` companion file via `view_file` (100% full-text scan).
2. For each question (`Q#`) and objective (`O#`), extract **all** verbatim sentences or paragraphs containing factual evidence.
3. **Mandatory Invariants**:
   - Comprehensive multi-snippet coverage is required across the full document text (`C-EXE-04`). Do NOT stop after a single sentence.
   - Do NOT copy `[P#]` spatial markers into `snippet_text`. Text in `snippet_text` must match the source document character-for-character (`C-TXT-02`).
   - Do NOT interpret, extrapolate, or generate synthetic commentary (`C-TXT-03`).

### 4. Keywords Determination & Findings Emission
1. For each target:
   - If `- Keywords:` sub-bullets exist, validate and retain them.
   - If omitted, deduce essential keywords from context (`C-EXE-05`).
2. Format findings payload conforming to `references/findings.schema.json` using string `target_ids: ["Q1", "O1"]`.
3. Save payload to `<name>.findings.json` (or specified `--out`).

---

## Workflow 2: Document Highlighter & In-Place Mutation (`/snipper hlt`)

### 1. Pre-Mutation Verification
1. Ensure the target `.docx` is not locked by Microsoft Word.
2. Verify that `<name>.txt` companion exists as the ground-truth text backup (`C-DOC-04`). Duplicate `.backup.docx` creation is eliminated.

### 2. Execute Idempotent Mutation
1. Run the highlighter CLI:
   ```bash
   python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx>"
   # or with explicit findings:
   python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx>" --f "<path/to/findings.json>"
   ```
2. What the mutator executes:
   - Identifies and strips any existing summary block between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`.
   - Clears existing highlight and bold styling from body paragraphs.
   - Prepends fresh summary block at paragraph 0 detailing target questions, objectives, bullet-point keywords, concept definitions, sources, and spaced quoted snippets with superscript citations (`Q¹`, `O¹`) — without `Snippet:` prefix markers.
   - Highlights keywords across the body text in the target's assigned color; bolds keywords inside answering snippet spans.
   - Saves mutated document in-place.

---

## Workflow 3: Scoped Evidence Retrieval (`/snipper lookup`)

### 1. Define Scope Boundary
- `--scope local` (default): Scopes directory subtree rooted at `--dir`. If `--dir` is a Module, includes all child sub-modules. If `--dir` is a Sub-module, includes only that sub-module. Never ascends.
- `--scope hierarchical`: Scopes local subtree and ascends upward to inherit ancestor keywords (`module.keywords.txt`, `library.keywords.txt`, etc.).
- `--scope global`: Searches across all modules and sub-modules in the library.

### 2. Execute Lookup
```bash
# Targeted search with lexical ranking capped at top N:
python .agents/skills/snipper/scripts/cli.py lookup "<query>" --dir "<path>" --scope local --limit 5

# Comprehensive search evaluating all scoped findings via LLM agent:
python .agents/skills/snipper/scripts/cli.py lookup "<query>" --dir "<path>" --scope local
```

### 3. Display Results
Snippet cards are presented with spatial coordinates (`[P#]`), target IDs, matched keywords, and relative document paths.
