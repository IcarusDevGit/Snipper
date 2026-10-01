## Context

The repository currently defines a package named `highliter` with console script `highliter = "highliter.cli:main"`. The codebase contains three phases: Phase 1 (deterministic lexical matching & highlight), Phase 2 (agent semantic answer discovery), and Phase 3 (in-place document mutation and summary generation). 

See `proposal.md` for the motivation and rebranding goals.

## Goals / Non-Goals

**Goals:**
- Move Python package `highliter/` to `snipper/`.
- Provide `snipper` as the console script and CLI entry point.
- Implement `snipper highlight <document.docx>` as the primary command for Phase 1 Highlighter execution, with `snipper match` and `snipper run --lexical-only` preserved as aliases.
- Rename `HighliterConfig` to `SnipperConfig` while keeping clean compatibility with the highlighter engine.
- Update all imports in codebase and tests from `highliter` to `snipper`.
- Update `pyproject.toml` to build `snipper`.
- Update agent documentation in `skill/` and OpenSpec specifications.
- Verify all unit and integration tests pass cleanly under `pytest`.

**Non-Goals:**
- Altering the core NLP lemma matching algorithm or python-docx run-splitting logic.
- Changing `findings.schema.json` data structure (only descriptions/references are updated).

## Decisions

### 1. Package Reorganization (`snipper/highlighter.py`)
- **Choice**: Rename the root package to `snipper/`, keeping `highlighter.py` as the module that powers the Phase 1 Highlighter engine.
- **Rationale**: Keeps the architecture modular and explicitly aligns module names with system roles: Snipper is the top-level suite; `highlighter` is its code-only styling and run-splitting engine.
- **Alternatives considered**: Extracting `highlighter` into a completely separate external library; rejected as unnecessary complexity for a unified local tool.

### 2. CLI Interface & Subcommands
- **Choice**: Add `highlight` as a top-level subcommand in `snipper.cli:main` alongside `run` and `match`.
- **Rationale**: Satisfies the requirement that the code-based Highlighter is a first-class feature of Snipper (`snipper highlight <doc>`) while retaining full backward compatibility for `match` and `run --lexical-only`.

### 3. Config Class Renaming
- **Choice**: Rename `HighliterConfig` to `SnipperConfig` in `snipper/config.py`. Provide an alias `HighlighterConfig = SnipperConfig` if needed for clarity.

### 4. Build Artifacts & Testing
- **Choice**: Clean out old `highliter.egg-info` build artifacts, update `pyproject.toml`, and run test suite via `pytest`.

## Risks / Trade-offs

- **Risk: Leftover imports or references causing runtime ImportError**  
  *Mitigation*: Full-text search for `highliter` across all `.py` files and tests, followed by running the full test suite.
- **Risk: Stale pip editable installation shadowing new package**  
  *Mitigation*: Re-run `pip install -e .` after renaming the directory and updating `pyproject.toml`.
