## Why

AI agents currently cannot read binary `.docx` files natively. Dreading the document repeatedly via custom Python scripts is slow and token-inefficient, while converting documents to Markdown introduces formatting syntax (such as `**`, `*`, `#`, or backticks) that can contaminate verbatim string extraction and break character-for-character snippet alignment (`C-TXT-02`). Generating a lightweight, paragraph-annotated `.txt` copy directly from the `.docx` source gives agents an instant, zero-clutter text representation with guaranteed character alignment.

## What Changes

- **Plain-Text Export Engine**: Introduce functionality in `DocumentParser` / exporter to generate a clean, unformatted text representation (`<filename>.snipper.txt`) containing the parsed `Questions` section and paragraph-delimited `Body` text.
- **Explicit Paragraph Indexing**: Body paragraphs in the `.txt` copy are annotated with sequential index tags (e.g., `[P0]`, `[P1]`), giving agents exact spatial awareness corresponding directly to `body_paragraphs` in the Python document model.
- **Zero-Clutter Verbatim Fidelity**: The exported text mirrors `paragraph.text` from `python-docx` character-for-character, with no Markdown styling tags, synthetic asterisks, or escaping artifacts.
- **CLI Export Interface**: Add a CLI command (e.g. `snipper dump <doc.docx>` or `snipper export <doc.docx>`) to generate the `.txt` companion file on demand, and automatically make it available during document processing.

## Capabilities

### New Capabilities
- `text-export`: Covers deterministic extraction of questions and paragraph-annotated body text from `.docx` files into lightweight `.txt` companion files with zero formatting clutter.

### Modified Capabilities
None.

## Impact

- **Document Model (`snipper/document.py`)**: Add text formatting and export utilities for parsed documents.
- **CLI (`snipper/cli.py`)**: Add `dump` (or `export`) subcommand to generate `.txt` companion files.
- **Test Suite (`tests/test_document.py`, `tests/test_cli.py`)**: Add tests verifying exact character fidelity, paragraph marker formatting, and CLI command execution.
