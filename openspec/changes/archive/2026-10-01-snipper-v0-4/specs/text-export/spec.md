## MODIFIED Requirements

### Requirement: Paragraph-Annotated Plain-Text Generation
The system SHALL generate a plain text representation of an input `.docx` file containing the body paragraphs annotated with sequential paragraph index markers (`[P0]`, `[P1]`, etc.) directly from the document content without requiring an embedded Questions section.

#### Scenario: Clean paragraph markers in Body
- **WHEN** a document with multiple body paragraphs is exported to plain text
- **THEN** each body paragraph is preceded by its zero-indexed tag (e.g., `[P0]`, `[P1]`) and separated by newlines

#### Scenario: Questions section preservation
- **WHEN** an entry has an associated `<name>.questions.txt` query file
- **THEN** questions and objectives metadata are preserved in the dedicated `<name>.questions.txt` file while the exported `.txt` file focuses purely on body paragraph markers

#### Scenario: Clean document without delimiters
- **WHEN** an input `.docx` contains clean body text without `Questions:` or `Body:` delimiter headings
- **THEN** the plain text is extracted cleanly across all document paragraphs

### Requirement: CLI Text Export Command
The system SHALL provide a CLI command to export the `.docx` document to a `.txt` companion file named `<name>.txt`.

#### Scenario: Default export filename
- **WHEN** the user executes `snipper dump <document.docx>`
- **THEN** the system generates `<document>.txt` alongside the target document and exits with code 0

#### Scenario: Explicit output path
- **WHEN** the user executes `snipper dump <document.docx> --output <path.txt>`
- **THEN** the plain text is written to the specified output path

### Requirement: Automated Companion Generation During Pipeline Execution
The system SHALL automatically generate or refresh the companion `<name>.txt` file during pipeline ingestion.

#### Scenario: Ingestion auto-sync
- **WHEN** `/snipper:snip` or `snipper snip <document.docx>` processes a `.docx` file
- **THEN** the system updates or creates the companion `<name>.txt` file alongside the target `.docx`
