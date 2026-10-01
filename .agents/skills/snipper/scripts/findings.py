"""Findings ingestion, validation, and Unicode superscript formatting."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Union

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

SUPERSCRIPT_DIGITS = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
}


def to_superscript_num(num: int) -> str:
    """Converts an integer to a Unicode superscript string."""
    return "".join(SUPERSCRIPT_DIGITS.get(d, d) for d in str(num))


def to_superscript_str(val: Any) -> str:
    """Converts digits in an identifier to Unicode superscript characters."""
    s = str(val)
    return "".join(SUPERSCRIPT_DIGITS.get(d, d) for d in s)


def format_superscript_citations(target_ids: List[Any]) -> str:
    """Formats a list of question/target IDs as a superscript citation string (e.g. [1, 2] -> '¹,²', ['Q1', 'O1'] -> 'O¹,Q¹')."""
    if not target_ids:
        return ""

    def sort_key(x: Any):
        s = str(x).strip()
        m = re.match(r"^([A-Za-z]+)(\d+)$", s)
        if m:
            return (m.group(1).upper(), int(m.group(2)))
        if s.isdigit():
            return ("Q", int(s))
        return ("Z", s)

    sorted_ids = sorted(set(target_ids), key=sort_key)
    return ",".join(to_superscript_str(tid) for tid in sorted_ids)


@dataclass
class FindingConcept:
    name: str
    definition: str
    source_url: Optional[str] = None


@dataclass
class Finding:
    question_numbers: List[int]
    snippet_text: str
    target_ids: List[str] = field(default_factory=list)
    web_sources: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    concepts: List[FindingConcept] = field(default_factory=list)


@dataclass
class FindingsData:
    findings: List[Finding] = field(default_factory=list)
    unanswered_questions: List[int] = field(default_factory=list)
    unanswered_targets: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FindingsData":
        if not isinstance(data, dict):
            raise ValueError("Findings data must be a dictionary.")

        raw_findings = data.get("findings", [])
        if not isinstance(raw_findings, list):
            raise ValueError("'findings' field must be a list.")

        findings: List[Finding] = []
        for idx, item in enumerate(raw_findings):
            if not isinstance(item, dict):
                raise ValueError(f"Finding at index {idx} must be a dictionary.")

            raw_target_ids = item.get("target_ids")
            raw_q_nums = item.get("question_numbers")
            snippet = item.get("snippet_text", "")
            sources = item.get("web_sources", [])
            keywords = item.get("keywords", [])
            raw_concepts = item.get("concepts", [])

            if not snippet or not isinstance(snippet, str) or not snippet.strip():
                raise ValueError(f"Finding at index {idx} must have non-empty 'snippet_text'.")

            target_ids: List[str] = []
            question_numbers: List[int] = []

            if raw_target_ids is not None and isinstance(raw_target_ids, list):
                target_ids = [str(t).strip() for t in raw_target_ids if str(t).strip()]
            if raw_q_nums is not None and isinstance(raw_q_nums, list):
                for q in raw_q_nums:
                    try:
                        question_numbers.append(int(q))
                    except (ValueError, TypeError):
                        pass

            if not target_ids and not question_numbers:
                raise ValueError(
                    f"Finding at index {idx} must have non-empty 'target_ids' or 'question_numbers' list."
                )

            # Cross-populate missing representations
            if not target_ids and question_numbers:
                target_ids = [f"Q{q}" for q in question_numbers]
            elif not question_numbers and target_ids:
                for tid in target_ids:
                    m = re.search(r"\d+", tid)
                    if m:
                        question_numbers.append(int(m.group()))

            parsed_concepts: List[FindingConcept] = []
            if isinstance(raw_concepts, list):
                for c in raw_concepts:
                    if isinstance(c, dict) and "name" in c and "definition" in c:
                        parsed_concepts.append(
                            FindingConcept(
                                name=str(c["name"]).strip(),
                                definition=str(c["definition"]).strip(),
                                source_url=str(c["source_url"]).strip() if c.get("source_url") else None,
                            )
                        )

            findings.append(
                Finding(
                    question_numbers=question_numbers,
                    target_ids=target_ids,
                    snippet_text=snippet,
                    web_sources=[str(s) for s in sources] if isinstance(sources, list) else [],
                    keywords=[str(k).strip() for k in keywords] if isinstance(keywords, list) else [],
                    concepts=parsed_concepts,
                )
            )

        unanswered_raw = data.get("unanswered_targets")
        unanswered_q_raw = data.get("unanswered_questions")

        unanswered_targets: List[str] = []
        unanswered_questions: List[int] = []

        if unanswered_raw is not None and isinstance(unanswered_raw, list):
            unanswered_targets = [str(t).strip() for t in unanswered_raw if str(t).strip()]
        if unanswered_q_raw is not None and isinstance(unanswered_q_raw, list):
            for q in unanswered_q_raw:
                try:
                    unanswered_questions.append(int(q))
                except (ValueError, TypeError):
                    pass

        if not unanswered_targets and unanswered_questions:
            unanswered_targets = [f"Q{q}" for q in unanswered_questions]
        elif not unanswered_questions and unanswered_targets:
            for ut in unanswered_targets:
                m = re.search(r"\d+", ut)
                if m:
                    unanswered_questions.append(int(m.group()))

        return cls(
            findings=findings,
            unanswered_questions=unanswered_questions,
            unanswered_targets=unanswered_targets,
        )

    @classmethod
    def from_file(cls, path: Path | str) -> "FindingsData":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Findings file not found: {p}")

        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        return cls.from_dict(data)
