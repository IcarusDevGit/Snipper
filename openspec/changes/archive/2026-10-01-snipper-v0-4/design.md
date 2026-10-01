## Context

See [proposal.md](proposal.md) for background and motivation. 

Currently, the Snipper engine resides in `.agents/skills/snipper/scripts/` (`document.py`, `mutation.py`, `highlighter.py`, `findings.py`, `cli.py`, `nlp.py`). The existing pipeline couples questions and body text within a single Word document, relying on regex delimiter matching (`Questions:` / `Body:`) and requiring `.backup.docx` duplicate files before in-place mutation. 

Snipper v0.4 introduces a decoupled sub-module architecture, query-level scoping, and three specialized workflows (`/snipper:snip`, `/snipper:hlt`, `/snipper:lookup`).

## Goals / Non-Goals

**Goals:**
- Decouple source content (`<name>.docx`), text companion/backup (`<name>.txt`), query targets (`<name>.questions.txt`), and findings (`<name>.findings.json`).
- Eliminate `.backup.docx` creation by using `<name>.txt` as the text backup and making `.docx` mutation idempotent via explicit delimiters at paragraph 0.
- Support both Questions (`Q#`) and Objectives (`O#`) with `- Keywords:` and `- Concepts:` sub-bullets.
- Implement Scope resolution (`local`, `hierarchical`, `global`) with ancestor keyword/concept inheritance.
- Provide the `/snipper:lookup` retrieval workflow combining optional lexical pre-filtering with agent evaluation.

**Non-Goals:**
- Multi-document interactive follow-up generation (deferred to v0.5).
- Altering the 15-color highlight palette or replacing `python-docx`.
- Non-Word binary document format ingestion.

## Decisions

### 1. File Organization & Prefix-Based Pairing
- **Choice**: Files within a sub-module share a common `<name>` base prefix:
  - `<name>.docx` (clean source entry)
  - `<name>.txt` (plain text companion & backup)
  - `<name>.questions.txt` (questions and objectives)
  - `<name>.findings.json` (extracted evidence, citations, keywords)
- **Rationale**: Keeps multiple entries or versions distinct within a folder while enabling convention-over-configuration (e.g. running `snipper snip report.docx` automatically locates `report.questions.txt` and produces `report.findings.json`).
- **Alternatives Considered**: Fixed names (`entry.docx`, `questions.txt`) which would limit sub-modules to strictly one entry.

### 2. Idempotent Summary Block via Explicit Delimiters
- **Choice**: The Questions & Answers / Objectives summary block is prepended at paragraph 0, wrapped within distinct marker paragraphs:
  `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`.
- **Rationale**: When re-running `snipper hlt`, the mutator identifies and strips existing summary paragraphs between the delimiters before inserting fresh findings, preventing duplicate blocks and enabling safe iterative re-mutations.
- **Alternatives Considered**: Appending at the end of the document (less visible for reviewers) or prepending without delimiters (making automated cleanup fragile).

### 3. Plain-Text Companion as Backup (Eliminating `.backup.docx`)
- **Choice**: Remove duplicate `.backup.docx` generation. `<name>.txt` serves as the durable text ground-truth.
- **Rationale**: Prevents disk clutter and out-of-sync duplicate files. The `.docx` mutation is non-destructive to textual content (only styles and the removable summary block are added).

### 4. Findings Schema Evolution to String `target_ids`
- **Choice**: Update findings schema from `question_numbers: [1, 2]` to `target_ids: ["Q1", "O1"]`.
- **Rationale**: Eliminates numeric ambiguity between Question 1 and Objective 1 across reporting, citations, and summary blocks.

### 5. Hybrid Retrieval for `/snipper:lookup`
- **Choice**:
  - When `--limit` is specified: runs lexical keyword and lemma overlap scoring to rank candidates and select top candidates for agent evaluation.
  - When `--limit` is omitted: skips lexical pre-filtering and evaluates all scoped findings via the LLM agent.
- **Rationale**: Allows rapid targeted searches when a limit is requested while preserving full semantic recall when searching without caps.

### 6. Scope Granularity & Boundary Semantics
- **Choice**:
  - **Local Scope**: Targets the entire subtree rooted at `--dir`. If `--dir` points to a **Module**, all child sub-modules and their respective entries/findings are included in scope. If `--dir` points to a **Sub-module** or specific entry file, scope is restricted strictly to that single sub-module. Local scope never ascends to parent directories.
  - **Hierarchical Scope**: Evaluates the local subtree rooted at `--dir` AND ascends upward through parent folders to aggregate ancestor metadata (`library.keywords.txt`, `module.keywords.txt`, etc.).
  - **Global Scope**: Spans all modules and sub-modules across the entire Library.
- **Rationale**: Provides granular control over context loading: users can target an entire subject domain (Module) or pinpoint a single document (Sub-module) without token leaks from unrelated modules.

## Risks / Trade-offs

- **[Risk] Missing `<name>.questions.txt` during `snip`** → *Mitigation*: Fall back gracefully with clear error guidance, or allow passing an explicit `--q <path>` parameter if files are named non-standardly.
- **[Risk] Existing legacy documents with embedded `Questions:` / `Body:`** → *Mitigation*: Provide automated migration logic in `DocumentParser` that can split legacy documents into `<name>.txt` and `<name>.questions.txt`.
- **[Risk] Re-mutation highlight accumulation** → *Mitigation*: In `mutation.py`, clear highlight and shading properties on body runs prior to reapplying slices from new findings.
- **[Risk] Deep directory traversal in `global` scope** → *Mitigation*: Default `--scope` to `local` whenever a target directory or file is specified; only scan the full library when explicitly requested.
