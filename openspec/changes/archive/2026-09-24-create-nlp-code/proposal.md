## Why

Highliter requires a deterministic, lightweight NLP pre-processing engine (Phase 1) that parses `.docx` files, identifies lexical noun matches between questions and the body text without invoking LLM agents, and applies in-place highlights. Creating this capability now establishes the core programmatic pipeline, enabling standalone lexical highlighting via CLI and saving LLM tokens before semantic answer extraction.

## What Changes

- Add a document ingestion parser resilient to heading variations that extracts `Questions` and `Body` from `.docx` files.
- Add language detection and spaCy NLP pipeline integration supporting both English (`en_core_web_sm`) and Brazilian Portuguese (`pt_core_news_sm`).
- Implement deterministic noun/proper-noun lemma extraction from questions, excluding stop words, verbs, and prepositions.
- Implement full-body lemma scanning to locate exact token offsets in the document structure.
- Implement in-place `.docx` styling for matches using either hex shading (`<w:shd>`) or named highlights (`<w:highlight>`).
- Provide a CLI command (`highliter run <file.docx> --lexical-only` or `highliter match <file.docx>`) to execute Phase 1 independently.

## Capabilities

### New Capabilities
- `lexical-matching`: Deterministic ingestion of `.docx` documents, language-aware spaCy lemmatization for noun matching across questions and body, and in-place XML highlighting.

### Modified Capabilities
<!-- None: This is a greenfield capability in a new repository. -->

## Impact

- Introduces dependencies: `spacy`, `python-docx`, language models (`en_core_web_sm`, `pt_core_news_sm`).
- Establishes the foundational Python package structure (`highliter/`) and CLI entry point.
- Does not alter existing files or require external API keys.
