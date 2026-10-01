## 1. Findings Ingestion & Superscript Utilities

- [x] 1.1 Implement `highliter.findings` module to load and validate findings data against `findings.schema.json`, and verify schema validation with unit tests.
- [x] 1.2 Implement Unicode superscript formatter converting question IDs to superscript annotations (e.g. `1` -> `¹`, `[1, 2]` -> `¹,²`), and verify with unit tests.

## 2. Snippet Alignment & Overlap Resolution

- [x] 2.1 Implement normalized text alignment utility locating verbatim snippet substrings across paragraphs, tolerating quote and whitespace variations, and verify with edge-case tests.
- [x] 2.2 Implement character-level span resolver supporting nested snippets (shorter inner span takes inner question color and identifier; outer span takes outer question color and identifier) and multi-question shared spans, and verify interval resolution.
- [x] 2.3 Implement match bolding integration ensuring lexical matches inside active snippet spans are styled bold with snippet highlight colors, and verify run styling.

## 3. Summary Section Generation & Document Mutation

- [x] 3.1 Implement Questions & Answers summary section builder inserting formatted questions, assigned colors, answering snippets, citation superscripts, and web sources before the Body, and verify document layout.
- [x] 3.2 Implement `highliter.mutation` orchestrating full in-place document assembly (lexical matches, snippet overlays, match bolding, and summary block), and verify with multi-paragraph document fixtures.

## 4. CLI Integration & End-to-End Verification

- [x] 4.1 Update `highliter/cli.py` to accept `--findings <path.json>`, executing full document mutation and saving in-place, and verify CLI options.
- [x] 4.2 Build end-to-end integration test running `highliter run <file.docx> --findings <findings.json>`, verifying the modified `.docx` structure, highlights, and annotations.
