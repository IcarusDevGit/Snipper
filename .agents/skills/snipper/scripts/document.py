"""Document ingestion, resilient section parsing, and question indexing."""

from dataclasses import dataclass, field
from pathlib import Path
import random
import re
import sys
from typing import Any, List, Optional, Tuple
import docx
from docx.document import Document as DocxDocument
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
@dataclass
class Question:
    id: int
    text: str
    paragraph_idx: int
    color: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    doc: DocxDocument
    file_path: Path
    questions_header_idx: int
    body_header_idx: int
    questions: List[Question] = field(default_factory=list)
    body_paragraphs: List[Tuple[int, Paragraph]] = field(default_factory=list)

    @property
    def body_text(self) -> str:
        return "\n".join(p.text for _, p in self.body_paragraphs)


class DocumentParser:
    """Parses a .docx file into structured Questions and Body containers."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def parse(self, file_path: Path | str) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Input document not found: {path}")

        doc = docx.Document(str(path))
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

        # Extract Questions with optional Keywords sub-bullets
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

            # Strip leading list markers like "1.", "1 -", "-", "*"
            cleaned = re.sub(r"^(?:\d+[\.\-\)]\s*|[\*\-\•]\s*)", "", raw_text).strip()
            if cleaned:
                raw_questions.append({
                    "p_idx": idx,
                    "text": cleaned,
                    "keywords": [],
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
