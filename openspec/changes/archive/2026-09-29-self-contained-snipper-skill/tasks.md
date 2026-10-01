## 1. Feature Porting into Skill Scripts

- [x] 1.1 Port `format_as_txt()`, `export_to_txt()`, `.annotated_text` property, and `.export_txt()` helper into `.agents/skills/snipper/scripts/document.py`, and verify syntax and imports
- [x] 1.2 Port the `dump` CLI subcommand and automatic companion `.snipper.txt` synchronization into `.agents/skills/snipper/scripts/cli.py`, and verify `dump` appears in `python .agents/skills/snipper/scripts/cli.py --help`
- [x] 1.3 Create `.agents/skills/snipper/requirements.txt` containing `python-docx>=1.1.0`, `spacy>=3.7.0`, and `PyYAML>=6.0.0`

## 2. Test Suite Relocation & Self-Contained Verification

- [x] 2.1 Create `.agents/skills/snipper/tests/conftest.py` that configures `sys.path` to include `.agents/skills/snipper/scripts`
- [x] 2.2 Relocate the 8 test files (`test_alignment.py`, `test_cli.py`, `test_config.py`, `test_document.py`, `test_findings.py`, `test_highlighter.py`, `test_mutation.py`, `test_nlp.py`) from root `tests/` to `.agents/skills/snipper/tests/` and update module imports from `from snipper.<module>` to `from <module>`
- [x] 2.3 Run `python -m pytest .agents/skills/snipper/tests` and verify all 30 tests pass

## 3. Workflow & Skill Instruction Alignment

- [x] 3.1 Update `.agents/workflows/snipper.md` to reference `python .agents/skills/snipper/scripts/cli.py` for all execution modes
- [x] 3.2 Update `.agents/skills/snipper/SKILL.md` CLI examples to standardize on the self-contained script paths

## 4. Decommission External Scripts & Packaging Artifacts

- [x] 4.1 Delete root `snipper/` directory, `snipper.egg-info/`, `pyproject.toml`, root `requirements.txt`, and root `tests/` directory
- [x] 4.2 Run `python -m pytest .agents/skills/snipper/tests` to confirm full test suite passes with zero external files remaining
- [x] 4.3 Run `python .agents/skills/snipper/scripts/cli.py --help` and verify end-to-end self-contained CLI operation
