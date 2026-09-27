"""Text normalization, alignment, and character-level span resolution."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Set, Tuple
from docx.text.paragraph import Paragraph

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from findings import format_superscript_citations
from highlighter import highlight_paragraph_spans
from nlp import LemmaMatch


QUOTE_REPLACEMENTS = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "`": "'",
    "´": "'",
    "—": "-",
    "–": "-",
    "\u00a0": " ",  # Non-breaking space
    "\u2009": " ",  # Thin space
    "\u202f": " ",  # Narrow no-break space
}


def normalize_for_search(text: str) -> Tuple[str, List[int]]:
    """
    Normalizes punctuation and whitespace for resilient search.
    Returns (normalized_string, list_of_original_indices_per_char).
    """
    normalized_chars = []
    orig_indices = []

    for orig_idx, ch in enumerate(text):
        norm_ch = QUOTE_REPLACEMENTS.get(ch, ch)
        normalized_chars.append(norm_ch)
        orig_indices.append(orig_idx)

    return "".join(normalized_chars), orig_indices


def find_snippet_in_text(snippet: str, target_text: str) -> Optional[Tuple[int, int]]:
    """
    Locates the start and end character offsets of snippet in target_text using normalization.
    Returns (start_char, end_char) in target_text, or None if not found.
    """
    if not snippet or not target_text:
        return None

    # Try direct search first
    direct_pos = target_text.find(snippet)
    if direct_pos != -1:
        return (direct_pos, direct_pos + len(snippet))

    # Normalized search
    norm_target, orig_indices = normalize_for_search(target_text)
    norm_snippet, _ = normalize_for_search(snippet)

    # Clean whitespace collapsing
    norm_target_clean = re.sub(r"\s+", " ", norm_target).strip()
    norm_snippet_clean = re.sub(r"\s+", " ", norm_snippet).strip()

    pos = norm_target.find(norm_snippet)
    if pos != -1:
        start_char = orig_indices[pos]
        end_char = orig_indices[pos + len(norm_snippet) - 1] + 1
        return (start_char, end_char)

    # Whitespace-resilient search (handles differences in \n, multiple spaces, etc.)
    tokens = [t for t in re.split(r"\s+", norm_snippet.strip()) if t]
    if tokens:
        pattern = r"\s+".join(re.escape(tok) for tok in tokens)
        m = re.search(pattern, norm_target)
        if m:
            start_char = orig_indices[m.start()]
            end_char = orig_indices[m.end() - 1] + 1
            return (start_char, end_char)

        # Case-insensitive whitespace-resilient search
        m_lower = re.search(pattern, norm_target, re.IGNORECASE)
        if m_lower:
            start_char = orig_indices[m_lower.start()]
            end_char = orig_indices[m_lower.end() - 1] + 1
            return (start_char, end_char)

    # Case-insensitive fallback
    pos_lower = norm_target.lower().find(norm_snippet.lower())
    if pos_lower != -1:
        start_char = orig_indices[pos_lower]
        end_char = orig_indices[pos_lower + len(norm_snippet) - 1] + 1
        return (start_char, end_char)

    return None


@dataclass
class ParagraphAnnotation:
    color: Optional[str] = None
    bold: bool = False
    is_match: bool = False
    superscript: str = ""


def resolve_paragraph_styling(
    paragraph_text: str,
    paragraph_idx: int,
    lemma_matches: List[LemmaMatch],
    snippet_spans: List[Tuple[int, int, List[int], str]],  # (start_char, end_char, question_ids, color)
    matches_only_in_snippets: bool = False,
) -> List[Tuple[int, int, Optional[str], bool, str]]:
    """
    Builds non-overlapping contiguous styled slices for a paragraph.
    Handles nested snippets (shorter span takes precedence) and match bolding.
    Returns list of (start_char, end_char, color, bold, superscript_str).
    """
    n = len(paragraph_text)
    if n == 0:
        return []

    annotations: List[ParagraphAnnotation] = [ParagraphAnnotation() for _ in range(n)]

    # 1. Overlay lexical matches
    for m in lemma_matches:
        if m.paragraph_idx != paragraph_idx:
            continue
        s = max(0, min(m.start_char, n))
        e = max(0, min(m.end_char, n))
        for i in range(s, e):
            if not matches_only_in_snippets:
                annotations[i].color = m.color
            annotations[i].is_match = True

    # 2. Overlay snippets: sort by span length descending so shorter inner spans overwrite longer outer spans
    sorted_snippets = sorted(snippet_spans, key=lambda s: -(s[1] - s[0]))

    for s_start, s_end, q_ids, color in sorted_snippets:
        s = max(0, min(s_start, n))
        e = max(0, min(s_end, n))
        if s >= e:
            continue

        for i in range(s, e):
            annotations[i].color = color
            if annotations[i].is_match:
                annotations[i].bold = True  # Matches inside snippets are bolded!

        # Attach superscript indicator to the last character of the snippet span
        sup_text = format_superscript_citations(q_ids)
        if sup_text and e > 0:
            existing_sup = annotations[e - 1].superscript
            if existing_sup and existing_sup != sup_text:
                annotations[e - 1].superscript = f"{existing_sup},{sup_text}"
            else:
                annotations[e - 1].superscript = sup_text

    # 3. Collapse into contiguous slices
    slices: List[Tuple[int, int, Optional[str], bool, str]] = []
    cur_start = 0
    cur_color = annotations[0].color
    cur_bold = annotations[0].bold
    cur_sup = annotations[0].superscript

    for i in range(1, n):
        ann = annotations[i]
        # Slices break when color/bold changes or when previous character had a superscript attached
        if ann.color != cur_color or ann.bold != cur_bold or cur_sup:
            slices.append((cur_start, i, cur_color, cur_bold, cur_sup))
            cur_start = i
            cur_color = ann.color
            cur_bold = ann.bold
            cur_sup = ann.superscript
        else:
            cur_sup = ann.superscript

    slices.append((cur_start, n, cur_color, cur_bold, cur_sup))
    return slices
