## MODIFIED Requirements

### Requirement: Standalone CLI Execution Guard
The system SHALL provide a CLI command to run only Phase 1 Highlighter lexical matching, saving the highlighted document and terminating with exit code 0 without invoking any agent.

#### Scenario: Lexical only execution
- **WHEN** the user executes `snipper highlight <file.docx>`, `snipper match <file.docx>`, or `snipper run <file.docx> --lexical-only`
- **THEN** lexical matches are identified and highlighted in the file by the deterministic Highlighter engine, and the process exits immediately with exit code 0 and zero LLM API or agent invocations
