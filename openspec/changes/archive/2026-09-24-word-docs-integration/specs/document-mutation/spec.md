## Purpose

Provides in-place Word document mutation and styling to integrate agent answer findings into the document with summary blocks, nested snippet precedence, match bolding, and superscript annotations.

## ADDED Requirements

### Requirement: Questions and Answers Summary Block Generation
The system SHALL insert a formatted summary section before the Body container in the `.docx` document detailing each Question, its assigned highlight color, answering snippets with citation markers, and any consulted web sources.

#### Scenario: All questions answered
- **WHEN** findings contain answering snippets for all questions
- **THEN** each question is listed in the summary section accompanied by its answering snippets and superscript question indicators

#### Scenario: Unanswered questions handling
- **WHEN** findings list one or more questions in `unanswered_questions`
- **THEN** those questions are rendered with `[No answering evidence found in text]` without throwing an error

#### Scenario: Web sources display
- **WHEN** a finding includes one or more URLs in `web_sources`
- **THEN** the cited URLs are listed under the respective question in the summary section

### Requirement: Verbatim Snippet Alignment and Cross-Paragraph Slicing
The system SHALL locate verbatim snippets within the document body using normalized text alignment and slice multi-paragraph snippets across paragraph boundaries.

#### Scenario: Punctuation and whitespace normalization
- **WHEN** a snippet in findings contains straight quotes while the document text uses smart quotes
- **THEN** the system successfully maps the snippet to the exact character range in the source document

#### Scenario: Multi-paragraph snippet partitioning
- **WHEN** a snippet spans across more than one paragraph in the Body
- **THEN** the system applies highlight runs within each respective paragraph without violating Word run boundaries

### Requirement: Nested Snippet Precedence and Overlap Resolution
The system SHALL resolve overlapping snippet intervals by applying the shorter inner span's question color and identifier while retaining the outer question's color and identifier for the surrounding span.

#### Scenario: Shorter answer inside longer answer
- **WHEN** phrase $S_A$ answering $Q_1$ is contained entirely within sentence $S_B$ answering $Q_2$, and $\text{len}(S_A) < \text{len}(S_B)$
- **THEN** $S_A$ is styled with $Q_1$'s color and superscript $¹$, and the remainder of $S_B$ is styled with $Q_2$'s color and superscript $²$

#### Scenario: Multi-question equal span
- **WHEN** a snippet span answers multiple questions equally (e.g., $Q_1$ and $Q_2$)
- **THEN** the span is highlighted with the color of the first question ($Q_1$) and carries combined superscripts (e.g., `¹,²`)

### Requirement: Match Bolding Inside Snippets
The system SHALL render lexical match tokens in bold when they intersect an active answering snippet span while preserving the snippet highlight color.

#### Scenario: Match token inside answer snippet
- **WHEN** a word is tagged as a lexical match and falls inside an answering snippet
- **THEN** that word is rendered in bold font weight and inherits the snippet's highlight color

### Requirement: In-Place Document Mutation Persistence
The system SHALL modify the original `.docx` file in-place, preserving existing document-level metadata, font styles, and formatting outside the modified sections.

#### Scenario: In-place document overwrite
- **WHEN** the mutation pipeline completes execution
- **THEN** the original document file is updated with the summary section and highlights while preserving document structure
