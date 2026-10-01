# Lexical Matching Specification

## Purpose

Provides deterministic document ingestion, multilingual NLP lemmatization, and in-place Word highlight styling to link question nouns with body text without requiring an agent.

## Requirements

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
The system SHALL mutate the input `.docx` document in-place by applying highlight formatting directly to runs that match vetted question keywords and answer snippets without blind noun noise.

#### Scenario: Hex shading application
- **WHEN** `palette_mode` is set to `hex`
- **THEN** matched runs are styled with `<w:shd w:fill="{HEX}"/>` corresponding to the question's assigned color

#### Scenario: Palette cycling
- **WHEN** the number of questions exceeds the number of colors in the palette
- **THEN** color assignment cycles sequentially using modulo indexing

#### Scenario: Targeted keyword highlighting without blind noun noise
- **WHEN** lexical matching and document highlighting are executed
- **THEN** validated question keywords are highlighted across the body text with their respective question's color (both inside and outside snippet spans), and bolded within snippet spans, avoiding blind whole-document noun matching

### Requirement: Standalone CLI Execution Guard
The system SHALL provide a CLI command to run only Phase 1 Highlighter lexical matching, saving the highlighted document and terminating with exit code 0 without invoking any agent.

#### Scenario: Lexical only execution
- **WHEN** the user executes `snipper highlight <file.docx>`, `snipper match <file.docx>`, or `snipper run <file.docx> --lexical-only`
- **THEN** lexical matches are identified and highlighted in the file by the deterministic Highlighter engine, and the process exits immediately with exit code 0 and zero LLM API or agent invocations

### Requirement: Lexical Prioritization for Lookup
The system SHALL provide lexical scoring of candidate snippets against query terms to rank and filter candidates when a retrieval limit is specified.

#### Scenario: Rank snippets by keyword overlap
- **WHEN** candidates are evaluated for query terms with `--limit 5`
- **THEN** snippets containing exact and lemmatized term matches are ranked higher and selected for downstream processing
