# Findings Lookup Specification

## Purpose

Searches and retrieves contextually relevant snippets across existing findings files within a defined scope boundary using hybrid lexical and semantic evaluation.

## Requirements

### Requirement: Scoped Findings Scanning
The system SHALL scan all `.findings.json` files within the resolved query scope (`local`, `hierarchical`, `global`) for snippets relevant to a specified question (`--q`) or objective (`--o`).

#### Scenario: Lookup in local scope
- **WHEN** the user executes `/snipper:lookup --q "encryption" --dir Security/access.docx`
- **THEN** only findings files within `Security/` are inspected for matching snippets

#### Scenario: Lookup in global scope
- **WHEN** the user executes `/snipper:lookup --o "telemetry endpoints" --scope global`
- **THEN** all `.findings.json` files across the entire Library are evaluated

### Requirement: Conditional Lexical Pre-Filtering
The system SHALL execute deterministic lexical keyword matching to prioritize candidates before agent evaluation only when a `--limit` parameter is provided.

#### Scenario: Limit specified triggers lexical ranking
- **WHEN** the lookup command is invoked with `--limit 5`
- **THEN** the system lexically scores candidate snippets against query terms to select the top candidates for semantic evaluation, stopping when the limit is reached

#### Scenario: Limit omitted evaluates all candidates
- **WHEN** the lookup command is invoked without `--limit`
- **THEN** the system skips lexical pre-filtering and evaluates all candidate snippets in scope for relevance

### Requirement: Standardized Snippet Card Display
The system SHALL display retrieved snippets with provenance details including source entry path, spatial paragraph coordinate (`[P#]`), and target identifier.

#### Scenario: Snippet card format
- **WHEN** relevant snippets are returned by `/snipper:lookup`
- **THEN** each result is formatted as a card displaying `[<path> :: P#] (Matched for <target_id>)`, followed by the verbatim snippet text and associated keywords
