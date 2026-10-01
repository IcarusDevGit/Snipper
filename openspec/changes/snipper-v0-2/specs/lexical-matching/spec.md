## MODIFIED Requirements

### Requirement: Document Ingestion and Section Parsing
The system SHALL ingest an input `.docx` file and parse the document into an ordered list of Questions and a Body text container, tolerating variations in subtitle formatting and extracting optional sub-bullet metadata.

#### Scenario: Parse standard bold and centered delimiters
- **WHEN** an input `.docx` contains a paragraph matching `questions` and a later paragraph matching `body`
- **THEN** the system extracts all text preceding the `body` marker as Questions and subsequent paragraphs as the Body container

#### Scenario: Heading case and style tolerance
- **WHEN** delimiter paragraphs use mixed case, trailing colons, or heading styles (e.g., `QUESTIONS:`, `## Body`)
- **THEN** the parser successfully identifies the boundaries without throwing an error

#### Scenario: Question sub-bullet metadata parsing
- **WHEN** a Question is followed by sub-bullet paragraphs prefixed with `- Keywords:` or `- Concepts:`
- **THEN** the parser extracts and associates those keywords and concepts directly with the preceding Question

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
