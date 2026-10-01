## Why

The current pipeline blindly highlights all question nouns across the entire document before any semantic discovery occurs, producing heavy visual noise. Furthermore, agents frequently truncate evidence collection after finding a single terse sentence. To resolve this, Snipper v0.2 introduces a concept- and keyword-driven architecture (`Context -> Answers -> Keywords -> Highlighter`) supporting sub-bullet metadata under questions, interactive web source selection for concepts, exhaustive multi-snippet discovery, and targeted keyword-only document highlighting.

## What Changes

- **Question Hierarchy with Keywords & Concepts**: In the `.docx` document, questions support optional sub-bullets: `- Keywords: ...` and `- Concepts: ...`.
- **Agent Keyword Invariant**: If keywords are omitted by the user, the agent is strictly required to determine them from the context necessary to answer each question.
- **Concept Definition & Interactive Web Selection**: Concepts are defined by the agent using the document body, or through external web search when annotated (e.g., `(web: true)`). When web search is requested, all discovered sources are listed and the user interactively selects the preferred source.
- **Exhaustive Multi-Snippet Gathering**: The agent performs a complete pass across the body, collecting all relevant sentences and paragraphs for each question rather than halting after the first minimal clause.
- **Elimination of Blind Noun Highlighting**: The code-based Highlighter replaces blind question-noun matching with targeted highlighting and bolding of vetted keywords within the answer context.
- **Enhanced Summary Section**: The in-place Word document summary block displays resolved concepts, approved web sources, question keywords, and rich verbatim answer snippets.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lexical-matching`: Update document parsing to extract sub-bullet `- Keywords:` and `- Concepts:`, and replace whole-document blind noun matching with targeted keyword matching.
- `document-mutation`: Expand the summary block to render concept definitions and approved web sources alongside answering snippets, and bold validated keywords inside snippet runs.

## Impact

- **Document Parser (`snipper.document`)**: Enhanced to parse sub-bullet lines beneath questions (`- Keywords:`, `- Concepts:`).
- **Findings Schema (`skill/findings.schema.json`)**: Updated to include `keywords` and `concepts` (with definition and source URL).
- **Highlighter Engine (`snipper.highlighter`, `snipper.nlp`, `snipper.mutation`)**: Updated to highlight and bold vetted keywords rather than all question nouns.
- **Agent Protocols (`skill/Instructions.md`, `skill/GlobalConstraints.md`, `skill/Definitions.md`)**: Instructs agent on concept resolution, interactive source selection, mandatory keyword determination, and exhaustive multi-snippet collection.
