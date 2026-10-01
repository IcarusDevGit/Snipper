## 1. Document Model and Sub-Bullet Parser

- [x] 1.1 Add `Concept` dataclass and extend `Question` with `keywords: List[str]` and `concepts: List[Concept]` in `snipper/document.py`
- [x] 1.2 Update `DocumentParser.parse()` in `snipper/document.py` to parse sub-bullet paragraphs (`- Keywords:`, `- Concepts:`) and test parsing in `tests/test_document.py`

## 2. Findings Schema and Data Structures

- [x] 2.1 Update `skill/findings.schema.json` to include `keywords` and `concepts` (with `name`, `definition`, `source_url`)
- [x] 2.2 Update `FindingsData` and `Finding` dataclasses in `snipper/findings.py` to serialize and deserialize `keywords` and `concepts`
- [x] 2.3 Add tests in `tests/test_findings.py` validating finding payloads with keywords and concepts

## 3. Highlighter & Document Mutation Enhancement

- [x] 3.1 Update `DocumentMutator` in `snipper/mutation.py` to render resolved concepts, source URLs, and keywords in the summary section
- [x] 3.2 Update `DocumentHighlighter` and `DocumentMutator` to highlight and bold targeted question keywords within snippet spans rather than blind whole-document nouns
- [x] 3.3 Add mutation and styling tests in `tests/test_mutation.py` and `tests/test_highlighter.py` verifying targeted keyword highlighting

## 4. Agent Protocols & Documentation

- [x] 4.1 Update `skill/Instructions.md` to define the `Context -> Answers -> Keywords -> Highlighter` execution protocol and interactive web source selection
- [x] 4.2 Update `skill/GlobalConstraints.md` and `skill/Definitions.md` with Concept and Keyword definitions, mandatory agent keyword determination, and exhaustive multi-snippet requirements
- [x] 4.3 Update `tests/test_cli.py` to test end-to-end pipeline execution with concepts and keywords, and verify with `pytest`

