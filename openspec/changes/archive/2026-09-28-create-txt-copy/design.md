## Context

See `proposal.md` for motivation. Currently, `DocumentParser` in `snipper/document.py` parses `.docx` files using `python-docx` into structured `Question` objects and `body_paragraphs: List[Tuple[int, Paragraph]]`. Each paragraph has `p.text`, which holds the exact raw Unicode characters. Currently, there is no direct export mechanism to output these parsed sections into a standalone text file for agents to read.

## Goals / Non-Goals

**Goals:**
- Provide a deterministic text export utility (`export_text_copy`) that writes parsed questions and body paragraphs into a clean `.txt` companion file.
- Include explicit `[P{idx}]` paragraph index markers for every body paragraph to provide unambiguous spatial orientation.
- Preserve 100% verbatim character alignment matching `p.text` without synthetic Markdown formatting or character escaping.
- Provide a `snipper dump <document.docx> [--output <path>]` CLI command.
- Support auto-generation of `<filename>.snipper.txt` during `snipper run` and `DocumentParser.parse()`.

**Non-Goals:**
- Interactive follow-up question workflows or document mutation modifications (scoped separately).
- Markdown formatting, HTML wrapping, or styling conversion.

## Decisions

### Decision 1: Companion File Naming Convention (`<filename>.snipper.txt`)
- **Choice**: Default to `<filename>.snipper.txt` in the same directory as the `.docx` file.
- **Rationale**: Prevents accidental collision with user-created `.txt` files while keeping the companion clearly coupled with the `.docx` document and its backup (`<filename>.backup.docx`).
- **Alternative**: Using `<filename>.txt`. Rejected due to collision risk with user notes.

### Decision 2: Paragraph Marker Format (`[P{idx}] `)
- **Choice**: Prefix each body paragraph with `[P0]`, `[P1]`, etc.
- **Rationale**: Zero-indexed integer tags directly correspond to the index in `parsed.body_paragraphs`. The syntax is distinct and easily recognized by LLM agents.
- **Alternative**: Line numbers only or HTML comments `<!-- p: 0 -->`. Rejected because plain text cannot use HTML comments cleanly, and line numbers drift across wrapped text.

### Decision 3: Text Structure Delimiters
- **Choice**:
  ```text
  === QUESTIONS ===
  1. <Question text>
     - Keywords: <kw1>, <kw2>
     - Concepts: <concept1>

  === BODY ===
  [P0] <verbatim paragraph text>

  [P1] <verbatim paragraph text>
  ```
- **Rationale**: Minimalist delimiters clearly partition questions from body text while maintaining human and machine readability.

### Decision 4: CLI Subcommand `snipper dump`
- **Choice**: Add `snipper dump <document.docx> [--output <path>]`.
- **Rationale**: Follows standard CLI conventions for dumping processed text representations without executing mutation.

## Risks / Trade-offs

- **[Risk] Agent inadvertently includes `[P0]` in `snippet_text`**  
  → **Mitigation**: Update agent instructions (`SKILL.md`) to explicitly note that `[P#]` prefixes are location markers and must be excluded from extracted `snippet_text`.
- **[Risk] Out-of-sync companion text if `.docx` is edited externally**  
  → **Mitigation**: `DocumentParser.parse()` or `snipper run` automatically updates `<filename>.snipper.txt` whenever the pipeline is invoked.
