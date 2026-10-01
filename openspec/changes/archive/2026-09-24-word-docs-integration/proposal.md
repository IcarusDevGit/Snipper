## Why

Highliter needs the document mutation and assembly engine (Phase 3) that integrates the findings discovered by agents or callers into the Word document (`.docx`) in-place. This provides users with a finalized, styled output containing a Questions & Answers summary, verbatim snippets highlighted in question colors, nested span conflict resolution, bolded matches inside snippets, and superscript question citations.

## What Changes

- Ingest structured agent findings conforming to `findings.schema.json`.
- Insert a formatted `Questions & Answers` summary block at the beginning of the document before the Body, detailing each Question, its assigned color, answering verbatim snippets with citations, and any web sources consulted.
- Overlay semantic snippet highlights on top of existing paragraph text in the Body.
- Implement multi-paragraph snippet partitioning across `<w:p>` boundaries.
- Implement interval resolution for nested snippets (shorter inner span takes inner question color and identifier; enclosing span retains outer question color and identifier).
- Implement multi-question equal span resolution (lowest question index color with composite superscripts `¹,²`).
- Bold all lexical match tokens that appear inside active snippet spans while preserving the snippet highlight.
- Append Unicode superscript identifiers (`¹`, `²`, etc.) to trailing runs of snippets.
- Save the mutated document in-place.

## Capabilities

### New Capabilities
- `document-mutation`: In-place mutation and assembly of `.docx` documents incorporating agent findings, summary sections, nested snippet precedence, match bolding, and superscript identifier annotations.

### Modified Capabilities
<!-- None: lexical-matching remains unchanged -->

## Impact

- Extends `highliter` package with `highliter.mutation` and enhances `highliter.cli` to support full pipeline runs (`highliter run <file.docx> --findings <findings.json>`).
- Reuses `python-docx` without requiring additional third-party dependencies.
