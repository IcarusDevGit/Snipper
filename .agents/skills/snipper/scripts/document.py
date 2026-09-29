"""Document ingestion, resilient section parsing, and question indexing."""

from dataclasses import dataclass, field
from pathlib import Path
import random
import re
import sys
from typing import List, Optional, Tuple
import docx
from docx.text.paragraph import Paragraph

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig


QUESTIONS_REGEX = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*|__)?(?:questions?|perguntas?)(?:\*\*|__)?\s*:?\s*$",
    re.IGNORECASE,
)
BODY_REGEX = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*|__)?(?:body|corpo|texto)(?:\*\*|__)?\s*:?\s*$",
    re.IGNORECASE,
)


KEYWORDS_REGEX = re.compile(
    r"^\s*[-*•]\s*(?:keywords?|palavras-chave)\s*:\s*(.+)$",
    re.IGNORECASE,
)
CONCEPTS_REGEX = re.compile(
    r"^\s*[-*•]\s*(?:concepts?|conceitos?)\s*:\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class Concept:
    name: str
    web_search: bool = False
    definition: Optional[str] = None
    source_url: Optional[str] = None


@dataclass
class Question:
    id: int
    text: str
    paragraph_idx: int
    color: str
    keywords: List[str] = field(default_factory=list)
    concepts: List[Concept] = field(default_factory=list)


@dataclass
class ParsedDocument:
    doc: docx.Document
    file_path: Path
    questions_header_idx: int
    body_header_idx: int
    questions: List[Question] = field(default_factory=list)
    body_paragraphs: List[Tuple[int, Paragraph]] = field(default_factory=list)

    @property
    def body_text(self) -> str:
        return "\n".join(p.text for _, p in self.body_paragraphs)

    @property
    def annotated_text(self) -> str:
        return format_as_txt(self)

    def export_txt(self, output_path: Optional[Path | str] = None) -> Path:
        return export_to_txt(self, output_path)


class DocumentParser:
    """Parses a .docx file into structured Questions and Body containers."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def parse(self, file_path: Path | str) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Input document not found: {path}")

        doc = docx.Document(path)
        paragraphs = doc.paragraphs

        questions_idx: Optional[int] = None
        body_idx: Optional[int] = None

        for idx, p in enumerate(paragraphs):
            text = p.text.strip()
            if not text:
                continue

            if questions_idx is None and QUESTIONS_REGEX.match(text):
                questions_idx = idx
                continue

            if questions_idx is not None and body_idx is None and BODY_REGEX.match(text):
                body_idx = idx
                break

        if questions_idx is None:
            raise ValueError("Could not locate 'Questions' section in document.")
        if body_idx is None:
            raise ValueError("Could not locate 'Body' section in document.")
        if body_idx <= questions_idx:
            raise ValueError("'Body' section must appear after 'Questions' section.")

        # Extract Questions with optional Keywords and Concepts sub-bullets
        raw_questions: List[dict] = []
        for idx in range(questions_idx + 1, body_idx):
            raw_text = paragraphs[idx].text.strip()
            if not raw_text:
                continue

            # If summary block was already inserted prior to Body, stop reading questions
            if re.match(r"^\s*questions\s*&\s*answers\s*$", raw_text, re.IGNORECASE):
                break

            # Check for Keywords sub-bullet
            kw_match = KEYWORDS_REGEX.match(raw_text)
            if kw_match and raw_questions:
                kw_content = kw_match.group(1).strip()
                items = [k.strip() for k in re.split(r"[,;]", kw_content) if k.strip()]
                raw_questions[-1]["keywords"].extend(items)
                continue

            # Check for Concepts sub-bullet
            concept_match = CONCEPTS_REGEX.match(raw_text)
            if concept_match and raw_questions:
                concept_content = concept_match.group(1).strip()
                items = [c.strip() for c in re.split(r"[,;]", concept_content) if c.strip()]
                for item in items:
                    web_search = bool(re.search(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", item, re.IGNORECASE))
                    clean_name = re.sub(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", "", item, flags=re.IGNORECASE).strip()
                    raw_questions[-1]["concepts"].append(Concept(name=clean_name, web_search=web_search))
                continue

            # Strip leading list markers like "1.", "1 -", "-", "*"
            cleaned = re.sub(r"^(?:\d+[\.\-\)]\s*|[\*\-\•]\s*)", "", raw_text).strip()
            if cleaned:
                raw_questions.append({
                    "p_idx": idx,
                    "text": cleaned,
                    "keywords": [],
                    "concepts": [],
                })

        # Assign colors
        palette = self.config.palette
        palette_len = len(palette)
        questions: List[Question] = []

        if self.config.palette_order == "random" and palette_len >= len(raw_questions):
            assigned_colors = random.sample(palette, len(raw_questions))
        else:
            assigned_colors = [palette[i % palette_len] for i in range(len(raw_questions))]

        for q_num, (q_data, color) in enumerate(zip(raw_questions, assigned_colors), start=1):
            questions.append(
                Question(
                    id=q_num,
                    text=q_data["text"],
                    paragraph_idx=q_data["p_idx"],
                    color=color,
                    keywords=q_data["keywords"],
                    concepts=q_data["concepts"],
                )
            )

        # Extract Body paragraphs
        body_paragraphs: List[Tuple[int, Paragraph]] = []
        for idx in range(body_idx + 1, len(paragraphs)):
            body_paragraphs.append((idx, paragraphs[idx]))

        return ParsedDocument(
            doc=doc,
            file_path=path,
            questions_header_idx=questions_idx,
            body_header_idx=body_idx,
            questions=questions,
            body_paragraphs=body_paragraphs,
        )


def format_as_txt(parsed: ParsedDocument) -> str:
    """Formats a ParsedDocument into zero-clutter plain text with paragraph tags."""
    lines: List[str] = ["=== QUESTIONS ==="]
    for q in parsed.questions:
        lines.append(f"{q.id}. {q.text}")
        if q.keywords:
            lines.append(f"   - Keywords: {', '.join(q.keywords)}")
        if q.concepts:
            c_strs = [
                f"{c.name} (web: true)" if c.web_search else c.name
                for c in q.concepts
            ]
            lines.append(f"   - Concepts: {', '.join(c_strs)}")

    lines.append("")
    lines.append("=== BODY ===")
    for i, (_, p_obj) in enumerate(parsed.body_paragraphs):
        lines.append(f"[P{i}] {p_obj.text}")

    return "\n".join(lines) + "\n"


def export_to_txt(parsed: ParsedDocument, output_path: Optional[Path | str] = None) -> Path:
    """Exports the parsed document as a lightweight .snipper.txt companion file."""
    if output_path:
        out = Path(output_path)
    else:
        out = parsed.file_path.with_name(f"{parsed.file_path.stem}.snipper.txt")

    content = format_as_txt(parsed)
    out.write_text(content, encoding="utf-8")
    return out
