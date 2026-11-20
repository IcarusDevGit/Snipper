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
1. For Word (`.docx`): Confirm Microsoft Word does not have `<name>.docx` open, and `<name>.txt` exists as local backup.
2. For Google Drive / Google Docs (`.gdoc`): Mutation is applied directly via Docs API batchUpdate. **No `.txt` files are needed or generated.**

### 2. Execution
Run the highlighter CLI:
```bash
python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx_or_gdoc>"
```
Or specify explicit findings:
```bash
python .agents/skills/snipper/scripts/cli.py hlt "<path/to/document.docx_or_gdoc>" --f "<path/to/findings.json>"
```

### 3. Verification & Idempotency
- The mutator clears any previous summary block between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`.
- The mutator clears previous body run highlight and bold styles before reapplying mutations.
- The summary block is prepended at paragraph 0 detailing target questions (`Q#`) and objectives (`O#`), bullet-point keywords, concept definitions, and spaced quoted snippets with superscript citations (`Q¹`, `O¹`) — without `Snippet:` prefix markers.
- Keywords are highlighted across body paragraphs with target colors, and bolded inside answering snippets.
- Document is saved in-place without duplicate `.backup.docx` bloat.
