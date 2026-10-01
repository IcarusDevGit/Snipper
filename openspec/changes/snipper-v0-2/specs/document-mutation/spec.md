## MODIFIED Requirements

### Requirement: Questions and Answers Summary Block Generation
The system SHALL insert a formatted summary section before the Body container in the `.docx` document detailing each Question, its assigned highlight color, answering snippets with citation markers, resolved concepts with approved web sources, and question keywords.

#### Scenario: All questions answered
- **WHEN** findings contain answering snippets for all questions
- **THEN** each question is listed in the summary section accompanied by its answering snippets and superscript question indicators

#### Scenario: Unanswered questions handling
- **WHEN** findings list one or more questions in `unanswered_questions`
- **THEN** those questions are rendered with `[No answering evidence found in text]` without throwing an error

#### Scenario: Web sources display
- **WHEN** a finding includes one or more URLs in `web_sources`
- **THEN** the cited URLs are listed under the respective question in the summary section

#### Scenario: Concepts and keywords display
- **WHEN** findings include resolved concepts with definitions and question keywords
- **THEN** the summary section renders the concept definitions, chosen web source citations, and question keywords under the respective Question block

### Requirement: Match Bolding Inside Snippets
The system SHALL render question keywords and lexical match tokens in bold when they intersect an active answering snippet span while preserving the snippet highlight color.

#### Scenario: Match token inside answer snippet
- **WHEN** a word is tagged as a lexical match and falls inside an answering snippet
- **THEN** that word is rendered in bold font weight and inherits the snippet's highlight color

#### Scenario: Keyword bolding inside answer snippet
- **WHEN** a validated question keyword occurs within an answering snippet span
- **THEN** that keyword is rendered in bold font weight and inherits the snippet's highlight color
