## Context

Phase 1 provides lexical matching and basic run highlighting. Phase 3 focuses on final document assembly and mutation, integrating agent findings conforming to [findings.schema.json](file:///c:/Dev/Highliter/findings.schema.json) into the `.docx` document in-place as specified in [Instructions.md](file:///c:/Dev/Highliter/Instructions.md) and [Definitions.md](file:///c:/Dev/Highliter/Definitions.md).

## Goals / Non-Goals

**Goals:**
- Ingest and validate agent findings JSON matching `findings.schema.json`.
- Insert formatted `Questions & Answers` summary section before the Body.
- Locate snippet spans across single and multi-paragraph boundaries using normalized alignment.
- Implement character-level interval resolution for nested and shared snippets.
- Bold lexical match tokens occurring inside active snippets while preserving the snippet highlight.
- Append Unicode superscript question indicators (`¹`, `²`, etc.) to snippet boundaries.
- Update the CLI to accept `--findings <path.json>` for automated in-place mutation.

**Non-Goals:**
- Making remote LLM API network calls (Phase 3 consumes findings JSON).
- Web application interface.

## Decisions

### 1. Character-Level Span Map for Interval Resolution
* **Decision**: For each paragraph, build a character-level styling array `char_map[i] = (color, is_bold, question_ids)` initialized with lexical matches, then overlaid with snippets. Longer snippets are applied first, and shorter nested snippets are overlaid on top to ensure shorter spans take precedence.
* **Rationale**: Eliminates complex interval boundary arithmetic. A character-level map resolves nesting, sub-run slicing, and match bolding in $O(L)$ time with mathematical precision.

### 2. Normalized Text Alignment
* **Decision**: When searching for `snippet_text` in body paragraphs, normalize straight/curly quotes, em-dashes, and multiple whitespace during search to locate exact character indices in the original source paragraph.
* **Rationale**: LLM agents often emit straight quotes or collapsed whitespace even when requested to be verbatim. Normalization prevents search failures while preserving original document characters.

### 3. Order of Operations for Document Mutation
* **Decision**: Highlight Body paragraphs first using object references (`Paragraph` instances from `ParsedDocument`), and insert summary paragraphs before the Body header afterwards.
* **Rationale**: Inserting new paragraphs changes numeric paragraph indices in `doc.paragraphs`. Performing body styling first prevents index shift bugs.

### 4. Unicode Superscript Formatting
* **Decision**: Use native Unicode superscript characters (`¹`, `²`, `³`, `⁴`, etc.) directly in run text.
* **Rationale**: Unicode superscripts are universally rendered identically across Microsoft Word, Google Docs, LibreOffice, and mobile viewers without requiring complex OpenXML superscript run tags.

## Risks / Trade-offs

* **[Risk] Snippet text not found in document** → *Mitigation*: Fall back to normalized sliding window search; log clear descriptive warning if a snippet is completely absent from the text.
* **[Risk] Multi-paragraph snippets across paragraph breaks** → *Mitigation*: Partition snippet into paragraph substrings and style each paragraph independently, attaching the superscript only to the final segment.
