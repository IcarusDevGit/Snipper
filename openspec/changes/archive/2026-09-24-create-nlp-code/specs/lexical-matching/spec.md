## Purpose

Provides deterministic document ingestion, multilingual NLP lemmatization, and in-place Word highlight styling to link question nouns with body text without requiring an agent.

## ADDED Requirements

### Requirement: Document Ingestion and Section Parsing
The system SHALL ingest an input `.docx` file and parse the document into an ordered list of Questions and a Body text container, tolerating variations in subtitle formatting.

#### Scenario: Parse standard bold and centered delimiters
- **WHEN** an input `.docx` contains a paragraph matching `questions` and a later paragraph matching `body`
- **THEN** the system extracts all text preceding the `body` marker as Questions and subsequent paragraphs as the Body container

#### Scenario: Heading case and style tolerance
- **WHEN** delimiter paragraphs use mixed case, trailing colons, or heading styles (e.g., `QUESTIONS:`, `## Body`)
- **THEN** the parser successfully identifies the boundaries without throwing an error

### Requirement: Multilingual NLP Pipeline Selection
The system SHALL support natural language tokenization and lemmatization for both English and Brazilian Portuguese, selecting the appropriate model based on configuration or document text.

#### Scenario: English document processing
- **WHEN** the document language is English or configured as `en`
- **THEN** the system uses the English model pipeline (`en_core_web_sm`) for tokenization and POS tagging

#### Scenario: Brazilian Portuguese document processing
- **WHEN** the document text is identified as Brazilian Portuguese or configured as `pt-BR`
- **THEN** the system uses the Portuguese model pipeline (`pt_core_news_sm`) for tokenization and POS tagging

### Requirement: Deterministic Noun Lemma Extraction
The system SHALL extract base lemmas for nouns and proper nouns from each question while excluding stop words, verbs, and prepositions.

#### Scenario: Plural and singular lemma alignment
- **WHEN** a question contains plural nouns (e.g., "patents", "investors")
- **THEN** the system extracts their base lemmas (`patent`, `investor`) alongside proper names

#### Scenario: Syntactic exclusion
- **WHEN** a question contains verbs, prepositions, or stop words (e.g., "Where did", "run", "in")
- **THEN** those tokens are strictly excluded from the match targets

#### Scenario: Proper nouns only filter
- **WHEN** `proper_nouns_only` is enabled in configuration
- **THEN** only proper nouns (`PROPN`) are extracted, ignoring common nouns

### Requirement: In-Place Document Highlighting
The system SHALL mutate the input `.docx` document in-place by applying highlight formatting directly to runs that match question noun lemmas.

#### Scenario: Hex shading application
- **WHEN** `palette_mode` is set to `hex`
- **THEN** matched runs are styled with `<w:shd w:fill="{HEX}"/>` corresponding to the question's assigned color

#### Scenario: Palette cycling
- **WHEN** the number of questions exceeds the number of colors in the palette
- **THEN** color assignment cycles sequentially using modulo indexing

### Requirement: Standalone CLI Execution Guard
The system SHALL provide a CLI command to run only Phase 1 lexical matching, saving the highlighted document and terminating with exit code 0 without invoking any agent.

#### Scenario: Lexical only execution
- **WHEN** the user executes `highliter run <file.docx> --lexical-only` or `highliter match <file.docx>`
- **THEN** lexical matches are identified and highlighted in the file, and the process exits immediately with zero LLM API or agent invocations
