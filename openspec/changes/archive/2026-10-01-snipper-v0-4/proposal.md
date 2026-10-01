## Why

Snipper previously operated as a single-document processor where questions and body text were tightly coupled inside the same Word document (`.docx`), requiring manual editing of source documents, awkward section delimiter matching (`Questions:` / `Body:`), and duplicate `.backup.docx` files for safety. 

With Snipper v0.4, knowledge is organized into a scalable hierarchy (Library -> Modules -> Sub-modules -> Entries) where clean source documents (`.docx`), lightweight plain-text companions (`.txt`), query files (`.questions.txt`), and extraction outputs (`.findings.json`) are decoupled. This eliminates document corruption risks, enables prompt token optimization via Scopes (`local`, `hierarchical`, `global`), introduces goal-oriented Objectives (`O#`) alongside Questions (`Q#`), and decomposes the monolithic pipeline into three specialized workflows: `/snipper:snip`, `/snipper:hlt`, and `/snipper:lookup`.

## What Changes

- **Sub-Module File Separation**: Decouples Questions and Body into separate files sharing a prefix: `<name>.docx` (clean entry), `<name>.txt` (fast read companion & backup), `<name>.questions.txt` (questions & objectives), and `<name>.findings.json` (findings & citations).
- **Elimination of `.backup.docx`**: The `.txt` companion serves as the permanent ground-truth text backup. Document mutation becomes reversible and idempotent via code-level stripping and delimited summary blocks.
- **Top-of-Document Summary Block**: Prepends the Questions & Answers / Objectives summary block at paragraph 0 of `<name>.docx`, wrapped in explicit delimiters (`=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`) for clean re-runs.
- **Objectives Support**: Extends query parsing and findings schema to support Objectives (`O#`) alongside Questions (`Q#`), both supporting `- Keywords:` and `- Concepts:` sub-bullets.
- **String Target IDs in Findings**: Updates findings schema from integer `question_numbers` to string `target_ids: ["Q1", "O1"]`.
- **Query Scopes**: Implements three query scopes: `local` (target module including all child sub-modules, or a single targeted sub-module/entry, without ascending to parents), `hierarchical` (target subtree plus ancestor keywords/concepts from `module.keywords.txt` and `library.keywords.txt`), and `global` (entire library).
- **Three Modular Workflows**:
  - `/snipper:snip --dir {.txt/.docs} [--q {file}]`: Generates/syncs `.txt` from `.docs` and extracts findings contextually relevant to questions/objectives. `--q` defaults to `<name>.questions.txt`.
  - `/snipper:hlt --docs {.docs} [--f {.findings}]`: Applies highlighting, bolding, citations, and prepended summary block to `.docx` based on `.findings.json`. `--f` defaults to `<name>.findings.json`.
  - `/snipper:lookup --q/o {query} [--dir path] [--scope scope] [--limit N]`: Searches existing `.findings.json` files within scope; uses lexical keyword matching for prioritization only when `--limit` is specified.

## Capabilities

### New Capabilities
- `scope-resolution`: Evaluates query scopes (`local`, `hierarchical`, `global`) and resolves upward keyword and concept inheritance across module and library hierarchy.
- `questions-objectives-parsing`: Ingests decoupled `<name>.questions.txt` containing Questions (`Q#`) and Objectives (`O#`) with keywords/concepts sub-bullets and maps findings to string `target_ids`.
- `findings-lookup`: Executes semantic and lexical snippet retrieval across pre-existing `.findings.json` files within a defined scope, formatting results into snippet cards with paragraph coordinates.

### Modified Capabilities
- `document-mutation`: Prepends summary block at paragraph 0 with start/end delimiters, supports both Questions and Objectives, eliminates the requirement for duplicate `.backup.docx` creation, and ensures idempotent re-runs.
- `text-export`: Exports plain text directly from clean body `.docx` without requiring an in-document `Questions:` delimiter, synchronizing companion `<name>.txt` alongside `<name>.docx`.
- `lexical-matching`: Decouples section parsing from single `.docx` files to ingest external `<name>.questions.txt`, and provides keyword matching prioritization for findings lookup.

## Impact

- **CLI Interface**: Updated CLI subcommands for `snip`, `highlight`/`hlt`, `lookup`, and `dump`.
- **File System**: Sub-modules will now store companion `.txt`, `.questions.txt`, and `.findings.json` files alongside `.docx` entries.
- **Agent Workflows**: Workflows decompose into `/snipper:snip`, `/snipper:hlt`, and `/snipper:lookup` with token savings via scope boundary enforcement.
- **Findings Schema**: `references/findings.schema.json` evolves from `question_numbers: [int]` to `target_ids: [string]`.
