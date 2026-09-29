"""In-place document mutation, summary block generation, and snippet overlay."""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.paragraph import Paragraph

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from alignment import (
    find_snippet_in_text,
    resolve_paragraph_styling,
)
from config import SnipperConfig
from document import ParsedDocument, Question
from findings import FindingsData, format_superscript_citations
from highlighter import (
    apply_highlight_to_run,
    copy_run_formatting,
    find_keyword_matches_in_text,
)
from nlp import LemmaMatch


def apply_paragraph_resolved_slices(
    paragraph: Paragraph,
    slices: List[Tuple[int, int, Optional[str], bool, str]],
    palette_mode: str = "hex",
):
    """Reconstructs paragraph runs with resolved highlights, bolding, and superscripts."""
    if not slices:
        return

    orig_text = paragraph.text
    orig_runs = list(paragraph.runs)

    # Build character to original run map
    char_to_run = []
    for run in orig_runs:
        char_to_run.extend([run] * len(run.text))
    while len(char_to_run) < len(orig_text):
        char_to_run.append(orig_runs[-1] if orig_runs else None)

    # Clear old runs
    for r in orig_runs:
        paragraph._p.remove(r._r)

    # Add new styled runs
    for start, end, color, bold, superscript in slices:
        text_chunk = orig_text[start:end]
        if not text_chunk:
            continue

        src_run = char_to_run[start] if start < len(char_to_run) else None
        new_run = paragraph.add_run(text_chunk)

        if src_run:
            copy_run_formatting(src_run, new_run)
        if bold:
            new_run.bold = True
        if color:
            is_hex = (palette_mode == "hex") or color.startswith("#")
            apply_highlight_to_run(new_run, color, is_hex)

        # Attach superscript if present on trailing character
        if superscript:
            sup_run = paragraph.add_run(superscript)
            if src_run:
                copy_run_formatting(src_run, sup_run)
            if color:
                is_hex = (palette_mode == "hex") or color.startswith("#")
                apply_highlight_to_run(sup_run, color, is_hex)


def insert_summary_block(
    parsed: ParsedDocument,
    findings_data: FindingsData,
    palette_mode: str = "hex",
):
    """Inserts the Questions & Answers summary section before the Body container."""
    if parsed.body_header_idx >= len(parsed.doc.paragraphs):
        return
    body_header_p = parsed.doc.paragraphs[parsed.body_header_idx]

    # Title: Questions & Answers
    title_p = body_header_p.insert_paragraph_before()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run("Questions & Answers")
    title_run.bold = True

    # Map findings by question number
    findings_by_q: Dict[int, List[Any]] = {}
    for f in findings_data.findings:
        for q_id in f.question_numbers:
            findings_by_q.setdefault(q_id, []).append(f)

    # Append each question and its answering evidence
    for q in parsed.questions:
        q_p = body_header_p.insert_paragraph_before()
        
        # Color tag / prefix
        prefix_run = q_p.add_run(f"Q{q.id}: ")
        prefix_run.bold = True
        is_hex = (palette_mode == "hex") or q.color.startswith("#")
        apply_highlight_to_run(prefix_run, q.color, is_hex)

        # Question text
        q_text_run = q_p.add_run(q.text)
        q_text_run.bold = True

        q_findings = findings_by_q.get(q.id, [])
        is_unanswered = (q.id in findings_data.unanswered_questions) or not q_findings

        # Collect keywords: combine q.keywords and findings keywords for this question
        q_keywords: List[str] = list(q.keywords)
        for f in q_findings:
            for kw in f.keywords:
                if kw not in q_keywords:
                    q_keywords.append(kw)

        if q_keywords:
            kw_p = body_header_p.insert_paragraph_before()
            kw_p.add_run(f"  * Keywords: {', '.join(q_keywords)}")

        # Collect and merge concepts for this question
        concept_dict: Dict[str, Dict[str, Optional[str]]] = {}
        concept_order: List[str] = []

        for c in getattr(q, "concepts", []):
            key = c.name.lower().strip()
            if key not in concept_dict:
                concept_order.append(key)
                concept_dict[key] = {
                    "name": c.name,
                    "definition": c.definition,
                    "source_url": c.source_url,
                }

        for f in q_findings:
            for fc in getattr(f, "concepts", []):
                key = fc.name.lower().strip()
                if key not in concept_dict:
                    concept_order.append(key)
                    concept_dict[key] = {
                        "name": fc.name,
                        "definition": fc.definition,
                        "source_url": fc.source_url,
                    }
                else:
                    if fc.definition:
                        concept_dict[key]["definition"] = fc.definition
                    if fc.source_url:
                        concept_dict[key]["source_url"] = fc.source_url

        for key in concept_order:
            c_info = concept_dict[key]
            c_name = c_info["name"]
            c_def = (c_info["definition"] or "").strip()
            c_url = (c_info["source_url"] or "").strip()

            c_p = body_header_p.insert_paragraph_before()
            if c_def:
                text = f"  * Concept: {c_name} - {c_def}"
            else:
                text = f"  * Concept: {c_name}"
            if c_url:
                text += f" (Source: {c_url})"
            c_p.add_run(text)
        if is_unanswered:
            unanswered_p = body_header_p.insert_paragraph_before()
            unans_run = unanswered_p.add_run("  * Snippet: [No answering evidence found in text]")
            unans_run.italic = True
        else:
            for f in q_findings:
                snip_p = body_header_p.insert_paragraph_before()
                snip_run = snip_p.add_run(f'  * Snippet: "{f.snippet_text}"')
                
                # Superscript citation
                sup_label = format_superscript_citations(f.question_numbers)
                if sup_label:
                    sup_run = snip_p.add_run(sup_label)
                    apply_highlight_to_run(sup_run, q.color, is_hex)

                if f.web_sources:
                    src_p = body_header_p.insert_paragraph_before()
                    src_p.add_run("    Sources Consulted: " + ", ".join(f.web_sources))

    # Blank spacing line before Body
    body_header_p.insert_paragraph_before()


class DocumentMutator:
    """Orchestrates in-place document mutation and assembly."""

    def __init__(self, config: Optional[SnipperConfig] = None):
        self.config = config or SnipperConfig()

    def mutate(
        self,
        parsed: ParsedDocument,
        matches: List[LemmaMatch],
        findings_data: FindingsData,
        output_path: Optional[Path] = None,
    ):
        """Mutates the document in-place with summary block, highlights, and superscripts."""
        questions_by_id = {q.id: q for q in parsed.questions}

        # Collect keywords across questions and findings
        keywords_by_q: Dict[int, List[str]] = {}
        for q in parsed.questions:
            if q.keywords:
                for kw in q.keywords:
                    keywords_by_q.setdefault(q.id, []).append(kw)
        for f in findings_data.findings:
            if f.keywords:
                for q_id in f.question_numbers:
                    for kw in f.keywords:
                        if kw not in keywords_by_q.setdefault(q_id, []):
                            keywords_by_q[q_id].append(kw)

        has_keywords = any(keywords_by_q.values())

        # Precompute snippet spans across paragraphs (supporting single and multi-paragraph snippets)
        paragraph_spans_by_idx: Dict[int, List[Tuple[int, int, List[int], str]]] = {
            p_idx: [] for p_idx, _ in parsed.body_paragraphs
        }

        # Build paragraph text offsets in body_text
        para_offsets: List[Tuple[int, int, int]] = []  # (p_idx, start_offset, end_offset)
        cur_offset = 0
        for p_idx, p_obj in parsed.body_paragraphs:
            p_len = len(p_obj.text)
            para_offsets.append((p_idx, cur_offset, cur_offset + p_len))
            cur_offset += p_len + 1  # newline separator

        full_body_text = parsed.body_text

        for f in findings_data.findings:
            primary_q = min(f.question_numbers)
            color = questions_by_id.get(primary_q, parsed.questions[0]).color

            # 1. Try single-paragraph matching first
            matched_single = False
            for p_idx, p_obj in parsed.body_paragraphs:
                p_text = p_obj.text
                if not p_text.strip():
                    continue
                pos = find_snippet_in_text(f.snippet_text, p_text)
                if pos:
                    paragraph_spans_by_idx[p_idx].append((pos[0], pos[1], f.question_numbers, color))
                    matched_single = True
                    break

            if matched_single:
                continue

            # 2. Try global cross-paragraph matching in body_text
            pos = find_snippet_in_text(f.snippet_text, full_body_text)
            if pos:
                g_start, g_end = pos
                for p_idx, p_start_off, p_end_off in para_offsets:
                    overlap_s = max(p_start_off, g_start)
                    overlap_e = min(p_end_off, g_end)
                    if overlap_s < overlap_e:
                        rel_s = overlap_s - p_start_off
                        rel_e = overlap_e - p_start_off
                        is_last = (g_end <= p_end_off)
                        q_ids = f.question_numbers if is_last else []
                        paragraph_spans_by_idx[p_idx].append((rel_s, rel_e, q_ids, color))

        # 1. Overlay snippets & match bolding onto body paragraphs
        for p_idx, p_obj in parsed.body_paragraphs:
            p_text = p_obj.text
            if not p_text.strip():
                continue

            # Identify snippets present in this paragraph
            snippet_spans: List[Tuple[int, int, List[int], str]] = paragraph_spans_by_idx.get(p_idx, [])

            # If keywords were provided/discovered, use targeted keyword matches
            if has_keywords:
                p_matches = find_keyword_matches_in_text(
                    keywords_by_q, questions_by_id, p_idx, p_text
                )
            else:
                p_matches = [m for m in matches if m.paragraph_idx == p_idx]

            # Resolve paragraph styling: keywords and matches are highlighted across the body
            # with the respective question's color, and bolded when intersecting snippet spans.
            slices = resolve_paragraph_styling(
                paragraph_text=p_text,
                paragraph_idx=p_idx,
                lemma_matches=p_matches,
                snippet_spans=snippet_spans,
                matches_only_in_snippets=False,
            )

            # Apply runs
            apply_paragraph_resolved_slices(p_obj, slices, palette_mode=self.config.palette_mode)

        # 2. Insert Questions & Answers Summary Block
        insert_summary_block(parsed, findings_data, palette_mode=self.config.palette_mode)

        # 3. Save modified document in-place
        target_path = output_path or parsed.file_path
        parsed.doc.save(str(target_path))
