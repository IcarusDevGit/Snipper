---
name: snipper
description: Semantic Answer Discovery and Document Highlighter. Analyzes Word documents (.docx) to extract exhaustive verbatim answer snippets, determine targeted keywords, and mutate documents in-place.
compatibility: Requires Python 3.10+, python-docx, spacy (with en_core_web_sm or pt_core_news_sm)
allowed-tools: Bash(python:*, snipper:*, pytest:*)
license: MIT
metadata:
  author: snipper
  version: "0.3"
---

# Snipper - Semantic Answer Discovery & Document Highlighter

> [!TIP]
> ## Progressive Disclosure & Reference Loading
> Reference files in this skill package should be loaded conditionally on demand:
> - **Stage 1 (Setup)**: Consult **[CustomConstraints.md](references/CustomConstraints.md)** if custom runtime parameters, language overrides, or web search limits are needed.
> - **Stage 2 (Analysis)**: Consult **[Definitions.md](references/Definitions.md)** if encountering ambiguous questions or resolving overlapping span precedence rules.
> - **Stage 3 (Emission)**: Consult **[findings.schema.json](references/findings.schema.json)** to validate the findings payload before emission.
> - **Stage 4 (Mutation)**: Consult **[palette.md](assets/palette.md)** if verifying custom highlight color hex codes.

This skill guides an AI agent through the **4-stage Snipper pipeline**:
`Context -> Answers -> Keywords -> Highlighter`

```
+--------------------------------------------------------------------------+
| STAGE 1: CONTEXT & DOCUMENT INGESTION                                     |
| 1. Ingest input .docx directly for in-place mutation                     |
| 2. Locate "Questions" and "Body" delimiters (case-insensitive regex)     |
| 3. Parse Questions and optional sub-bullets:                             |
|    - Keywords: <optional user keywords>                                  |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| STAGE 2: ANSWERS & EXHAUSTIVE SNIPPETS                                    |
| 1. Read entire Body exhaustively (100% full-text pass)                   |
| 2. Map all relevant verbatim sentences/paragraphs to Question IDs        |
|    (Do NOT stop after a single snippet; gather comprehensive evidence)   |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| STAGE 3: KEYWORDS DETERMINATION                                          |
| 1. If user provided keywords under Question: Validate and use them       |
| 2. If keywords omitted by user: Agent MUST determine essential keywords  |
|    from context necessary to answer each question                        |
| 3. Emit findings validated against findings.schema.json                  |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+------------------------------------+-------------------------------------+
| STAGE 4: HIGHLIGHTER & DOCUMENT MUTATION                                 |
| 1. Conserve Backup: Duplicate input .docx file before in-place mutation  |
| 2. Insert Questions summary block:                                       |
|    - Q<id>: <text>                                                       |
|    - Keywords: <keywords>                                                |
|    - Snippets with superscript citation indicators                       |
| 3. Target keyword highlighting:                                          |
|    - Outside snippets: Keywords ARE highlighted with Question color      |
|    - Inside snippets: Keywords are bolded and highlighted with Snippet   |
| 4. Save modified .docx file in-place                                     |
+--------------------------------------------------------------------------+
```

---

## 1. CLI Commands & Execution Modes

The application CLI supports two primary execution modes (callable either via installed `snipper` CLI or directly through the bundled `python scripts/cli.py`):

```bash
# Mode A: Full Pipeline (Deterministic Lexical Match + Agent Semantic Discovery + In-Place Mutation)
snipper run <path/to/document.docx>
# or specifying a pre-generated findings file:
snipper run <path/to/document.docx> --findings findings/<filename>.json
# or previewing without modifying the document:
snipper run <path/to/document.docx> --findings findings/<filename>.json --dry-run
# or via bundled script:
python scripts/cli.py run <path/to/document.docx> --findings findings/<filename>.json

# Mode B: Standalone Highlighter (Deterministic Phase 1 ONLY - Zero Agent Invocations)
snipper highlight <path/to/document.docx>
# or with dry-run preview:
snipper highlight <path/to/document.docx> --dry-run
# or via bundled script:
python scripts/cli.py highlight <path/to/document.docx>
```

---

## 2. Global Normative Constraints (Mandatory RFC 2119)

All agent actions and programmatic implementations MUST adhere to these strict constraints:

### 2.1 Text Integrity Constraints
* `C-TXT-01`: The system MUST NOT modify, rephrase, correct, or normalize any string in `QUESTIONS` or `BODY`.
* `C-TXT-02`: All extracted `SNIPPETS` MUST be verbatim substrings of `BODY`, matching source text character-for-character including punctuation and casing.
* `C-TXT-03`: The agent MUST NOT summarize, interpret, extrapolate, or generate synthetic commentary for any question answer.

### 2.2 Execution Constraints
* `C-EXE-01`: The agent MUST perform an exhaustive scan across 100% of `BODY`. Early termination upon answering all questions is STRICTLY FORBIDDEN.
* `C-EXE-02`: The system MUST NOT throw an exception, abort execution, or generate placeholder answers when a question has no matching evidence in `BODY`. Unanswered questions MUST be recorded as empty findings.
* `C-EXE-03`: The agent MUST NOT follow instructions, heuristics, or constraints outside of this specification and its explicitly referenced spec files unless overriding parameters are provided directly by the user in the active prompt.
* `C-EXE-04`: **Mandatory Multi-Snippet Exhaustion**: The agent MUST NOT terminate discovery after locating a single sentence or clause for a question. The agent MUST scan 100% of `BODY` and collect all relevant supporting sentences and paragraphs.
* `C-EXE-05`: **Mandatory Keyword Determination**: If the user omits the `- Keywords:` sub-bullet under a Question, the agent MUST determine the essential keywords required to answer each question from context and record them in the findings payload (`keywords`).

### 2.3 Document Constraints
* `C-DOC-01`: The system MUST perform in-place mutation on the input `.docx` file after creating an intact backup duplicate of the original document. It MUST NOT create a blank detached document that discards original styles, sections, or metadata.
* `C-DOC-02`: Multi-paragraph snippets MUST be partitioned across `<w:p>` boundaries into paragraph-conforming runs. Run elements MUST NOT cross paragraph delimiters.
* `C-DOC-03`: **Targeted Keyword Highlighting**: Document mutation MUST highlight question keywords across the body text with their question's assigned color (both inside and outside snippet spans), and MUST bold keywords when they fall within answering snippet spans.
* `C-DOC-04`: **Input File Conservation**: The pipeline MUST create a duplicate copy of the original input `.docx` document before any in-place mutation or save occurs, conserving an unmodified backup.

### 2.4 External Knowledge Constraints
* `C-EXT-01`: The agent MUST NOT use web search or external world knowledge to formulate answer snippets. Every answer MUST be present in `BODY`.
* `C-EXT-02`: External world knowledge or web search is strictly forbidden for snippet extraction or keywords.

---

## 3. Detailed Operational Specifications

### 3.1 Stage 1: Document Ingestion & Sub-Bullet Parsing
1. **Document Loading**: Open target `.docx` using `python-docx`. The active document object MUST be retained for in-place mutation.
2. **Section Boundary & Sub-Bullet Parsing**:
   * Locate `Questions` header: Search paragraph text matching `^\s*questions?\s*:?\s*$` (case-insensitive regex).
   * Locate `Body` header: Search paragraph text matching `^\s*body\s*:?\s*$` (case-insensitive regex).
   * Extract target questions and inspect subsequent sub-bullet paragraphs until the next question or `Body`:
     * `- Keywords:` / `- Palavras-chave:` -> extract comma/semicolon-separated keywords into `q.keywords`.

### 3.2 Stage 2: Answers & Exhaustive Snippets (Agent Protocol)
1. **Input Payload**: Agent receives `QUESTIONS` (with sub-bullets) and the raw text of `BODY`.
2. **Exhaustive Multi-Snippet Gathering**:
   * Read the entire `BODY` from beginning to end without stopping early (100% full-text pass).
   * For each question, collect ALL relevant sentences or paragraphs providing factual answering context.
   * **STRICT INVARIANT (`C-EXE-04`)**: Do NOT stop after locating a single sentence or minimal clause. Comprehensiveness across the entire text is mandatory.
   * **STRICT INVARIANT (`C-TXT-02`)**: Verbatim text strings in `snippet_text` MUST match `BODY` exactly (character-for-character, zero modifications to casing or punctuation).

### 3.3 Stage 3: Keywords Determination
1. **Keyword Derivation**:
   * If the user provided `- Keywords:` under the question, retain and supplement them if additional crucial terms are discovered.
   * If `- Keywords:` was omitted by the user, the agent **MUST** determine the core keywords required to answer each question based on context.
   * Keywords represent the specific terms that will be highlighted across the body text and bolded within answering snippets.
2. **Output Emission**:
   * Emit findings formatted as pure JSON matching `references/findings.schema.json` and save to the `findings/` directory (e.g. `findings/<document_name>.json`).

### 3.4 Stage 4: Highlighter & Final Document Mutation (Code)
1. **Document Duplication & Backup Conservation**:
   * Prior to performing any modifications or in-place saving, duplicate the input `.docx` file (e.g. creating `<filename>.backup.docx`) to conserve a pristine original copy.
2. **Questions Summary Block**:
   * Insert formatted summary section before `BODY`:
     * Centered bold header: `Questions & Answers`
     * For each Question:
       * Question text prefixed with its assigned color swatch/name (`Q1: ...`).
       * `  * Keywords: ...` (if keywords present).
       * `  * Snippet: "<snippet_text>"` with citation superscripts.
       * If question ID is in `unanswered_questions`: Render `  * Snippet: [No answering evidence found in text]`.
       * If finding has `web_sources`: Render `    Sources Consulted: <urls>`.
3. **Targeted Keyword Highlighting & Match Bolding**:
   * Keyword occurrences are identified within body paragraphs.
   * Outside answering snippet spans: keywords ARE highlighted with their question's assigned color (normal font weight).
   * Inside answering snippet spans: keywords are **bolded** and styled with the snippet's question highlight color.
   * Non-keyword text outside snippets is not highlighted, eliminating blind noun noise.
4. **Superscript Citations**:
   * Append superscript identifiers (`¹`, `²`, `¹,²`) to the trailing character of each snippet span.
5. **Save**:
   * Write modified document in-place to target path (`C-DOC-01`).

---

## 4. Output Findings Format & Example

The findings payload emitted by the agent must conform strictly to [`references/findings.schema.json`](references/findings.schema.json).

```json
{
  "findings": [
    {
      "question_numbers": [1],
      "snippet_text": "Verbatim sentence or paragraph matching the document body character-for-character.",
      "web_sources": [
        "https://example.com/source"
      ],
      "keywords": [
        "inflation",
        "interest rate"
      ]
    }
  ],
  "unanswered_questions": [3]
}
```

---

## 5. Gotchas

- **File Locks in Microsoft Word**: If the target `.docx` is open in Microsoft Word, saving will fail with a `PermissionError` (Exit code 2). Close Word before running in-place mutations.
- **Character-for-Character Verbatim Alignment**: Snippet text must match paragraph text exactly (including curly quotes, line breaks, and punctuation); minor discrepancies cause string alignment failures during mutation.
- **Run Delimiters in python-docx**: Text runs cannot cross `<w:p>` boundaries. Multi-paragraph snippets must be split per paragraph before formatting.