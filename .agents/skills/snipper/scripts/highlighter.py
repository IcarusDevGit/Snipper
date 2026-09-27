"""In-place Word document highlighting and run splitting engine."""

from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import docx
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.text.paragraph import Paragraph
from docx.text.run import Run

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from document import Question
from nlp import LemmaMatch


NAMED_HIGHLIGHT_MAP: Dict[str, WD_COLOR_INDEX] = {
    "yellow": WD_COLOR_INDEX.YELLOW,
    "turquoise": WD_COLOR_INDEX.TURQUOISE,
    "cyan": WD_COLOR_INDEX.TURQUOISE,
    "green": WD_COLOR_INDEX.BRIGHT_GREEN,
    "bright_green": WD_COLOR_INDEX.BRIGHT_GREEN,
    "pink": WD_COLOR_INDEX.PINK,
    "magenta": WD_COLOR_INDEX.PINK,
    "light_gray": WD_COLOR_INDEX.GRAY_25,
    "gray": WD_COLOR_INDEX.GRAY_25,
    "dark_yellow": WD_COLOR_INDEX.DARK_YELLOW,
    "teal": WD_COLOR_INDEX.TEAL,
    "dark_cyan": WD_COLOR_INDEX.TEAL,
    "blue": WD_COLOR_INDEX.BLUE,
    "red": WD_COLOR_INDEX.RED,
}


@dataclass
class StyleSlice:
    text: str
    bold: Optional[bool]
    italic: Optional[bool]
    font_name: Optional[str]
    font_size: Optional[Any]
    font_color_rgb: Optional[Any]
    highlight_color: Optional[str]
    is_hex: bool


def apply_highlight_to_run(run: Run, color: str, is_hex: bool):
    """Applies either hex shading or named highlight to a python-docx Run."""
    if not color:
        return

    clean_color = color.strip()
    if is_hex or clean_color.startswith("#") or len(clean_color) == 6:
        hex_val = clean_color.lstrip("#").upper()
        shd_xml = f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{hex_val}"/>'
        shd_elem = parse_xml(shd_xml)
        run._r.get_or_add_rPr().append(shd_elem)
    else:
        named = NAMED_HIGHLIGHT_MAP.get(clean_color.lower(), WD_COLOR_INDEX.YELLOW)
        run.font.highlight_color = named


def copy_run_formatting(source: Run, target: Run):
    """Copies font attributes from source Run to target Run."""
    if source.bold is not None:
        target.bold = source.bold
    if source.italic is not None:
        target.italic = source.italic
    if source.underline is not None:
        target.underline = source.underline
    if source.font.name is not None:
        target.font.name = source.font.name
    if source.font.size is not None:
        target.font.size = source.font.size
    try:
        if source.font.color and source.font.color.rgb:
            target.font.color.rgb = source.font.color.rgb
    except Exception:
        pass


def highlight_paragraph_spans(
    paragraph: Paragraph,
    spans: List[Tuple[int, int, str, bool]],  # (start_char, end_char, color, bold_override)
    default_palette_mode: str = "hex",
):
    """
    Highlights character spans in a paragraph by slicing runs while preserving formatting.
    spans must be non-overlapping and sorted by start_char.
    """
    if not spans:
        return

    orig_text = paragraph.text
    if not orig_text:
        return

    # Map each character index in paragraph.text to its source Run
    char_to_run: List[Optional[Run]] = []
    for run in paragraph.runs:
        char_to_run.extend([run] * len(run.text))

    # Pad if discrepancy between runs and paragraph.text
    while len(char_to_run) < len(orig_text):
        char_to_run.append(paragraph.runs[-1] if paragraph.runs else None)

    # Build span map for each character: (color, bold_override)
    char_span_info: List[Optional[Tuple[str, bool]]] = [None] * len(orig_text)
    for start, end, color, bold in spans:
        s = max(0, min(start, len(orig_text)))
        e = max(0, min(end, len(orig_text)))
        for i in range(s, e):
            char_span_info[i] = (color, bold)

    # Partition into contiguous slices with identical (run, color, bold)
    slices: List[Tuple[str, Optional[Run], Optional[str], bool]] = []
    if len(orig_text) > 0:
        cur_text = [orig_text[0]]
        cur_run = char_to_run[0]
        cur_span = char_span_info[0]

        for i in range(1, len(orig_text)):
            c_char = orig_text[i]
            c_run = char_to_run[i]
            c_span = char_span_info[i]

            if c_run == cur_run and c_span == cur_span:
                cur_text.append(c_char)
            else:
                color, bold = (cur_span[0], cur_span[1]) if cur_span else (None, False)
                slices.append(("".join(cur_text), cur_run, color, bold))
                cur_text = [c_char]
                cur_run = c_run
                cur_span = c_span

        color, bold = (cur_span[0], cur_span[1]) if cur_span else (None, False)
        slices.append(("".join(cur_text), cur_run, color, bold))

    # Remove all existing runs from paragraph
    for r in list(paragraph.runs):
        paragraph._p.remove(r._r)

    # Add reconstructed slices
    for text_part, src_run, color, bold_override in slices:
        new_run = paragraph.add_run(text_part)
        if src_run:
            copy_run_formatting(src_run, new_run)
        if bold_override:
            new_run.bold = True
        if color:
            is_hex = (default_palette_mode == "hex") or color.startswith("#")
            apply_highlight_to_run(new_run, color, is_hex)


class DocumentHighlighter:
    """Applies lemma matches in-place to parsed documents."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def highlight_matches(
        self,
        body_paragraphs: List[Tuple[int, Paragraph]],
        matches: List[LemmaMatch],
    ):
        """Highlights lemma matches in body paragraphs in-place."""
        matches_by_p: Dict[int, List[LemmaMatch]] = {}
        for m in matches:
            matches_by_p.setdefault(m.paragraph_idx, []).append(m)

        for p_idx, p_obj in body_paragraphs:
            p_matches = matches_by_p.get(p_idx, [])
            if not p_matches:
                continue

            # Sort and deduplicate/merge overlapping matches
            p_matches.sort(key=lambda m: (m.start_char, -(m.end_char - m.start_char)))
            spans: List[Tuple[int, int, str, bool]] = []

            last_end = 0
            for m in p_matches:
                if m.start_char >= last_end:
                    spans.append((m.start_char, m.end_char, m.color, False))
                    last_end = m.end_char

            highlight_paragraph_spans(p_obj, spans, default_palette_mode=self.config.palette_mode)

    def highlight_keywords(
        self,
        body_paragraphs: List[Tuple[int, Paragraph]],
        questions: List[Question],
    ):
        """Highlights targeted question keywords in body paragraphs in-place."""
        keywords_by_q = {q.id: q.keywords for q in questions if q.keywords}
        q_map = {q.id: q for q in questions}
        all_matches: List[LemmaMatch] = []
        for p_idx, p_obj in body_paragraphs:
            p_matches = find_keyword_matches_in_text(keywords_by_q, q_map, p_idx, p_obj.text)
            all_matches.extend(p_matches)
        self.highlight_matches(body_paragraphs, all_matches)


def find_keyword_matches_in_text(
    keywords_by_question: Dict[int, List[str]],
    questions_by_id: Dict[int, Question],
    paragraph_idx: int,
    paragraph_text: str,
) -> List[LemmaMatch]:
    """Finds occurrences of keywords for each question and returns LemmaMatch instances."""
    if not paragraph_text.strip():
        return []

    matches: List[LemmaMatch] = []
    for q_id, keywords in keywords_by_question.items():
        q = questions_by_id.get(q_id)
        color = q.color if q else "#FFFF7F"
        for kw in keywords:
            kw_clean = kw.strip()
            if not kw_clean:
                continue
            left_b = r"\b" if re.match(r"^\w", kw_clean) else ""
            right_b = r"\b" if re.search(r"\w$", kw_clean) else ""
            pattern = left_b + re.escape(kw_clean) + right_b
            for m in re.finditer(pattern, paragraph_text, flags=re.IGNORECASE):
                matches.append(
                    LemmaMatch(
                        paragraph_idx=paragraph_idx,
                        start_char=m.start(),
                        end_char=m.end(),
                        text=paragraph_text[m.start():m.end()],
                        lemma=kw_clean.lower(),
                        question_ids=[q_id],
                        color=color,
                    )
                )
    return matches
