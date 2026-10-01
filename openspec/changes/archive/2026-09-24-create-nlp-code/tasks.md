## 1. Project Setup & Package Scaffolding

- [x] 1.1 Create `highliter` package structure with `pyproject.toml` or `requirements.txt` specifying `spacy` and `python-docx`, and verify package dependencies resolve.
- [x] 1.2 Implement configuration reader for `CustomConstraints.md` (parsing `language`, `palette`, `palette_mode`, `proper_nouns_only`) and verify via unit tests.

## 2. Document Ingestion & Section Parsing

- [x] 2.1 Implement resilient header parser identifying `Questions` and `Body` paragraphs (case-insensitive, accepting colons, bold, and heading styles) using `python-docx`, and verify with sample document structures.
- [x] 2.2 Implement question enumerator assigning 1-indexed IDs ($Q1, Q2, \dots$) and mapping colors from palette configuration, and verify question mapping.

## 3. NLP Lemmatization Engine

- [x] 3.1 Implement multilingual spaCy model loader with lazy loading and automated model download checks for `en_core_web_sm` and `pt_core_news_sm`, and verify model loading.
- [x] 3.2 Implement question noun lemma extractor filtering for `NOUN` and `PROPN` (excluding stop words, verbs, prepositions) with support for `proper_nouns_only`, and verify extraction against English and Portuguese test queries.
- [x] 3.3 Implement body text lemma scanner that maps question lemmas to paragraph and character spans `(paragraph_idx, start_char, end_char, question_id)`, and verify against multi-paragraph text fixtures.

## 4. In-Place Highlighting & XML Styling

- [x] 4.1 Implement sub-run text splitting utility in `python-docx` to isolate matching words while preserving existing font styles, and verify XML run structure.
- [x] 4.2 Implement highlight styler applying `<w:shd w:fill="{HEX}"/>` for hex colors and `<w:highlight>` for named colors, with modulo palette cycling, and verify visual styling in modified document.

## 5. CLI Interface & Verification

- [x] 5.1 Implement CLI commands `highliter run <file.docx> --lexical-only` and `highliter match <file.docx>`, ensuring in-place save and immediate exit with code 0 without calling any agent.
- [x] 5.2 Build end-to-end test with a sample `.docx` file validating that matching nouns between questions and body are correctly highlighted in-place.
