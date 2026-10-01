## ADDED Requirements

### Requirement: Lexical Prioritization for Lookup
The system SHALL provide lexical scoring of candidate snippets against query terms to rank and filter candidates when a retrieval limit is specified.

#### Scenario: Rank snippets by keyword overlap
- **WHEN** candidates are evaluated for query terms with `--limit 5`
- **THEN** snippets containing exact and lemmatized term matches are ranked higher and selected for downstream processing

## MODIFIED Requirements

### Requirement: Document Ingestion and Section Parsing
The system SHALL ingest the document body from `<name>.docx` or `<name>.txt` and questions/objectives from `<name>.questions.txt`, extracting targets and sub-bullet metadata without requiring embedded section delimiters inside the `.docx`, while tolerating legacy embedded delimiters when migrating existing documents.

#### Scenario: Parse standard bold and centered delimiters
- **WHEN** an input document uses legacy embedded delimiters (`questions` and `body`)
- **THEN** the system parses the legacy sections and migrates questions into `<name>.questions.txt` and clean body into `<name>.txt`

#### Scenario: Heading case and style tolerance
- **WHEN** delimiter paragraphs or target lines use mixed case or trailing colons (e.g., `Q1:`, `O1:`)
- **THEN** the parser successfully identifies the targets without throwing an error

#### Scenario: Question sub-bullet metadata parsing
- **WHEN** a Question or Objective is followed by sub-bullet paragraphs prefixed with `- Keywords:` or `- Concepts:`
- **THEN** the parser extracts and associates those keywords and concepts directly with the preceding target item

#### Scenario: Ingest decoupled questions file
- **WHEN** processing an entry with an external `<name>.questions.txt` file
- **THEN** the system extracts all questions, objectives, keywords, and concepts from the text file to drive matching against the body

#### Scenario: Default questions file resolution
- **WHEN** a document path is supplied without an explicit questions file path
- **THEN** the system resolves the questions file by replacing the `.docx` extension with `.questions.txt` in the same directory
