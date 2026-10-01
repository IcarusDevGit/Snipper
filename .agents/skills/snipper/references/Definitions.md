# SPEC: DEFINITIONS
DOCUMENT_VERSION: 2.1.0
TARGET_AUDIENCE: AGENT_SYSTEM

## 1. CORE ENTITIES

### 1.1 BODY
* **TYPE**: Source text container (`str`).
* **SEMANTICS**: The target text within the input document (`.docx`) evaluated for answers.
* **INVARIANT**: Preserved in-place within the document; never truncated, reordered, or synthesized.

### 1.2 TARGETS (QUESTIONS & OBJECTIVES)
* **TYPE**: Ordered sequence of target queries (`List[Target]`).
* **IDENTIFIERS**: String target identifiers: Questions (`Q1`, `Q2`, etc.) and Objectives (`O1`, `O2`, etc.).
* **ASSOCIATION**: Each Target maps 1:1 to an assigned `COLOR`.
* **METADATA**: Targets MAY be followed by `- Keywords:` and `- Concepts:` sub-bullet items.

### 1.3 MATCHES
* **TYPE**: Lexical token occurrences in `BODY` matching targeted question/objective `KEYWORDS` (or target noun lemmas if keywords are not yet resolved).
* **LINGUISTIC_SCOPE**:
  * Parts of Speech: `NOUN`, `PROPN` (Proper Noun) or exact keyword terms.
  * Exclusions: Stop words (`is_stop == True`), verbs (`VERB`), prepositions (`ADP`), conjunctions (`CCONJ`, `SCONJ`).
  * Normalization: Lemmatization (`token.lemma_.lower()`). Supports English (`en_core_web_sm`) and Brazilian Portuguese (`pt_core_news_sm`).
* **DETERMINATION**: Programmatic execution (Code / Highlighter / Mutator). Targeted to keywords inside snippet spans.

### 1.4 SNIPPETS
* **TYPE**: Verbatim text spans (`str`) extracted from `BODY` providing factual answers or evidence for one or more `TARGETS`.
* **CARDINALITY**: A snippet MAY satisfy $\ge 1$ target simultaneously. Multiple snippets SHOULD be gathered to answer a target thoroughly.
* **GRANULARITY**: Full contiguous sentences or paragraphs. Sub-sentence clauses are permitted only when answering a distinct sub-target.
* **INTEGRITY**: Character-for-character identical to the source span in `BODY`. Zero alteration.

### 1.5 IDENTIFIERS
* **TYPE**: Superscript Unicode glyphs (e.g., `Q¹`, `O¹`, `Q¹,O¹` or `¹`, `²`).
* **SEMANTICS**: Appended to snippets in the annotated `BODY` referencing the target identifier(s) answered by that span.

### 1.6 COLORS & PALETTE
* **PALETTE_TYPES**:
  * `hex`: 6-character hex color codes (`#RRGGBB`), rendered in Word XML as `<w:shd w:val="clear" w:color="auto" w:fill="RRGGBB"/>`.
  * `named`: Word-native highlight color strings (`w:highlight`), e.g., `yellow`, `turquoise`, `bright_green`, `pink`, `light_gray`.
* **ALLOCATION_LOGIC**:
  * $|Questions| \le |Palette|$: Assigned sequentially or randomly per configuration.
  * $|Questions| > |Palette|$: Colors cycle via modulo ($Index \pmod{|Palette|}$).

### 1.7 KEYWORDS
* **TYPE**: Salient terms essential for answering a Question (`List[str]`).
* **SPECIFICATION**: Designated as sub-bullet under Question (e.g., `- Keywords: inflation, rate`) or determined by the agent from context if omitted by the user.
* **ROLE**: Direct targets for highlighting and bolding within answering snippet spans.

---

## 2. STRUCTURAL & OVERLAP SPECIFICATIONS

### 2.1 IN-PLACE DOCUMENT MUTATION
* The system loads the target input `.docx` file and modifies it directly in-place.
* Document-level styles, non-body sections, headers, and metadata MUST be preserved.
* Output is saved to the input path or designated target without generating an unstyled detached document.
* Mutation is idempotent: summary block is prepended at paragraph 0 wrapped between `=== SNIPPER SUMMARY START ===` and `=== SNIPPER SUMMARY END ===`. Re-running clears previous summary blocks and body highlight styling before applying updated findings.

### 2.2 KEYWORDS & MATCHES INSIDE AND OUTSIDE SNIPPETS
* If a `KEYWORD` or `MATCH` token falls within the character range of an answering `SNIPPET`:
  * Font Weight: **BOLD** (`run.bold = True`).
  * Background Color: Inherits the enclosing `SNIPPET` highlight color.
* Vetted question keywords occurring outside answering `SNIPPET` spans ARE highlighted across the `BODY` with their respective Question's assigned color (normal font weight), allowing users to locate keywords across the entire document without blind noun noise.

### 2.3 NESTED SNIPPETS
* Given span $S_A$ (answering $Q_A$) and span $S_B$ (answering $Q_B$) where $S_A \subset S_B$:
  * Inner span ($S_A$ where $\text{len}(S_A) < \text{len}(S_B)$): Rendered with $Q_A$'s color and $Q_A$'s identifier.
  * Surrounding outer span ($S_B \setminus S_A$): Rendered with $Q_B$'s color and $Q_B$'s identifier.

### 2.4 MULTI-QUESTION EQUAL SPANS
* If span $S$ answers both $Q_A$ and $Q_B$ ($A < B$):
  * Color: Highlighted with $Q_A$'s assigned color.
  * Identifiers: Appended with combined superscripts (e.g., `¹,²`).

