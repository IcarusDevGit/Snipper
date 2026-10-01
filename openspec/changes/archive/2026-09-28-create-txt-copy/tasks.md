## 1. Document Model Text Export

- [x] 1.1 Implement `export_to_txt()` and text serialization helper in `snipper/document.py` to render `=== QUESTIONS ===` and `=== BODY ===` with `[P{idx}]` paragraph tags, and verify with unit tests in `tests/test_document.py`
- [x] 1.2 Add unit tests in `tests/test_document.py` verifying character-for-character verbatim fidelity across punctuation, quotes, and symbols without markdown styling artifacts

## 2. CLI Subcommand & Pipeline Integration

- [x] 2.1 Add `dump` subcommand in `snipper/cli.py` supporting `snipper dump <document.docx> [--output <path>]`, and verify CLI argument parsing and file output in `tests/test_cli.py`
- [x] 2.2 Wire automatic companion `<filename>.snipper.txt` synchronization into `run_pipeline` in `snipper/cli.py`, and verify with integration tests in `tests/test_cli.py`

## 3. Agent Protocol & Documentation

- [x] 3.1 Update `.agents/skills/snipper/SKILL.md` and `.agents/workflows/snipper.md` to instruct agents to read `<filename>.snipper.txt` and treat `[P#]` markers as spatial coordinates rather than verbatim text
