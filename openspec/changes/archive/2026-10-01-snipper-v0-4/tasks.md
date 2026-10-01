## 1. Schema & Data Model Updates

- [x] 1.1 Update `references/findings.schema.json` and `findings.py` to support string `target_ids: ["Q1", "O1"]` and verify with test suite
- [x] 1.2 Implement `QuestionsParser` in `document.py` to parse decoupled `<name>.questions.txt` files supporting `Q#` (Questions) and `O#` (Objectives) with `- Keywords:` and `- Concepts:` sub-bullets, and verify with unit tests
- [x] 1.3 Update `DocumentParser` and plain-text export in `document.py` to generate clean body `<name>.txt` companion files with paragraph coordinates `[P#]` without requiring in-document `Questions:` or `Body:` delimiters

## 2. Scope Resolution & Ancestor Inheritance

- [x] 2.1 Implement `ScopeResolver` to parse and enforce `local`, `hierarchical`, and `global` boundaries across Library, Module, and Sub-module directories
- [x] 2.2 Implement ancestor metadata inheritance loader for `library.keywords.txt`, `library.concepts.txt`, `module.keywords.txt`, and `module.concepts.txt` in hierarchical mode
- [x] 2.3 Add unit tests verifying scope boundary enforcement, token pruning, and upward keyword/concept inheritance

## 3. Idempotent In-Place Document Mutation

- [x] 3.1 Update `DocumentMutator` in `mutation.py` to prepend the summary block at paragraph 0 wrapped between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`
- [x] 3.2 Implement summary block detection and cleanup on re-runs to ensure `snipper hlt` is fully idempotent without accumulating duplicate summary blocks or highlights
- [x] 3.3 Remove duplicate `.backup.docx` creation from the mutation pipeline, treating `<name>.txt` as the primary text backup
- [x] 3.4 Add unit and integration tests verifying clean mutation and re-mutation behavior on Word documents

## 4. Findings Lookup & Hybrid Retrieval

- [x] 4.1 Implement scoped findings scanner in `findings.py` or new retrieval module to discover candidate snippets across `.findings.json` files within the active scope
- [x] 4.2 Implement deterministic lexical scoring to rank candidate snippets when `--limit` is provided, and bypass lexical pre-filtering when `--limit` is omitted
- [x] 4.3 Implement snippet card formatter displaying source path, spatial coordinate `[P#]`, target ID, snippet text, and matched keywords
- [x] 4.4 Add unit tests verifying `/snipper:lookup` execution, limit-based candidate capping, and output card formatting

## 5. CLI Subcommands, Workflows & Verification

- [x] 5.1 Update `cli.py` to expose `/snipper:snip`, `/snipper:hlt`, `/snipper:lookup`, and `dump` with convention-over-configuration auto-detection for `--q` and `--f`
- [x] 5.2 Update `.agents/skills/snipper/SKILL.md` and create/update workflow markdown files (`.agents/workflows/snipper.md`) reflecting the decoupled v0.4 architecture
- [x] 5.3 Execute full pytest test suite (`pytest .agents/skills/snipper/scripts`) and verify all existing and new tests pass cleanly
