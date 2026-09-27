"""Findings ingestion, validation, and Unicode superscript formatting."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

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


def format_superscript_citations(question_ids: List[int]) -> str:
    """Formats a list of question IDs as a superscript citation string (e.g. [1, 2] -> '¹,²')."""
    if not question_ids:
        return ""
    sorted_ids = sorted(set(question_ids))
    return ",".join(to_superscript_num(qid) for qid in sorted_ids)


@dataclass
class Finding:
    question_numbers: List[int]
    snippet_text: str
    web_sources: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class FindingsData:
    findings: List[Finding] = field(default_factory=list)
    unanswered_questions: List[int] = field(default_factory=list)

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

            q_nums = item.get("question_numbers", [])
            snippet = item.get("snippet_text", "")
            sources = item.get("web_sources", [])
            keywords = item.get("keywords", [])

            if not isinstance(q_nums, list) or not q_nums:
                raise ValueError(f"Finding at index {idx} must have non-empty 'question_numbers' list.")
            if not isinstance(snippet, str) or not snippet.strip():
                raise ValueError(f"Finding at index {idx} must have non-empty 'snippet_text'.")

            findings.append(
                Finding(
                    question_numbers=[int(q) for q in q_nums],
                    snippet_text=snippet,
                    web_sources=[str(s) for s in sources] if isinstance(sources, list) else [],
                    keywords=[str(k).strip() for k in keywords] if isinstance(keywords, list) else [],
                )
            )

        unanswered = data.get("unanswered_questions", [])
        unanswered_list = [int(q) for q in unanswered] if isinstance(unanswered, list) else []

        return cls(
            findings=findings,
            unanswered_questions=unanswered_list,
        )

    @classmethod
    def from_file(cls, path: Path | str) -> "FindingsData":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Findings file not found: {p}")

        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        return cls.from_dict(data)
