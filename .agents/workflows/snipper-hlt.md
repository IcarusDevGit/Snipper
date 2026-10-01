---
description: "Idempotently mutate a Word document in-place with prepended summary block and highlighted keywords and snippets."
---

# /snipper-hlt Workflow

Idempotently mutate a target Word document (`.docx`) in-place using evidence findings, prepending a delimited summary block at paragraph 0 and applying targeted highlights and bolding.

**Input**: Path to target `<name>.docx`.
Optional: `--f <path/to/findings.json>`, `--dry-run`.

---

## Steps

### 1. Pre-Flight Checks
1. Confirm Microsoft Word does not have `<name>.docx` open.
2. Confirm `<name>.txt` exists as the ground-truth text backup.

### 2. Execution
Run the highlighter CLI:
```bash
python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx>"
```
Or specify explicit findings:
```bash
python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx>" --f "<path/to/findings.json>"
```

### 3. Verification & Idempotency
- The mutator clears any previous summary block between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`.
- The mutator clears previous body run highlight and bold styles before reapplying mutations.
- The summary block is prepended at paragraph 0 detailing target questions (`Q#`) and objectives (`O#`), keywords, concept definitions, and snippets with superscript citations (`Q¹`, `O¹`).
- Keywords are highlighted across body paragraphs with target colors, and bolded inside answering snippets.
- Document is saved in-place without duplicate `.backup.docx` bloat.
