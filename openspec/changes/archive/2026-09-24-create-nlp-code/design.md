## Context

Highliter's deterministic pre-processing phase (Phase 1) is defined in [Instructions.md](file:///c:/Dev/Highliter/Instructions.md) and [Definitions.md](file:///c:/Dev/Highliter/Definitions.md). The system must extract questions and body text from `.docx` files, identify question noun lemmas using spaCy, highlight lexical matches directly in the document, and terminate without invoking an LLM when requested.

## Goals / Non-Goals

**Goals:**
- Provide a robust Python package (`highliter`) with CLI entry point.
- Parse `.docx` files into Questions and Body containers with resilient heading tolerance.
- Support multilingual lemmatization for English (`en_core_web_sm`) and Brazilian Portuguese (`pt_core_news_sm`).
- Implement in-place highlighting supporting both hex codes (`<w:shd>`) and native Word highlights (`<w:highlight>`).
- Support CLI standalone execution (`highliter run <file.docx> --lexical-only` or `highliter match <file.docx>`).

**Non-Goals:**
- LLM semantic answer discovery (Phase 2, deferred to subsequent change).
- Web application interface or cloud hosting (CLI only).
- Non-`.docx` file formats (e.g. PDF, raw text).

## Decisions

### 1. NLP Engine: spaCy (`en_core_web_sm` / `pt_core_news_sm`)
* **Decision**: Use spaCy with small language models for POS tagging and lemmatization.
* **Rationale**: spaCy is fast, offline, and provides accurate `NOUN` / `PROPN` tagging alongside base lemmas (`token.lemma_.lower()`).
* **Alternatives Considered**: NLTK (requires multi-step downloads, clunky lemmatization) and pure regex (cannot differentiate nouns from verbs).

### 2. Highlighting Mechanism: Direct XML Shading for Hex Codes
* **Decision**: For hex colors, inject `<w:shd w:val="clear" w:color="auto" w:fill="{HEX}"/>` into the run properties (`rPr`). For named colors, use `run.font.highlight_color = WD_COLOR_INDEX.{NAME}`.
* **Rationale**: `python-docx` only supports 16 predefined highlight color constants. Direct XML manipulation unlocks arbitrary hex codes while remaining 100% compatible with Word and Google Docs.
* **Alternatives Considered**: Background paragraph shading (styles whole lines rather than specific token words).

### 3. In-Place Mutation via `python-docx`
* **Decision**: Mutate the active `docx.Document` instance directly and overwrite the source file (or write to a specified output path).
* **Rationale**: Avoids discarding original document metadata, margins, non-body sections, and existing styles.

### 4. Run Splitting for Sub-Paragraph Matching
* **Decision**: Implement a text run segmenter that divides an existing `Run` into pre-match, matched, and post-match segments with inherited formatting.
* **Rationale**: Word runs group arbitrary character sequences. A single match typically occupies a sub-string of a run.

## Risks / Trade-offs

* **[Risk] Missing spaCy model at runtime** → *Mitigation*: Provide automated CLI download prompts or helper functions (`spacy.cli.download`) when models are missing.
* **[Risk] Heading format anomalies in user documents** → *Mitigation*: Use regex `^\s*(questions?|perguntas?)\s*:?\s*$` and `^\s*(body|corpo|texto)\s*:?\s*$` with case-insensitivity.
* **[Risk] Run splitting loses subtle XML formatting** → *Mitigation*: Copy all font properties (bold, italic, font name, size, color) to newly created runs when splitting text.
