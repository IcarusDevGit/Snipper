"""Findings retrieval, lexical prioritization, and snippet card formatting."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from findings import Finding, FindingsData
from scope import ScopeResolver, ScopeResult

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "and", "or", "but", "if", "then", "else", "what",
    "which", "who", "whom", "this", "that", "these", "those", "how", "when",
    "where", "why", "de", "do", "da", "em", "um", "uma", "os", "as", "para", "com",
}


@dataclass
class CandidateSnippet:
    source_findings_path: Union[Path, str]
    source_doc_path: Optional[Union[Path, str]]
    target_id: str
    snippet_text: str
    paragraph_coord: str  # e.g. "P3"
    keywords: List[str] = field(default_factory=list)
    web_sources: List[str] = field(default_factory=list)
    score: float = 0.0



def extract_paragraph_coordinates(body_txt: str, snippet: str) -> str:
    """Finds paragraph coordinate(s) [P#] in companion text for a given snippet."""
    if not body_txt or not snippet:
        return ""

    norm_snippet = re.sub(r"\s+", " ", snippet.strip())
    lines = body_txt.splitlines()

    matched_p: List[str] = []
    for line in lines:
        line_str = line.strip()
        m = re.match(r"^\[P(\d+)\]\s*(.+)$", line_str)
        if m:
            p_num = m.group(1)
            p_text = re.sub(r"\s+", " ", m.group(2).strip())
            # Check for substring match (case-insensitive)
            if norm_snippet.lower() in p_text.lower() or p_text.lower() in norm_snippet.lower():
                matched_p.append(f"P{p_num}")

    if matched_p:
        if len(matched_p) == 1:
            return matched_p[0]
        return f"{matched_p[0]}-{matched_p[-1]}"

    return ""


def score_candidate(snippet: CandidateSnippet, query: str) -> float:
    """Computes a lexical relevance score for a candidate snippet against a query."""
    q_clean = query.strip().lower()
    if not q_clean:
        return 0.0

    score = 0.0
    s_text_lower = snippet.snippet_text.lower()

    # Exact query match
    if q_clean in s_text_lower:
        score += 15.0

    # Token overlap (excluding stop words)
    q_tokens = [t for t in re.findall(r"\w+", q_clean) if t not in STOP_WORDS]
    for token in q_tokens:
        if token in s_text_lower:
            score += 3.0
        # Keyword matches carry higher weight
        for kw in snippet.keywords:
            if token in kw.lower():
                score += 5.0
        # Target ID match (e.g. searching "Q1")
        if token == snippet.target_id.lower():
            score += 8.0

    return score


def scan_scoped_findings(scope_result: ScopeResult) -> List[CandidateSnippet]:
    """Scans all .findings.json files in scope and builds candidate snippets."""
    findings_files = scope_result.get_scoped_findings_files()
    candidates: List[CandidateSnippet] = []
    storage = getattr(scope_result, "storage_provider", None)

    for f_target in findings_files:
        try:
            if storage is not None:
                json_content = storage.read_text(f_target)
                findings_data = FindingsData.from_json(json_content)
            else:
                findings_data = FindingsData.from_file(f_target)
        except Exception:
            continue

        body_txt = ""
        source_doc = None

        if storage is not None and hasattr(storage, "_resolve_target"):
            source_doc = str(f_target)
            try:
                # If target is DriveItem or path, locate companion txt
                item = storage._resolve_target(f_target)
                stem = item.name.replace(".findings.json", "").replace(".findings", "")
                parent_id = item.parent_id or storage.library_folder_id
                body_txt = storage.read_text(f"{stem}.txt")
            except Exception:
                pass
        else:
            f_path = Path(f_target)
            doc_stem = f_path.stem.replace(".findings", "")
            parent_dir = f_path.parent

            companion_txt_candidates = [
                parent_dir / f"{doc_stem}.txt",
                parent_dir / f"{doc_stem}.snipper.txt",
            ]
            for txt_c in companion_txt_candidates:
                if txt_c.exists():
                    try:
                        body_txt = txt_c.read_text(encoding="utf-8")
                        break
                    except Exception:
                        pass

            docx_path = parent_dir / f"{doc_stem}.docx"
            source_doc = docx_path if docx_path.exists() else None

        for f in findings_data.findings:
            target_ids = getattr(f, "target_ids", [])
            if not target_ids and f.question_numbers:
                target_ids = [f"Q{q}" for q in f.question_numbers]

            coord = extract_paragraph_coordinates(body_txt, f.snippet_text)

            for tid in target_ids:
                candidates.append(
                    CandidateSnippet(
                        source_findings_path=f_target if isinstance(f_target, Path) else Path(str(f_target)),
                        source_doc_path=source_doc if (source_doc is None or isinstance(source_doc, Path)) else Path(str(source_doc)),
                        target_id=tid,
                        snippet_text=f.snippet_text,
                        paragraph_coord=coord,
                        keywords=list(f.keywords),
                        web_sources=list(f.web_sources),
                    )
                )

    return candidates


def lookup_snippets(
    query: str,
    target_path: Optional[Union[Path, str]] = None,
    scope: Optional[str] = None,
    limit: Optional[int] = None,
    library_root: Optional[Union[Path, str]] = None,
    storage_provider: Optional[Any] = None,
) -> Tuple[List[CandidateSnippet], ScopeResult]:
    """Executes snippet lookup within the resolved scope with conditional lexical pre-filtering."""
    resolver = ScopeResolver(default_library_root=library_root, storage_provider=storage_provider)
    scope_result = resolver.resolve(target_path=target_path, scope=scope, library_root=library_root)

    candidates = scan_scoped_findings(scope_result)

    if limit is not None and limit > 0:
        # Lexical prioritization when limit is provided
        for c in candidates:
            c.score = score_candidate(c, query)

        # Filter candidates with positive match scores, sorted descending
        matched = [c for c in candidates if c.score > 0]
        matched.sort(key=lambda x: x.score, reverse=True)
        return matched[:limit], scope_result

    # When limit is omitted, bypass lexical pre-filtering and return all candidates in scope
    return candidates, scope_result



def format_snippet_card(index: int, candidate: CandidateSnippet) -> str:
    """Formats a candidate snippet into a standardized display card."""
    doc_display = str(candidate.source_doc_path or candidate.source_findings_path)
    coord_part = f" :: {candidate.paragraph_coord}" if candidate.paragraph_coord else ""
    kw_part = f"\n   Keywords: {', '.join(candidate.keywords)}" if candidate.keywords else ""

    return (
        f"{index}. [{doc_display}{coord_part}] (Matched for {candidate.target_id})\n"
        f'   "{candidate.snippet_text}"{kw_part}'
    )


def format_lookup_results(
    candidates: List[CandidateSnippet],
    scope_type: str,
    limit: Optional[int] = None,
) -> str:
    """Renders formatted search results card list."""
    limit_str = str(limit) if limit is not None else "None"
    header = f"[Found {len(candidates)} relevant snippets (Scope: {scope_type}, Limit: {limit_str})]\n"

    if not candidates:
        return header + "\nNo matching snippets found."

    cards = [format_snippet_card(idx, c) for idx, c in enumerate(candidates, start=1)]
    return header + "\n" + "\n\n".join(cards)
