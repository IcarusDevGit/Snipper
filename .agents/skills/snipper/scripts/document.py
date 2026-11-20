"""Document ingestion, resilient section parsing, and question indexing."""

from dataclasses import dataclass, field
import io
from pathlib import Path
import random
import re
import sys
from typing import Any, List, Optional, Tuple, Union
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
    paragraph_idx: int = 0
    color: str = "#FFFF00"
    keywords: List[str] = field(default_factory=list)
    concepts: List[Concept] = field(default_factory=list)
    target_type: str = "Q"  # "Q" or "O"
    target_id: str = "Q1"


@dataclass
class ParsedDocument:
    doc: docx.Document
    file_path: Union[Path, str]
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

    def export_txt(
        self,
        output_path: Optional[Union[Path, str]] = None,
        storage_provider: Optional[Any] = None,
        config: Optional[SnipperConfig] = None,
    ) -> Union[Path, str]:
        return export_to_txt(self, output_path, storage_provider=storage_provider, config=config)


class QuestionsParser:
    """Parses decoupled questions.txt files containing Questions (Q#) and Objectives (O#)."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def parse_file(self, file_path: Path | str) -> List[Question]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Questions file not found: {path}")
        return self.parse_text(path.read_text(encoding="utf-8"))

    def parse_text(self, text: str) -> List[Question]:
        clean_text = text.lstrip("\ufeff")
        lines = clean_text.splitlines()
        raw_items: List[dict] = []
        current_section = "Q"

        section_regex = re.compile(
            r"^\s*(?:#+\s*)?(?:(questions?|perguntas?)|(objectives?|objetivos?))\s*:?\s*$",
            re.IGNORECASE,
        )

        item_regex = re.compile(
            r"^\s*(?:([QOqo])\s*(\d+)|(?:questions?|perguntas?)\s*(\d+)|(?:objectives?|objetivos?)\s*(\d+)|(\d+))\s*[:\-\.]\s*(.+)$",
            re.IGNORECASE,
        )

        for line_idx, line in enumerate(lines):
            stripped = line.strip().lstrip("\ufeff")
            if not stripped:
                continue

            # Section header matching (e.g. "Questions", "Objectives")
            sec_match = section_regex.match(stripped)
            if sec_match:
                if sec_match.group(1):
                    current_section = "Q"
                elif sec_match.group(2):
                    current_section = "O"
                continue

            # Keywords sub-bullet
            kw_match = KEYWORDS_REGEX.match(stripped)
            if kw_match and raw_items:
                kw_content = kw_match.group(1).strip()
                items = [k.strip() for k in re.split(r"[,;]", kw_content) if k.strip()]
                raw_items[-1]["keywords"].extend(items)
                continue

            # Concepts sub-bullet
            concept_match = CONCEPTS_REGEX.match(stripped)
            if concept_match and raw_items:
                concept_content = concept_match.group(1).strip()
                items = [c.strip() for c in re.split(r"[,;]", concept_content) if c.strip()]
                for item in items:
                    web_search = bool(re.search(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", item, re.IGNORECASE))
                    clean_name = re.sub(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", "", item, flags=re.IGNORECASE).strip()
                    raw_items[-1]["concepts"].append(Concept(name=clean_name, web_search=web_search))
                continue

            # Target matching (Q1:, O1:, Question 1:, Objective 1:, 1.)
            m = item_regex.match(stripped)
            if m:
                target_type = current_section
                target_num = 1
                item_text = ""
                if m.group(1) and m.group(2):
                    target_type = m.group(1).upper()
                    target_num = int(m.group(2))
                    item_text = m.group(6).strip()
                elif m.group(3):
                    target_type = "Q"
                    target_num = int(m.group(3))
                    item_text = m.group(6).strip()
                elif m.group(4):
                    target_type = "O"
                    target_num = int(m.group(4))
                    item_text = m.group(6).strip()
                elif m.group(5):
                    target_type = current_section
                    target_num = int(m.group(5))
                    item_text = m.group(6).strip()

                target_id = f"{target_type}{target_num}"
                raw_items.append({
                    "id": target_num,
                    "target_id": target_id,
                    "target_type": target_type,
                    "text": item_text,
                    "line_idx": line_idx,
                    "keywords": [],
                    "concepts": [],
                })
            else:
                cleaned = re.sub(r"^[-*•]\s*", "", stripped).strip()
                if cleaned and not cleaned.startswith("#") and not section_regex.match(cleaned):
                    q_num = len(raw_items) + 1
                    raw_items.append({
                        "id": q_num,
                        "target_id": f"{current_section}{q_num}",
                        "target_type": current_section,
                        "text": cleaned,
                        "line_idx": line_idx,
                        "keywords": [],
                        "concepts": [],
                    })

        palette = self.config.palette
        palette_len = len(palette)
        questions: List[Question] = []
        for idx, item in enumerate(raw_items):
            color = palette[idx % palette_len]
            questions.append(
                Question(
                    id=item["id"],
                    text=item["text"],
                    paragraph_idx=item["line_idx"],
                    color=color,
                    keywords=item["keywords"],
                    concepts=item["concepts"],
                    target_type=item["target_type"],
                    target_id=item["target_id"],
                )
            )
        return questions


class DocumentParser:
    """Parses a .docx file into structured Questions and Body containers, supporting clean decoupled entries and legacy formats."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def parse(
        self,
        file_path: Union[Path, str, io.BytesIO],
        questions_file: Optional[Union[Path, str, io.BytesIO]] = None,
        questions_text: Optional[str] = None,
        virtual_path: Optional[Union[Path, str]] = None,
    ) -> ParsedDocument:
        if isinstance(file_path, (io.BytesIO, io.BufferedIOBase)) or hasattr(file_path, "read"):
            try:
                if hasattr(file_path, "seek"):
                    file_path.seek(0)
                doc = docx.Document(file_path)
                effective_path = Path(virtual_path or "document.docx")
            except Exception:
                if hasattr(file_path, "seek"):
                    file_path.seek(0)
                raw_bytes = file_path.read()
                if isinstance(raw_bytes, bytes):
                    content = raw_bytes.decode("utf-8", errors="replace")
                else:
                    content = str(raw_bytes)
                doc = docx.Document()
                for line in content.splitlines():
                    doc.add_paragraph(line)
                effective_path = Path(virtual_path or "document.gdoc")
        else:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Input document not found: {path}")
            try:
                doc = docx.Document(path)
            except Exception:
                content = path.read_text(encoding="utf-8", errors="replace")
                doc = docx.Document()
                for line in content.splitlines():
                    doc.add_paragraph(line)
            effective_path = path

        paragraphs = doc.paragraphs

        # 1. Resolve external questions
        external_questions: List[Question] = []
        if questions_text is not None:
            qp = QuestionsParser(self.config)
            external_questions = qp.parse_text(questions_text)
        elif isinstance(questions_file, (io.BytesIO, io.BufferedIOBase)) or hasattr(questions_file, "read"):
            qp = QuestionsParser(self.config)
            content = questions_file.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            external_questions = qp.parse_text(content)
        elif questions_file:
            q_path = Path(questions_file)
            if q_path.exists():
                qp = QuestionsParser(self.config)
                external_questions = qp.parse_file(q_path)
        elif effective_path.exists():
            candidates = [
                effective_path.with_name(f"{effective_path.stem}.questions"),
                effective_path.with_name(f"{effective_path.stem}.questions.gdoc"),
                effective_path.with_name(f"{effective_path.stem}.questions.txt"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    qp = QuestionsParser(self.config)
                    external_questions = qp.parse_file(candidate)
                    break

        # 2. Check for legacy embedded Questions and Body sections
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

        # 3. Decoupled or clean document mode
        if external_questions or questions_idx is None:
            body_paragraphs: List[Tuple[int, Paragraph]] = []
            in_summary_block = False

            for idx, p in enumerate(paragraphs):
                text = p.text.strip().lstrip("\ufeff")
                if text == "=== SNIPPER SUMMARY START ===" or text.startswith("=== SNIPPER SUMMARY START ==="):
                    in_summary_block = True
                    continue
                if in_summary_block:
                    if text == "=== SNIPPER SUMMARY END ===" or text.endswith("=== SNIPPER SUMMARY END ==="):
                        in_summary_block = False
                    continue
                body_paragraphs.append((idx, p))

            return ParsedDocument(
                doc=doc,
                file_path=effective_path,
                questions_header_idx=-1,
                body_header_idx=0,
                questions=external_questions,
                body_paragraphs=body_paragraphs,
            )

        # 4. Legacy embedded Questions/Body mode
        if body_idx is None:
            raise ValueError("Could not locate 'Body' section in document.")
        if body_idx <= questions_idx:
            raise ValueError("'Body' section must appear after 'Questions' section.")

        raw_questions: List[dict] = []
        for idx in range(questions_idx + 1, body_idx):
            raw_text = paragraphs[idx].text.strip()
            if not raw_text:
                continue

            if re.match(r"^\s*questions\s*&\s*answers\s*$", raw_text, re.IGNORECASE):
                break

            kw_match = KEYWORDS_REGEX.match(raw_text)
            if kw_match and raw_questions:
                kw_content = kw_match.group(1).strip()
                items = [k.strip() for k in re.split(r"[,;]", kw_content) if k.strip()]
                raw_questions[-1]["keywords"].extend(items)
                continue

            concept_match = CONCEPTS_REGEX.match(raw_text)
            if concept_match and raw_questions:
                concept_content = concept_match.group(1).strip()
                items = [c.strip() for c in re.split(r"[,;]", concept_content) if c.strip()]
                for item in items:
                    web_search = bool(re.search(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", item, re.IGNORECASE))
                    clean_name = re.sub(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", "", item, flags=re.IGNORECASE).strip()
                    raw_questions[-1]["concepts"].append(Concept(name=clean_name, web_search=web_search))
                continue

            cleaned = re.sub(r"^(?:\d+[\.\-\)]\s*|[\*\-\•]\s*)", "", raw_text).strip()
            if cleaned:
                raw_questions.append({
                    "p_idx": idx,
                    "text": cleaned,
                    "keywords": [],
                    "concepts": [],
                })

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
                    target_type="Q",
                    target_id=f"Q{q_num}",
                )
            )

        body_paragraphs = []
        for idx in range(body_idx + 1, len(paragraphs)):
            body_paragraphs.append((idx, paragraphs[idx]))

        return ParsedDocument(
            doc=doc,
            file_path=effective_path,
            questions_header_idx=questions_idx,
            body_header_idx=body_idx,
            questions=questions,
            body_paragraphs=body_paragraphs,
        )


def format_as_txt(parsed: ParsedDocument, include_questions: Optional[bool] = None) -> str:
    """Formats a ParsedDocument into plain text with paragraph tags."""
    lines: List[str] = []

    should_include_q = include_questions if include_questions is not None else (parsed.questions_header_idx >= 0)

    if should_include_q and parsed.questions:
        lines.append("=== QUESTIONS ===")
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


def export_to_txt(
    parsed: ParsedDocument,
    output_path: Optional[Union[Path, str]] = None,
    storage_provider: Optional[Any] = None,
    config: Optional[SnipperConfig] = None,
) -> Union[Path, str]:
    """Exports the parsed document as a companion .txt file or uploads via storage provider.
    Bypasses file creation if Google Drive or Google Docs is in use (storage_backend == 'gdoc' or 'gdrive').
    """
    content = format_as_txt(parsed)

    is_gdoc_mode = (
        (config and getattr(config, "storage_backend", None) == "gdoc")
        or (storage_provider and getattr(storage_provider, "storage_backend", None) == "gdoc")
        or (storage_provider and getattr(storage_provider, "backend", None) == "gdoc")
        or (parsed.file_path and str(parsed.file_path).endswith(".gdoc"))
    )

    if is_gdoc_mode:
        p = Path(parsed.file_path)
        return str(output_path or f"{p.stem}.txt")

    if storage_provider is not None:
        p = Path(parsed.file_path)
        target_dir = Path(output_path).parent if output_path else p.parent
        filename = Path(output_path).name if output_path else f"{p.stem}.txt"
        return storage_provider.write_text(str(target_dir), filename, content)

    if output_path:
        out = Path(output_path)
    else:
        p = Path(parsed.file_path)
        if parsed.questions_header_idx >= 0:
            out = p.with_name(f"{p.stem}.snipper.txt")
        else:
            out = p.with_name(f"{p.stem}.txt")

    out.write_text(content, encoding="utf-8")
    return out

