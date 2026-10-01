# Questions and Objectives Parsing Specification

## Purpose

Parses decoupled plain-text query files containing Questions and Objectives with keywords and concepts into structured targets for semantic extraction.

## Requirements

### Requirement: Questions and Objectives File Ingestion
The system SHALL parse questions and objectives from an external `.txt` file (conventionally `<name>.questions.txt`) where lines prefixed with `Q<id>:` are parsed as Questions and lines prefixed with `O<id>:` are parsed as Objectives.

#### Scenario: Ingest mixed questions and objectives
- **WHEN** a questions file contains both `Q1: ...` and `O1: ...` definitions
- **THEN** the parser extracts both items as distinct query targets retaining their unique identifier types

#### Scenario: Tolerate punctuation and casing variations
- **WHEN** target headers use varying whitespace or formats such as `q1:`, `Q2 :`, `O1:`, or `Objective 1:`
- **THEN** the parser normalizes the header to its canonical `Q#` or `O#` format

### Requirement: Sub-Bullet Keywords and Concepts Extraction
The system SHALL parse subsequent sub-bullet lines under any Question or Objective for `- Keywords:` and `- Concepts:`.

#### Scenario: Extract keywords for objective
- **WHEN** an Objective `O1` is followed by `- Keywords: audit, syslog, tls`
- **THEN** the extracted keywords list for `O1` contains `["audit", "syslog", "tls"]`

#### Scenario: Extract concept with citation requirement
- **WHEN** a Question or Objective is followed by `- Concepts: Data Privacy`
- **THEN** the system registers `Data Privacy` as a required concept target to be defined and cited in findings

### Requirement: Findings String Identifier Mapping
The system SHALL record target references in emitted findings payloads using string IDs (`target_ids: ["Q1", "O1"]`) instead of pure integer indexes.

#### Scenario: Multi-target answering snippet
- **WHEN** a single snippet provides answering context for both Question `Q1` and Objective `O1`
- **THEN** the finding payload records `target_ids: ["Q1", "O1"]`
