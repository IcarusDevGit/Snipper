## MODIFIED Requirements

### Requirement: Questions and Answers Summary Block Generation
The system SHALL insert a formatted summary section prepended at paragraph 0 (top of document) bounded by explicit start and end delimiters (`=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`), detailing each Question (`Q#`) and Objective (`O#`), its assigned highlight color, answering snippets with citation markers, resolved concepts with approved citations, and keywords. If an existing summary block is detected, it SHALL be replaced cleanly.

#### Scenario: All questions answered
- **WHEN** findings contain answering snippets for questions and objectives
- **THEN** each target item is listed in the summary section at paragraph 0 accompanied by its answering snippets and superscript indicators within the summary block delimiters

#### Scenario: Unanswered questions handling
- **WHEN** findings list one or more questions or objectives in `unanswered_questions` or with empty findings
- **THEN** those targets are rendered with `[No answering evidence found in text]` without throwing an error

#### Scenario: Web sources display
- **WHEN** a finding includes one or more URLs in `web_sources`
- **THEN** the cited URLs are listed under the respective Question or Objective in the summary section

#### Scenario: Concepts and keywords display
- **WHEN** findings include resolved concepts with definitions and target keywords
- **THEN** the summary section renders the concept definitions, chosen citations, and keywords under the respective Question or Objective block

#### Scenario: Idempotent re-mutation replacement
- **WHEN** `snipper hlt` is executed on a `.docx` file that already contains a summary block
- **THEN** the existing summary block between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===` is stripped and replaced with the updated summary block without duplicating content

### Requirement: In-Place Document Mutation Persistence
The system SHALL modify the original `.docx` file in-place, preserving existing document-level metadata, font styles, and formatting outside the modified sections, without requiring the creation of a `.backup.docx` duplicate.

#### Scenario: In-place document overwrite
- **WHEN** the mutation pipeline completes execution
- **THEN** the original document file is updated with the summary section and highlights while `<name>.txt` is maintained as the primary text backup and document structure is preserved
