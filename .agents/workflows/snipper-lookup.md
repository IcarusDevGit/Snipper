---
description: "Query and retrieve candidate snippets across scoped findings files with optional lexical pre-filtering and agent evaluation."
---

# /snipper-lookup Workflow

Search and retrieve candidate answer snippets across `.findings.json` files within an enforced directory scope (`local`, `hierarchical`, `global`).

**Input**: Search query string.
Optional:
- `--dir <path>`: Root directory for scope (Module or Sub-module directory)
- `--scope <local|hierarchical|global>`: Scoping mode (default: `local`)
- `--limit <N>`: Maximum number of candidates to return (triggers deterministic lexical pre-filtering)

---

## Steps

### 1. Scope Boundary Enforcement
- `local`: Subtree rooted at `--dir`. If `--dir` is a Module, all child sub-modules enter scope. If `--dir` is a Sub-module, only that sub-module is scoped. Never ascends.
- `hierarchical`: Scopes subtree rooted at `--dir` and ascends upward to inherit ancestor keywords (`module.keywords.txt`, `library.keywords.txt`).
- `global`: Scopes all modules and sub-modules across the library.

### 2. Execution
Run the lookup CLI:
```bash
# Targeted search with lexical ranking capped at top N:
python .agents/skills/snipper/scripts/cli.py lookup "<query>" --dir "<path>" --scope local --limit 5

# Comprehensive evaluation across all scoped candidates via LLM agent:
python .agents/skills/snipper/scripts/cli.py lookup "<query>" --dir "<path>" --scope local
```

### 3. Review Results
Output displays standardized snippet cards:
```text
------------------------------------------------------------
[Module/SubModule/report.docx] [P12] (Target: Q1)
Matched Keywords: risk, exposure
"Verbatim snippet text from findings payload..."
------------------------------------------------------------
```
The agent reviews matching candidate cards to evaluate context and cite exact document sources.
