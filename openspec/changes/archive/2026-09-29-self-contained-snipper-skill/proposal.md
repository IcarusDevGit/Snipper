## Why

Snipper's codebase currently suffers from architectural fragmentation: core logic is split and diverging between an external root Python package (`snipper/`) and the Antigravity skill directory (`.agents/skills/snipper/scripts/`). Recent capabilities like plain-text export (`export_to_txt`) and the `dump` CLI subcommand exist only in root `snipper/`, whereas standalone execution improvements, `--dry-run`, and skill-relative asset resolution exist only in `.agents/skills/snipper/scripts/`. 

To maintain clean repository boundaries and make Snipper truly portable, all scripts, dependencies, assets, and tests must be 100% self-contained inside `.agents/skills/snipper/`, eliminating all external scripts and package infrastructure from the workspace root.

## What Changes

- **Port Missing Text Export Features**: Add `format_as_txt()`, `export_to_txt()`, and `annotated_text` helper methods to `.agents/skills/snipper/scripts/document.py`.
- **Port CLI Subcommands**: Add the `dump` command and automatic `.snipper.txt` synchronization into `.agents/skills/snipper/scripts/cli.py`.
- **Add Skill-Local Requirements**: Create `.agents/skills/snipper/requirements.txt` containing runtime dependencies (`python-docx`, `spacy`, `PyYAML`).
- **Relocate Test Suite**: Move the test suite from root `tests/` to `.agents/skills/snipper/tests/`, updating imports to target `scripts/` directly so the skill can be verified in isolation.
- **Update Workflow & Skill Invocations**: Standardize execution commands in `.agents/workflows/snipper.md` and `.agents/skills/snipper/SKILL.md` to run `python .agents/skills/snipper/scripts/cli.py`.
- **Remove External Artifacts (**BREAKING**)**: Remove root `snipper/`, `snipper.egg-info/`, `pyproject.toml`, and root `requirements.txt`. External `snipper` pip package entry points will no longer be provided outside the skill.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None (behavioral capabilities `document-mutation`, `lexical-matching`, and `text-export` are preserved unchanged; `skip_specs: true` enabled).

## Impact

- **File Organization**: All Snipper logic resides exclusively in `.agents/skills/snipper/`.
- **CLI Invocations**: Commands are executed via `python .agents/skills/snipper/scripts/cli.py <command>`.
- **Testing**: Tests are executed via `pytest .agents/skills/snipper/tests`.
- **Workspace Cleanliness**: Deletes `snipper/`, `snipper.egg-info/`, `pyproject.toml`, and root `requirements.txt`.
