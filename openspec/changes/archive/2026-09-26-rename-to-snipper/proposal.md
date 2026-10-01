## Why

The project name contains a typographical error ("Highliter" instead of "Highlighter") and does not accurately capture the overarching purpose of the tool: discovering, extracting, and aligning verbatim answer snippets. Renaming the project to **Snipper** establishes a clear conceptual hierarchy where **Snipper** serves as the primary system, while **Highlighter** is formalized as its deterministic, fully code-based Phase 1 engine.

## What Changes

- **Project & CLI Rebranding**: Rename project from `highliter` to `snipper`. The primary command-line tool becomes `snipper`.
- **Typo Correction**: Eliminate all instances of the misspelled `Highliter` / `highliter` across package directories, build configurations, source code, test suites, and documentation, replacing them with `Snipper` (for the overall project and CLI) and `Highlighter` / `highlight` (for the Phase 1 formatting engine).
- **Phase 1 Highlighter Command**: Establish `snipper highlight <file.docx>` as the primary CLI interface for the standalone code-based Highlighter engine, retaining `snipper match` and `snipper run --lexical-only` as aliases.
- **Python Package Reorganization**: Rename package directory `highliter/` to `snipper/` and update `pyproject.toml` metadata, build includes, and console script entry point.
- **Class & Configuration Updates**: Rename `HighliterConfig` to `SnipperConfig` while keeping clean integration with the highlighter engine.
- **Skill & Instructions Update**: Update agent execution protocols in `skill/Instructions.md`, `skill/Definitions.md`, and schema descriptions to reference `snipper` and the `Highlighter` phase.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lexical-matching`: Update the Standalone CLI Execution Guard requirement and scenarios to establish `snipper highlight <file.docx>` as the primary Phase 1 Highlighter invocation alongside compatibility aliases.

## Impact

- **CLI / Entry points**: `highliter` executable replaced with `snipper`.
- **Python Code**: Directory `highliter/` moved to `snipper/`; imports updated throughout source and `tests/`.
- **Build & Packaging**: `pyproject.toml` updated for package name `snipper` and script `snipper = "snipper.cli:main"`.
- **Agent Skill & Specs**: Updates to `skill/Instructions.md`, `skill/findings.schema.json`, and OpenSpec specs.
