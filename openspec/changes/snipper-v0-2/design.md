## Context

The v0.1 architecture executed blind whole-document noun matching prior to semantic discovery, leading to noisy formatting. Moreover, agents frequently stopped search after locating a single minimal clause. Snipper v0.2 establishes a concept- and keyword-driven pipeline (`Context -> Answers -> Keywords -> Highlighter`) where questions can have sub-bullet metadata, agents must determine keywords if omitted, web search for concepts offers interactive source selection, and Highlighter only renders vetted keywords in context.

See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Extend `DocumentParser` to parse `- Keywords:` and `- Concepts:` sub-bullet paragraphs beneath questions.
- Extend `Question` data model in `snipper/document.py` to store `keywords: List[str]` and `concepts: List[Concept]`.
- Update `findings.schema.json` to validate `keywords` (array of strings) and `concepts` (array of concept objects with definitions and selected sources).
- Update agent execution instructions in `skill/Instructions.md`, `skill/Definitions.md`, and `skill/GlobalConstraints.md`:
  - Mandatory keyword determination by the agent when omitted by the user.
  - Interactive source selection protocol when web search is requested for a concept.
  - Exhaustive multi-snippet gathering across 100% of the body text.
- Update `DocumentMutator` to render concepts, approved sources, and keywords in the summary block.
- Update `DocumentHighlighter` to highlight/bold only validated keywords inside snippet context, eliminating blind whole-document noun scanning.
- Provide comprehensive test coverage for sub-bullet parsing, schema serialization, and mutated docx output.

**Non-Goals:**
- Creating a GUI for source selection (interactive CLI/agent prompting is used).
- Modifying the underlying python-docx run-splitting XML engine.

## Decisions

### 1. Resilient Sub-Bullet Parsing
- **Choice**: In `DocumentParser.parse()`, after recognizing a Question paragraph, inspect subsequent paragraphs until the next Question or the Body delimiter. Check for sub-bullet prefixes:
  - `^\s*[-*•]\s*(?:keywords?|palavras-chave)\s*:\s*(.+)$`
  - `^\s*[-*•]\s*(?:concepts?|conceitos?)\s*:\s*(.+)$`
- **Rationale**: Forgiving regex allows both English and Portuguese labels, bullet variations (`-`, `*`, `•`), and comma/semicolon delimited items.

### 2. Concept Model & Web Search Flags
- **Choice**: Model concepts with a `Concept` dataclass: `name: str`, `web_search: bool = False`. If a concept string includes `(web: true)` or `(web)`, set `web_search = True`.
- **Rationale**: Clean, readable notation in Word documents that is easily identified by both regex and LLMs.

### 3. Findings Schema Expansion
- **Choice**: Add `keywords` and `concepts` to each finding or at root level in `findings.schema.json`:
  ```json
  "keywords": { "type": "array", "items": { "type": "string" } },
  "concepts": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["name", "definition"],
      "properties": {
        "name": { "type": "string" },
        "definition": { "type": "string" },
        "source_url": { "type": "string" }
      }
    }
  }
  ```
- **Rationale**: Preserves structured validation and enables DocumentMutator to render rich definitions and citations cleanly.

### 4. Keyword Highlighting vs Blind Noun Highlighting
- **Choice**: In `DocumentHighlighter` and `DocumentMutator`, highlight vetted question keywords across the entire body text with the respective question's color. Inside answering snippet spans, those keywords are rendered in **bold**. Deprecate blind whole-document noun scanning from general question words.
- **Rationale**: Ensures vetted keywords are visually tracked across the entire document without generating false-positive noun highlights from unvetted question phrasing.

## Risks / Trade-offs

- **Risk: Word documents with non-standard bullet indentation**  
  *Mitigation*: Strip leading whitespace and support various bullet symbols (`-`, `*`, `•`, numbered sub-bullets).
- **Risk: Agent omitting keywords despite instructions**  
  *Mitigation*: Schema validation can enforce `minItems: 1` on `keywords` for each answered question.
