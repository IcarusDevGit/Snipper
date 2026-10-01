## 1. Package Reorganization and Build Configuration

- [x] 1.1 Move package directory `highliter` to `snipper` and verify directory structure
- [x] 1.2 Update `pyproject.toml` with `name = "snipper"`, `include = ["snipper*"]`, and console script `snipper = "snipper.cli:main"`
- [x] 1.3 Remove legacy `highliter.egg-info` artifacts and reinstall package in editable mode (`pip install -e .`)

## 2. Core Python Source Updates & CLI Enhancement

- [x] 2.1 Rename `HighliterConfig` to `SnipperConfig` in `snipper/config.py` and update internal package imports across all files in `snipper/`
- [x] 2.2 Add `highlight` subcommand in `snipper/cli.py` as primary Phase 1 Highlighter interface, preserving `match` and `run --lexical-only` aliases
- [x] 2.3 Fix all occurrences of misspelled "Highliter" in code comments, CLI help text, logs, and docstrings

## 3. Test Suite Migration and Verification

- [x] 3.1 Update import statements across all files in `tests/` from `highliter` to `snipper`
- [x] 3.2 Update CLI invocation tests in `tests/test_cli.py` to test `snipper highlight`, `snipper match`, and `snipper run`
- [x] 3.3 Execute the full test suite with `pytest` and verify all tests pass with 100% success

## 4. Documentation & Agent Skills Rebranding

- [x] 4.1 Update `skill/Instructions.md`, `skill/Definitions.md`, and constraint files to reference `snipper` CLI and the Phase 1 Highlighter engine
- [x] 4.2 Update `skill/findings.schema.json` description references
- [x] 4.3 Update `brainstorm.md` references to reflect the Snipper project identity
