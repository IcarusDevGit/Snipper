---
name: snipper
description: Semantic Answer Discovery and Document Highlighter. Analyzes Word documents (.docx) to extract exhaustive verbatim answer snippets, determine targeted keywords, and mutate documents in-place.
compatibility: Requires Python 3.10+, python-docx, spacy (with en_core_web_sm or pt_core_news_sm)
allowed-tools: Bash(python:*, snipper:*, pytest:*)
license: MIT
metadata:
  author: snipper
  version: "0.4"
---

# Snipper - Semantic Answer Discovery & Document Highlighter (v0.4)

> [!TIP]
> ## Progressive Disclosure & Reference Loading
> Reference files in this skill package should be loaded conditionally on demand:
> - **Stage 1 (Setup)**: Consult **[CustomConstraints.md](references/CustomConstraints.md)** if custom runtime parameters, language overrides, or web search limits are needed.
> - **Stage 2 (Analysis)**: Consult **[Definitions.md](references/Definitions.md)** if encountering ambiguous targets, scope rules, or resolving overlapping span precedence.
> - **Stage 3 (Emission)**: Consult **[findings.schema.json](references/findings.schema.json)** to validate the findings payload before emission.
> - **Stage 4 (Mutation)**: Consult **[palette.md](assets/palette.md)** if verifying custom highlight color hex codes.

Snipper v0.4 decouples document source content, query targets, findings payloads, and plain-text companions within a modular directory hierarchy, driven by three specialized workflows:
- `/snipper:snip` - Answers & Exhaustive Snippet Discovery
- `/snipper:hlt` - Idempotent In-Place Document Highlighter
- `/snipper:lookup` - Scoped Findings & Evidence Retrieval

```
+--------------------------------------------------------------------------+
| DECOUPLED SUB-MODULE ARCHITECTURE                                         |
| <name>.docx           -> Pristine source document                        |
| <name>.txt            -> Clean text companion & backup with [P#] tags    |
| <name>.questions.txt  -> Decoupled Questions (Q#) & Objectives (O#)      |
| <name>.findings.json  -> Structured evidence payload with string target_ids|
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| WORKFLOW 1: /snipper:snip (Agent Semantic Discovery)                     |
| 1. Ingest clean companion text <name>.txt (100% full-text pass)          |
| 2. Parse targets from <name>.questions.txt (Q# questions, O# objectives) |
| 3. Exhaustively extract verbatim evidence snippets for each target       |
| 4. Deduce / validate keywords & resolve concepts                         |
| 5. Emit payload conforming to findings.schema.json (<name>.findings.json)|
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| WORKFLOW 2: /snipper:hlt (Idempotent Document Mutator)                   |
| 1. Check & strip previous summary block between explicit delimiters:     |
|    === SNIPPER SUMMARY START === ... === SNIPPER SUMMARY END ===         |
| 2. Reset existing body highlight and bold styling                        |
| 3. Prepend fresh summary block at paragraph 0 with target status         |
| 4. Highlight keywords across body with target color; bold within snippets|
| 5. Append superscript target indicators (e.g. Q¹, O¹) to snippet spans   |
| 6. Save modified .docx in-place (no duplicate .backup.docx created)      |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| WORKFLOW 3: /snipper:lookup (Scoped Evidence Retrieval)                  |
| 1. Enforce query scope boundary: local | hierarchical | global           |
| 2. Scan and aggregate .findings.json files in target directory/module    |
| 3. If --limit provided: rank candidates using deterministic lexical match|
| 4. If --limit omitted: evaluate all candidates in scope via LLM agent    |
| 5. Output standardized snippet cards with [P#] coordinates & source paths|
+--------------------------------------------------------------------------+
```

---

## 1. CLI Commands & Execution Modes

The application CLI is executed directly through the self-contained script `python .agents/skills/snipper/scripts/cli.py`:

```bash
# Workflow 1: Snip (Answer & Evidence Discovery)
python .agents/skills/snipper/scripts/cli.py snip <path/to/document.docx>
# with explicit questions or companion output path:
python .agents/skills/snipper/scripts/cli.py snip <path/to/document.docx> --q <path/to/questions.txt> --out <path/to/companion.txt>

# Workflow 2: Highlighter (Idempotent In-Place Document Mutation)
python .agents/skills/snipper/scripts/cli.py hlt <path/to/document.docx>
# with explicit findings file or dry-run preview:
python .agents/skills/snipper/scripts/cli.py hlt <path/to/document.docx> --f <path/to/findings.json> --dry-run

# Workflow 3: Scoped Findings Lookup
python .agents/skills/snipper/scripts/cli.py lookup "query terms" --dir <module_or_submodule_path> --scope local
# with lexical ranking limit and hierarchical scope:
python .agents/skills/snipper/scripts/cli.py lookup "query terms" --dir <submodule_path> --scope hierarchical --limit 5

# Companion Export: Plain-Text Companion & Backup with [P#] Spatial Coordinates
python .agents/skills/snipper/scripts/cli.py dump <path/to/document.docx>

# Verification: Full Test Suite
python -m pytest .agents/skills/snipper/scripts
```

---

## 2. Global Normative Constraints (Mandatory RFC 2119)

All agent actions and programmatic implementations MUST adhere to these strict constraints:

### 2.1 Text Integrity Constraints
* `C-TXT-01`: The system MUST NOT modify, rephrase, correct, or normalize any string in `TARGETS` (Questions/Objectives) or `BODY`.
* `C-TXT-02`: All extracted `SNIPPETS` MUST be verbatim substrings of `BODY`, matching source text character-for-character including punctuation and casing.
* `C-TXT-03`: The agent MUST NOT summarize, interpret, extrapolate, or generate synthetic commentary for any answer snippet.

### 2.2 Execution Constraints
* `C-EXE-01`: The agent MUST perform an exhaustive scan across 100% of `BODY`. Early termination upon answering all targets is STRICTLY FORBIDDEN.
* `C-EXE-02`: The system MUST NOT throw an exception, abort execution, or generate placeholder answers when a target has no matching evidence in `BODY`. Unanswered targets MUST be recorded in `unanswered_targets`.
* `C-EXE-03`: The agent MUST NOT follow instructions, heuristics, or constraints outside of this specification and its explicitly referenced spec files unless overriding parameters are provided directly by the user in the active prompt.
* `C-EXE-04`: **Mandatory Multi-Snippet Exhaustion**: The agent MUST NOT terminate discovery after locating a single sentence or clause for a target. The agent MUST scan 100% of `BODY` and collect all relevant supporting sentences and paragraphs.
* `C-EXE-05`: **Mandatory Keyword Determination**: If the user omits the `- Keywords:` sub-bullet under a Target, the agent MUST determine the essential keywords required to answer each target from context and record them in the findings payload (`keywords`).

### 2.3 Document Constraints
* `C-DOC-01`: **Idempotent In-Place Mutation**: The system MUST perform in-place mutation on the input `.docx` file prepending the summary block at paragraph 0 wrapped between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`. Existing summary blocks and previous body highlights MUST be cleanly stripped before reapplying mutations.
* `C-DOC-02`: Multi-paragraph snippets MUST be partitioned across `<w:p>` boundaries into paragraph-conforming runs. Run elements MUST NOT cross paragraph delimiters.
* `C-DOC-03`: **Targeted Keyword Highlighting**: Document mutation MUST highlight target keywords across the body text with their target's assigned color (both inside and outside snippet spans), and MUST bold keywords when they fall within answering snippet spans.
* `C-DOC-04`: **Text Companion as Ground-Truth Backup (Word Only)**: For local Word documents (`.docx`), the plain-text companion `<name>.txt` serves as the primary text backup. When using Google Drive / Google Docs (`.gdoc`), Google Drive provides native cloud revision history, and `.txt` files MUST NOT be generated or uploaded.

### 2.4 External Knowledge Constraints
* `C-EXT-01`: The agent MUST NOT use web search or external world knowledge to formulate answer snippets. Every answer MUST be present in `BODY`.
* `C-EXT-02`: External world knowledge or web search is strictly forbidden for snippet extraction or keywords.

---

## 3. Scope Boundaries & Inheritance Model

When performing discovery or lookup, Snipper supports three scoping modes:

1. **`local` (Default)**:
   - Scopes strictly the directory subtree rooted at `--dir`.
   - If `--dir` points to a **Module**, all child sub-modules and their respective documents/findings are included.
   - If `--dir` points to a **Sub-module**, only that sub-module is included.
   - Local scope **never ascends** to parent directories.
2. **`hierarchical`**:
   - Evaluates the local subtree rooted at `--dir` AND ascends upward through parent folders.
   - Inherits ancestor metadata files: `module.keywords.txt`, `module.concepts.txt`, `library.keywords.txt`, and `library.concepts.txt`.
3. **`global`**:
   - Expands scope to all modules and sub-modules across the entire Library.

---

## 4. Detailed Operational Specifications

### 4.1 Questions & Objectives File (`<name>.questions.txt`)
Decoupled target files support both Questions (`Q#`) and Objectives (`O#`):
```text
Q1: What are the main risk factors?
- Keywords: risk, exposure, default
- Concepts: Credit Risk (web: true)

O1: Identify all mitigation strategies.
- Keywords: mitigation, hedging, collateral
```

### 4.2 Findings Schema (`references/findings.schema.json`)
The findings payload emitted by `/snipper:snip` conforms to `findings.schema.json` using string `target_ids`:
```json
{
  "findings": [
    {
      "target_ids": ["Q1", "O1"],
      "snippet_text": "Verbatim sentence or paragraph matching the document body character-for-character.",
      "web_sources": [
        "https://example.com/source"
      ],
      "keywords": [
        "risk",
        "mitigation"
      ]
    }
  ],
  "unanswered_targets": ["Q2"]
}
```

### 4.3 Idempotent In-Place Mutation (`/snipper:hlt`)
1. **Pristine Preservation**: Existing document styles, margins, headers, and non-body elements are preserved.
2. **Delimited Summary Block**: Prepend summary at paragraph 0:
   ```text
   === SNIPPER SUMMARY START ===
   Questions & Answers / Objectives

   Q1: What are the main risk factors?
   Keywords:
     • risk
     • exposure
     • default

   "..." Q¹

   O1: Identify all mitigation strategies.
   Keywords:
     • mitigation
     • hedging
     • collateral

   "..." O¹

   === SNIPPER SUMMARY END ===
   ```
3. **Re-mutation Safety**: When `snipper hlt` runs on an already-mutated `.docx`, it identifies and deletes all paragraphs between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`, clears run highlight and bold properties from body paragraphs, and writes fresh mutations without duplicating blocks or stacking highlights.

### 4.4 Findings Lookup & Retrieval (`/snipper:lookup`)
1. **Candidate Discovery**: Discovers all `<name>.findings.json` files within the resolved `--scope`.
2. **Deterministic Lexical Ranking**:
   - If `--limit <N>` is provided: calculates lexical keyword and lemma overlap scores, ranks candidates, and caps output to top N candidates.
   - If `--limit` is omitted: skips lexical pre-filtering and evaluates all candidate findings.
3. **Snippet Card Display**: Formats results with spatial coordinates, target IDs, matched keywords, and source relative paths:
   ```text
   ------------------------------------------------------------
   [Module/SubModule/report.docx] [P12] (Target: Q1)
   Matched Keywords: risk, exposure
   "Verbatim snippet text from findings payload..."
   ------------------------------------------------------------
   ```

---

## 5. Gotchas

- **File Locks in Microsoft Word**: If the target `.docx` is open in Microsoft Word, saving will fail with a `PermissionError`. Close Word before running in-place mutations.
- **Character-for-Character Verbatim Alignment**: Snippet text must match paragraph text exactly (including curly quotes, line breaks, and punctuation); minor discrepancies cause string alignment failures during mutation.
- **Run Delimiters in python-docx**: Text runs cannot cross `<w:p>` boundaries. Multi-paragraph snippets must be split per paragraph before formatting.
- **Clean Ground Truth**: `<name>.txt` serves as the un-mutated text backup. If an in-place `.docx` ever needs reconstruction, the plain text is conserved in `<name>.txt`.