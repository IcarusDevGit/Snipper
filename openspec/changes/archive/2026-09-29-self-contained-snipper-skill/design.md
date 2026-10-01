## Context

See `proposal.md` for motivation. Currently, Snipper's implementation is bifurcated between a top-level Python package (`snipper/`) and an Antigravity agent skill (`.agents/skills/snipper/scripts/`). Tests in `tests/` import from `snipper.*`, and `pyproject.toml` registers `snipper` as a pip package. Crucial text companion features (`export_to_txt` and `dump`) were added to `snipper/` but not to `.agents/skills/snipper/scripts/`.

## Goals / Non-Goals

**Goals:**
- Consolidate all Snipper logic, tests, assets, and requirements into `.agents/skills/snipper/`.
- Port `export_to_txt`, `format_as_txt`, `annotated_text`, and `dump` subcommand into `.agents/skills/snipper/scripts/` with 100% feature parity.
- Relocate the entire unit test suite to `.agents/skills/snipper/tests/` and ensure all 30 tests pass.
- Completely remove all root-level scripts, package configurations, and dependencies (`snipper/`, `snipper.egg-info/`, `pyproject.toml`, `requirements.txt`, root `tests/`).
- Standardize all workflow and skill execution commands to use `python .agents/skills/snipper/scripts/cli.py`.

**Non-Goals:**
- Implementing Snipper v0.4 features (e.g., expanded concept modeling or cross-document workflows).
- Supporting pip-installed global `snipper` entry points outside the skill.

## Decisions

### 1. Internal Import Architecture within `.agents/skills/snipper/scripts/`
- **Choice**: Use the existing `_SCRIPT_DIR` sys.path bootstrap pattern across scripts:
  ```python
  _SCRIPT_DIR = Path(__file__).resolve().parent
  if str(_SCRIPT_DIR) not in sys.path:
      sys.path.insert(0, str(_SCRIPT_DIR))
  ```
- **Rationale**: Enables any script (e.g., `cli.py`, `document.py`) to run directly via Python without requiring `pip install` or package management.
- **Alternatives Considered**: Relative imports (`from .config import SnipperConfig`). Rejected because running `python scripts/cli.py` as `__main__` fails on intra-package relative imports when executed as a script.

### 2. Relocating Tests into `.agents/skills/snipper/tests/`
- **Choice**: Move all 8 test files from `tests/` to `.agents/skills/snipper/tests/` and add a `conftest.py` that adds `../scripts` to `sys.path`.
- **Rationale**: Tests are self-contained with the skill. The entire skill can be validated anytime by running `pytest .agents/skills/snipper/tests`.
- **Alternatives Considered**: Deleting tests entirely. Rejected because tests are required to guard against regressions during consolidation.

### 3. Complete Purge of Root-Level Packaging Files
- **Choice**: Delete `c:\Dev\Highliter\snipper/`, `c:\Dev\Highliter\pyproject.toml`, `c:\Dev\Highliter\requirements.txt`, and `c:\Dev\Highliter\snipper.egg-info/`.
- **Rationale**: Enforces that `.agents/skills/snipper` is the sole source of truth and prevents future drift.
- **Dependencies**: Add `.agents/skills/snipper/requirements.txt` declaring `python-docx>=1.1.0`, `spacy>=3.7.0`, and `PyYAML>=6.0.0`.

## Risks / Trade-offs

- **[Risk] Test suite fails after removing `snipper` root package** → **Mitigation**: Introduce `.agents/skills/snipper/tests/conftest.py` that injects `.agents/skills/snipper/scripts` into `sys.path`, and update test imports from `from snipper.x import y` to `from x import y`.
- **[Risk] Path resolution regression for `CustomConstraints.md` and `palette.md`** → **Mitigation**: `.agents/skills/snipper/scripts/config.py` already resolves candidate paths relative to `script_dir.parent`. Verify these paths in `test_config.py`.
- **[Risk] Workflow script breakage** → **Mitigation**: Update `.agents/workflows/snipper.md` and `SKILL.md` to consistently call `python .agents/skills/snipper/scripts/cli.py <command>`.

## Migration Plan

1. **Step 1**: Port missing `export_to_txt`, `format_as_txt`, and `dump` into `.agents/skills/snipper/scripts/`.
2. **Step 2**: Create `.agents/skills/snipper/requirements.txt`.
3. **Step 3**: Relocate tests from `tests/` to `.agents/skills/snipper/tests/` and update imports.
4. **Step 4**: Verify all 30 tests pass via `python -m pytest .agents/skills/snipper/tests`.
5. **Step 5**: Update command paths in `workflows/snipper.md` and `SKILL.md`.
6. **Step 6**: Delete `snipper/`, `snipper.egg-info/`, `pyproject.toml`, `requirements.txt`, and root `tests/`.
7. **Step 7**: Re-run test suite and CLI dry-run to confirm zero regressions.
