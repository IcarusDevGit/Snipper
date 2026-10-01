# Scope Resolution Specification

## Purpose

Defines query boundary enforcement across Library, Module, and Sub-module hierarchies to control context loading and inherit ancestor metadata.

## Requirements

### Requirement: Query Scope Evaluation
The system SHALL evaluate the specified scope parameter (`local`, `hierarchical`, `global`) for a given target file or directory path, defaulting to `local` when a directory or file is specified, and `global` when omitted.

#### Scenario: Local scope evaluation on module
- **WHEN** the user executes a command with `--scope local` or omits `--scope` while targeting a module directory
- **THEN** the active scope includes all sub-modules, entries, and findings contained within that target module directory, without ascending to parent directories

#### Scenario: Local scope evaluation on sub-module
- **WHEN** the user executes a command with `--scope local` or omits `--scope` while targeting a sub-module directory or specific entry file
- **THEN** the active scope includes only that specific target sub-module directory and its immediate files

#### Scenario: Hierarchical scope evaluation
- **WHEN** the user executes a command with `--scope hierarchical` targeting a sub-module
- **THEN** the active scope includes the target sub-module plus all ancestor module directories and the library root

#### Scenario: Global scope evaluation
- **WHEN** the user executes a command with `--scope global` or omits both `--dir` and `--scope`
- **THEN** the active scope encompasses all modules and sub-modules across the entire library root

### Requirement: Ancestor Metadata Inheritance
The system SHALL aggregate keywords and concepts upward through parent directories when executing under `hierarchical` scope.

#### Scenario: Inherit module and library keywords
- **WHEN** executing under `hierarchical` scope for an entry inside a sub-module
- **THEN** the system loads keywords from `library.keywords.txt` at the root and `module.keywords.txt` at parent module levels, combining them with entry-level keywords

#### Scenario: Inherit parent concepts with citations
- **WHEN** parent directories contain `library.concepts.txt` or `module.concepts.txt`
- **THEN** defined concepts and their mandatory citations are inherited and made available within the sub-module query context

### Requirement: Out-of-Scope Context Pruning
The system SHALL exclude all entries, findings, keywords, and concepts that reside outside the resolved scope boundary.

#### Scenario: Sibling module exclusion
- **WHEN** a query is executed with `local` or `hierarchical` scope targeting SubModule A
- **THEN** sibling SubModule B and unrelated modules are completely omitted from the query and agent prompt context
