"""In-place document mutation, summary block generation, and snippet overlay."""

import io
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
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

SUMMARY_START_MARKER = "=== SNIPPER SUMMARY START ==="
SUMMARY_END_MARKER = "=== SNIPPER SUMMARY END ==="


def strip_existing_summary_block(doc: docx.Document) -> bool:
    """Detects and strips any pre-existing summary block wrapped between delimiters or legacy blocks."""
    paragraphs = doc.paragraphs
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None

    for idx, p in enumerate(paragraphs):
        text = p.text.strip()
        if text == SUMMARY_START_MARKER:
            start_idx = idx
        elif text == SUMMARY_END_MARKER and start_idx is not None:
            end_idx = idx
            break

    if start_idx is not None and end_idx is not None:
        # Check if there is an empty spacing line after end marker
        remove_end = end_idx
        if remove_end + 1 < len(paragraphs) and not paragraphs[remove_end + 1].text.strip():
            remove_end += 1

        for i in range(remove_end, start_idx - 1, -1):
            p = paragraphs[i]
            p._p.getparent().remove(p._p)
        return True

    return False


def clean_paragraph_previous_mutation(paragraph: Paragraph) -> str:
    """Removes trailing superscript citation runs from previous mutations to recover clean text."""
    sup_pattern = re.compile(r"^(?:[QO]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)(?:,[QO]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)*$")
    for r in list(paragraph.runs):
        r_text = r.text.strip()
        if r_text and sup_pattern.match(r_text):
            paragraph._p.remove(r._r)
    return paragraph.text


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


def _build_findings_by_target(findings_data: FindingsData) -> Dict[str, List[Any]]:
    """Indexes findings by explicit target_ids, falling back to question_numbers only when target_ids is empty."""
    findings_by_target: Dict[str, List[Any]] = {}
    for f in findings_data.findings:
        target_ids = getattr(f, "target_ids", [])
        if target_ids:
            for tid in target_ids:
                findings_by_target.setdefault(tid, []).append(f)
        else:
            for qid in f.question_numbers:
                findings_by_target.setdefault(f"Q{qid}", []).append(f)
                findings_by_target.setdefault(str(qid), []).append(f)
    return findings_by_target


def _collect_target_summary_data(
    q: Question,
    findings_by_target: Dict[str, List[Any]],
    findings_data: FindingsData,
) -> Tuple[str, List[Any], bool, List[str], List[Dict[str, Optional[str]]]]:
    """Collects deduplicated findings, unanswered status, keywords, and merged concepts for a target."""
    target_id_str = getattr(q, "target_id", f"Q{q.id}")
    lookup_keys = [target_id_str]
    if getattr(q, "target_type", "Q") == "Q":
        lookup_keys.extend([f"Q{q.id}", str(q.id)])

    q_findings: List[Any] = []
    for key in lookup_keys:
        if key in findings_by_target:
            for item in findings_by_target[key]:
                if item not in q_findings:
                    q_findings.append(item)

    is_unanswered = (
        (q.id in findings_data.unanswered_questions and getattr(q, "target_type", "Q") == "Q")
        or (target_id_str in getattr(findings_data, "unanswered_targets", []))
        or not q_findings
    )

    q_keywords: List[str] = list(q.keywords)
    for f in q_findings:
        for kw in f.keywords:
            if kw and kw not in q_keywords:
                q_keywords.append(kw)

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

    concepts = [concept_dict[k] for k in concept_order]
    return target_id_str, q_findings, is_unanswered, q_keywords, concepts


def _format_concept_bullet_text(c_info: Dict[str, Optional[str]]) -> str:
    """Formats a single concept entry as a clean bullet line."""
    c_name = c_info["name"]
    c_def = (c_info["definition"] or "").strip()
    c_url = (c_info["source_url"] or "").strip()
    text = f"  • {c_name} - {c_def}" if c_def else f"  • {c_name}"
    if c_url:
        text += f" (Source: {c_url})"
    return text


def insert_summary_block(
    parsed: ParsedDocument,
    findings_data: FindingsData,
    palette_mode: str = "hex",
):
    """Inserts the Questions & Answers / Objectives summary block prepended at paragraph 0."""
    doc = parsed.doc
    strip_existing_summary_block(doc)

    if not doc.paragraphs:
        anchor_p = doc.add_paragraph()
    else:
        anchor_p = doc.paragraphs[0]

    # Start marker
    start_p = anchor_p.insert_paragraph_before()
    start_p.add_run(SUMMARY_START_MARKER)

    # Title
    title_p = anchor_p.insert_paragraph_before()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    has_objectives = any(getattr(q, "target_type", "Q") == "O" for q in parsed.questions)
    title_text = "Questions & Answers / Objectives" if has_objectives else "Questions & Answers"
    title_run = title_p.add_run(title_text)
    title_run.bold = True

    anchor_p.insert_paragraph_before()

    findings_by_target = _build_findings_by_target(findings_data)

    # Append each target (Question or Objective) and answering evidence
    for q in parsed.questions:
        q_p = anchor_p.insert_paragraph_before()

        (
            target_id_str,
            q_findings,
            is_unanswered,
            q_keywords,
            concepts,
        ) = _collect_target_summary_data(q, findings_by_target, findings_data)

        prefix_run = q_p.add_run(f"{target_id_str}: ")
        prefix_run.bold = True
        is_hex = (palette_mode == "hex") or q.color.startswith("#")
        apply_highlight_to_run(prefix_run, q.color, is_hex)

        q_text_run = q_p.add_run(q.text)
        q_text_run.bold = True

        if q_keywords:
            kw_header_p = anchor_p.insert_paragraph_before()
            kw_header_run = kw_header_p.add_run("Keywords:")
            kw_header_run.bold = True
            for kw in q_keywords:
                kw_p = anchor_p.insert_paragraph_before()
                kw_p.add_run(f"  • {kw}")

        if concepts:
            c_header_p = anchor_p.insert_paragraph_before()
            c_header_run = c_header_p.add_run("Concepts:")
            c_header_run.bold = True
            for c_info in concepts:
                c_p = anchor_p.insert_paragraph_before()
                c_p.add_run(_format_concept_bullet_text(c_info))

        # Blank line separating target metadata from snippets
        anchor_p.insert_paragraph_before()

        if is_unanswered:
            unanswered_p = anchor_p.insert_paragraph_before()
            unans_run = unanswered_p.add_run("[No answering evidence found in text]")
            unans_run.italic = True
            anchor_p.insert_paragraph_before()
        else:
            for f in q_findings:
                snip_p = anchor_p.insert_paragraph_before()
                snip_p.add_run(f'"{f.snippet_text}"')

                # Superscript citation
                sup_source = getattr(f, "target_ids", None) or f.question_numbers
                sup_label = format_superscript_citations(sup_source)
                if sup_label:
                    snip_p.add_run(" ")
                    sup_run = snip_p.add_run(sup_label)
                    sup_run.font.superscript = True
                    apply_highlight_to_run(sup_run, q.color, is_hex)

                if f.web_sources:
                    src_p = anchor_p.insert_paragraph_before()
                    src_p.add_run("  Sources Consulted: " + ", ".join(f.web_sources))

                # Blank line between each snippet for visual readability
                anchor_p.insert_paragraph_before()

    # End marker
    end_p = anchor_p.insert_paragraph_before()
    end_p.add_run(SUMMARY_END_MARKER)

    # Spacing line before document body
    anchor_p.insert_paragraph_before()


class DocumentMutator:
    """Orchestrates in-place document mutation, highlighting, and idempotent summary replacement."""

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
        if not questions_by_id and parsed.questions:
            questions_by_id = {i: q for i, q in enumerate(parsed.questions, start=1)}
        questions_by_target = {getattr(q, "target_id", f"Q{q.id}"): q for q in parsed.questions}

        # Key keyword buckets by target index to avoid Q1/O1 numeric ID collisions
        target_key_by_id: Dict[str, int] = {
            getattr(q, "target_id", f"Q{q.id}"): idx for idx, q in enumerate(parsed.questions)
        }
        q_by_idx: Dict[int, Question] = {idx: q for idx, q in enumerate(parsed.questions)}
        keywords_by_idx: Dict[int, List[str]] = {}
        for idx, q in enumerate(parsed.questions):
            if q.keywords:
                keywords_by_idx.setdefault(idx, []).extend(q.keywords)
        for f in findings_data.findings:
            if not f.keywords:
                continue
            f_tids = getattr(f, "target_ids", [])
            if f_tids:
                for tid in f_tids:
                    if tid in target_key_by_id:
                        bucket = keywords_by_idx.setdefault(target_key_by_id[tid], [])
                        for kw in f.keywords:
                            if kw not in bucket:
                                bucket.append(kw)
            else:
                for q_id in f.question_numbers:
                    q_tid = f"Q{q_id}"
                    if q_tid in target_key_by_id:
                        bucket = keywords_by_idx.setdefault(target_key_by_id[q_tid], [])
                        for kw in f.keywords:
                            if kw not in bucket:
                                bucket.append(kw)

        has_keywords = any(keywords_by_idx.values())

        # Clean any trailing superscripts from previous mutations on body paragraphs
        for p_idx, p_obj in parsed.body_paragraphs:
            clean_paragraph_previous_mutation(p_obj)

        # Precompute snippet spans across paragraphs
        paragraph_spans_by_idx: Dict[int, List[Tuple[int, int, List[int], str]]] = {
            p_idx: [] for p_idx, _ in parsed.body_paragraphs
        }

        # Build paragraph text offsets in body_text
        para_offsets: List[Tuple[int, int, int]] = []
        cur_offset = 0
        for p_idx, p_obj in parsed.body_paragraphs:
            p_len = len(p_obj.text)
            para_offsets.append((p_idx, cur_offset, cur_offset + p_len))
            cur_offset += p_len + 1

        full_body_text = parsed.body_text

        for f in findings_data.findings:
            primary_q = min(f.question_numbers) if f.question_numbers else 1
            default_color = parsed.questions[0].color if parsed.questions else "#FFFF00"
            t_ids = getattr(f, "target_ids", [])
            matched_q = questions_by_target.get(t_ids[0]) if t_ids else None
            if matched_q is None:
                matched_q = questions_by_id.get(primary_q, Question(1, "", 0, default_color))
            color = matched_q.color

            sup_ids = t_ids if t_ids else f.question_numbers

            # 1. Try single-paragraph matching first
            matched_single = False
            for p_idx, p_obj in parsed.body_paragraphs:
                p_text = p_obj.text
                if not p_text.strip():
                    continue
                pos = find_snippet_in_text(f.snippet_text, p_text)
                if pos:
                    paragraph_spans_by_idx[p_idx].append((pos[0], pos[1], sup_ids, color))
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
                        q_ids = sup_ids if is_last else []
                        paragraph_spans_by_idx[p_idx].append((rel_s, rel_e, q_ids, color))

        # 1. Overlay snippets & match bolding onto body paragraphs
        for p_idx, p_obj in parsed.body_paragraphs:
            p_text = p_obj.text
            if not p_text.strip():
                continue

            snippet_spans = paragraph_spans_by_idx.get(p_idx, [])

            if has_keywords:
                p_matches = find_keyword_matches_in_text(
                    keywords_by_idx, q_by_idx, p_idx, p_text
                )
            else:
                p_matches = [m for m in matches if m.paragraph_idx == p_idx]

            slices = resolve_paragraph_styling(
                paragraph_text=p_text,
                paragraph_idx=p_idx,
                lemma_matches=p_matches,
                snippet_spans=snippet_spans,
                matches_only_in_snippets=False,
            )

            apply_paragraph_resolved_slices(p_obj, slices, palette_mode=self.config.palette_mode)

        # 2. Insert / Replace Questions & Answers Summary Block at paragraph 0
        insert_summary_block(parsed, findings_data, palette_mode=self.config.palette_mode)

        # 3. Save modified document in-place or to output stream
        if isinstance(output_path, (io.BytesIO, io.BufferedIOBase)) or hasattr(output_path, "write"):
            parsed.doc.save(output_path)
            output_path.seek(0)
            return output_path

        if output_path is None and (isinstance(parsed.file_path, (io.BytesIO, io.BufferedIOBase)) or hasattr(parsed.file_path, "write")):
            out_stream = io.BytesIO()
            parsed.doc.save(out_stream)
            out_stream.seek(0)
            return out_stream

        target_path = output_path or parsed.file_path
        parsed.doc.save(str(target_path))
        return target_path


def hex_to_rgb_color(hex_str: str) -> Dict[str, float]:
    """Converts a hex color (#RRGGBB) to Google Docs API RgbColor (floats 0.0 - 1.0)."""
    clean = hex_str.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return {"red": 1.0, "green": 1.0, "blue": 0.0}
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0
    return {"red": round(r, 4), "green": round(g, 4), "blue": round(b, 4)}


def detect_summary_block_range(doc_data: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """Detects start and end index of an existing summary block in Google Docs document structure."""
    content = doc_data.get("body", {}).get("content", [])
    start_index: Optional[int] = None
    end_index: Optional[int] = None

    for idx, elem in enumerate(content):
        if "paragraph" not in elem:
            continue
        p_text = "".join(el.get("textRun", {}).get("content", "") for el in elem["paragraph"].get("elements", []))
        if SUMMARY_START_MARKER in p_text and start_index is None:
            start_index = elem.get("startIndex")
        elif SUMMARY_END_MARKER in p_text and start_index is not None:
            end_index = elem.get("endIndex")
            if idx + 1 < len(content):
                next_elem = content[idx + 1]
                if "paragraph" in next_elem:
                    next_text = "".join(el.get("textRun", {}).get("content", "") for el in next_elem["paragraph"].get("elements", []))
                    if not next_text.strip():
                        end_index = next_elem.get("endIndex")
            break

    if start_index is not None and end_index is not None:
        return (start_index, end_index)
    return None


class GoogleDocsMutator:
    """Mutates native Google Docs in-place via Docs API v1 atomic batchUpdate requests."""

    def __init__(self, config: Optional[SnipperConfig] = None, docs_service: Optional[Any] = None):
        self.config = config or SnipperConfig()
        self.docs_service = docs_service

    def detect_summary_block_range(self, doc_data: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        return detect_summary_block_range(doc_data)

    def build_summary_block_text(
        self,
        parsed: ParsedDocument,
        findings_data: FindingsData,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Constructs the plain text summary block and relative character styling spans."""
        summary_text = ""
        style_spans: List[Dict[str, Any]] = []

        def _add_line(line: str) -> Tuple[int, int]:
            nonlocal summary_text
            start_off = len(summary_text)
            summary_text += line + "\n"
            end_off = len(summary_text) - 1
            return start_off, end_off

        # 1. Start delimiter
        s_start, s_end = _add_line(SUMMARY_START_MARKER)
        style_spans.append({
            "start": s_start,
            "end": s_end,
            "bold": True,
            "fontSize": 10.0,
        })

        # 2. Title
        has_objectives = any(getattr(q, "target_type", "Q") == "O" for q in parsed.questions)
        title_text = "Questions & Answers / Objectives" if has_objectives else "Questions & Answers"
        t_start, t_end = _add_line(title_text)
        style_spans.append({
            "start": t_start,
            "end": t_end,
            "bold": True,
            "fontSize": 13.0,
        })
        _add_line("")

        # 3. Map findings by target
        findings_by_target = _build_findings_by_target(findings_data)

        # 4. Format each target item
        for q in parsed.questions:
            (
                target_id_str,
                q_findings,
                is_unanswered,
                q_keywords,
                concepts,
            ) = _collect_target_summary_data(q, findings_by_target, findings_data)

            prefix = f"{target_id_str}: "
            full_line = f"{prefix}{q.text}"
            q_start, q_end = _add_line(full_line)

            # Prefix: bold + highlight
            style_spans.append({
                "start": q_start,
                "end": q_start + len(prefix),
                "bold": True,
                "color": q.color,
                "fontSize": 11.0,
            })
            # Text: bold
            style_spans.append({
                "start": q_start + len(prefix),
                "end": q_end,
                "bold": True,
                "fontSize": 11.0,
            })

            # Target keywords as bullet points
            if q_keywords:
                kh_start, kh_end = _add_line("Keywords:")
                style_spans.append({
                    "start": kh_start,
                    "end": kh_end,
                    "bold": True,
                    "fontSize": 11.0,
                })
                for kw in q_keywords:
                    _add_line(f"  • {kw}")

            # Target concepts as bullet points
            if concepts:
                ch_start, ch_end = _add_line("Concepts:")
                style_spans.append({
                    "start": ch_start,
                    "end": ch_end,
                    "bold": True,
                    "fontSize": 11.0,
                })
                for c_info in concepts:
                    _add_line(_format_concept_bullet_text(c_info))

            _add_line("")

            # Snippets (clean quotes without "Snippet:" marker, spaced apart)
            if is_unanswered:
                u_start, u_end = _add_line("[No answering evidence found in text]")
                style_spans.append({
                    "start": u_start,
                    "end": u_end,
                    "italic": True,
                    "fontSize": 11.0,
                })
                _add_line("")
            else:
                for f in q_findings:
                    sup_source = getattr(f, "target_ids", None) or f.question_numbers
                    sup_label = format_superscript_citations(sup_source) or ""
                    snip_line = f'"{f.snippet_text}" {sup_label}' if sup_label else f'"{f.snippet_text}"'
                    s_start, s_end = _add_line(snip_line)
                    if sup_label:
                        sup_start = s_end - len(sup_label)
                        style_spans.append({
                            "start": sup_start,
                            "end": s_end,
                            "color": q.color,
                            "baselineOffset": "SUPERSCRIPT",
                        })
                    if f.web_sources:
                        _add_line("  Sources Consulted: " + ", ".join(f.web_sources))
                    _add_line("")

        # 5. End delimiter & spacing line
        e_start, e_end = _add_line(SUMMARY_END_MARKER)
        style_spans.append({
            "start": e_start,
            "end": e_end,
            "bold": True,
            "fontSize": 9.0,
        })
        summary_text += "\n"

        return summary_text, style_spans

    def build_mutation_requests(
        self,
        doc_data: Dict[str, Any],
        parsed: ParsedDocument,
        matches: List[LemmaMatch],
        findings_data: FindingsData,
    ) -> List[Dict[str, Any]]:
        """Constructs atomic Google Docs API batchUpdate requests."""
        requests: List[Dict[str, Any]] = []

        content = doc_data.get("body", {}).get("content", [])
        doc_end = content[-1].get("endIndex", 1) if content else 1

        # 1. Detect existing summary block
        existing_range = self.detect_summary_block_range(doc_data)
        old_len = 0
        if existing_range:
            # Clear any corrupted bold and baselineOffset across body
            if doc_end > 2:
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": 1, "endIndex": doc_end - 1},
                        "textStyle": {
                            "bold": False,
                            "baselineOffset": "NONE",
                        },
                        "fields": "bold,baselineOffset,backgroundColor",
                    }
                })
            requests.append({
                "deleteContentRange": {
                    "range": {
                        "startIndex": existing_range[0],
                        "endIndex": existing_range[1],
                    }
                }
            })
            old_len = existing_range[1] - existing_range[0]

        # 2. Insert summary block at index 1
        summary_text, summary_styles = self.build_summary_block_text(parsed, findings_data)
        requests.append({
            "insertText": {
                "location": {"index": 1},
                "text": summary_text,
            }
        })
        new_len = len(summary_text)
        shift = new_len - old_len

        # 2.1 Reset paragraph style of summary block to NORMAL_TEXT so it does NOT inherit
        # TITLE/HEADING styling or flood the document outline/navigation panel
        requests.append({
            "updateParagraphStyle": {
                "range": {
                    "startIndex": 1,
                    "endIndex": 1 + new_len,
                },
                "paragraphStyle": {
                    "namedStyleType": "NORMAL_TEXT",
                    "spaceAbove": {"magnitude": 1, "unit": "PT"},
                    "spaceBelow": {"magnitude": 2, "unit": "PT"},
                    "lineSpacing": 115,
                },
                "fields": "namedStyleType,spaceAbove,spaceBelow,lineSpacing",
            }
        })

        # 2.2 Reset base text style for the summary block (Arial 11pt, unhighlighted)
        requests.append({
            "updateTextStyle": {
                "range": {
                    "startIndex": 1,
                    "endIndex": 1 + new_len,
                },
                "textStyle": {
                    "weightedFontFamily": {
                        "fontFamily": "Arial"
                    },
                    "fontSize": {"magnitude": 11, "unit": "PT"},
                    "italic": False,
                    "underline": False,
                    "strikethrough": False,
                    "baselineOffset": "NONE",
                },
                "fields": "weightedFontFamily,fontSize,italic,underline,strikethrough,baselineOffset",
            }
        })

        # 3. Apply styling to summary block
        for s_style in summary_styles:
            abs_s = 1 + s_style["start"]
            abs_e = 1 + s_style["end"]
            if abs_s >= abs_e:
                continue
            text_style: Dict[str, Any] = {}
            fields: List[str] = []
            if s_style.get("bold") is not None:
                text_style["bold"] = bool(s_style["bold"])
                fields.append("bold")
            if s_style.get("italic") is not None:
                text_style["italic"] = bool(s_style["italic"])
                fields.append("italic")
            if s_style.get("fontSize") is not None:
                text_style["fontSize"] = {
                    "magnitude": float(s_style["fontSize"]),
                    "unit": "PT",
                }
                fields.append("fontSize")
            if s_style.get("color"):
                text_style["backgroundColor"] = {
                    "color": {"rgbColor": hex_to_rgb_color(s_style["color"])}
                }
                fields.append("backgroundColor")
            if s_style.get("baselineOffset"):
                text_style["baselineOffset"] = s_style["baselineOffset"]
                fields.append("baselineOffset")
            if fields:
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": abs_s, "endIndex": abs_e},
                        "textStyle": text_style,
                        "fields": ",".join(fields),
                    }
                })

        # 4. Map questions and keywords for body styling
        questions_by_target: Dict[str, Question] = {q.target_id: q for q in parsed.questions}
        questions_by_num: Dict[int, Question] = {q.id: q for q in parsed.questions}
        default_color = parsed.questions[0].color if parsed.questions else "#FFFF00"

        # Map each keyword to its target color
        keywords_by_color: Dict[str, str] = {}
        for q in parsed.questions:
            for kw in q.keywords:
                if kw.strip():
                    keywords_by_color[kw.strip().lower()] = q.color
        for f in findings_data.findings:
            t_id = f.target_ids[0] if f.target_ids else (f"Q{f.question_numbers[0]}" if f.question_numbers else "Q1")
            q = questions_by_target.get(t_id) or questions_by_num.get(f.question_numbers[0] if f.question_numbers else 1)
            color = q.color if q else default_color
            for kw in f.keywords:
                if kw.strip():
                    keywords_by_color[kw.strip().lower()] = color

        # 5. Walk body paragraphs directly from doc_data to guarantee 100% accurate alignment
        in_summary = False
        for elem in content:
            if "paragraph" not in elem:
                continue
            p_text = "".join(el.get("textRun", {}).get("content", "") for el in elem["paragraph"].get("elements", []))
            if SUMMARY_START_MARKER in p_text:
                in_summary = True
                continue
            if in_summary:
                if SUMMARY_END_MARKER in p_text:
                    in_summary = False
                continue
            if not p_text.strip():
                continue

            p_orig_start = elem["startIndex"]
            n = len(p_text)
            char_color: List[Optional[str]] = [None] * n
            char_bold: List[bool] = [False] * n

            # 1. Overlay keyword matches across paragraph
            for kw_lower, color in keywords_by_color.items():
                left_b = r"\b" if re.match(r"^\w", kw_lower) else ""
                right_b = r"\b" if re.search(r"\w$", kw_lower) else ""
                pattern = left_b + re.escape(kw_lower) + right_b
                for m in re.finditer(pattern, p_text, flags=re.IGNORECASE):
                    k_s = max(0, min(m.start(), n))
                    k_e = max(0, min(m.end(), n))
                    for i in range(k_s, k_e):
                        char_color[i] = color

            # 2. Locate answering snippets in this paragraph and overlay whole snippet spans
            snippet_spans: List[Tuple[int, int, str]] = []
            for f in findings_data.findings:
                pos = find_snippet_in_text(f.snippet_text, p_text)
                if pos:
                    t_id = f.target_ids[0] if f.target_ids else (f"Q{f.question_numbers[0]}" if f.question_numbers else "Q1")
                    q = questions_by_target.get(t_id) or questions_by_num.get(f.question_numbers[0] if f.question_numbers else 1)
                    s_color = q.color if q else default_color
                    snippet_spans.append((pos[0], pos[1], s_color))

            # Sort snippets by span length descending (shorter inner spans take precedence)
            for s_start, s_end, s_color in sorted(snippet_spans, key=lambda s: -(s[1] - s[0])):
                s = max(0, min(s_start, n))
                e = max(0, min(s_end, n))
                for i in range(s, e):
                    char_color[i] = s_color

            # 3. Bold keywords inside answering snippet spans
            for kw_lower, _ in keywords_by_color.items():
                left_b = r"\b" if re.match(r"^\w", kw_lower) else ""
                right_b = r"\b" if re.search(r"\w$", kw_lower) else ""
                pattern = left_b + re.escape(kw_lower) + right_b
                for m in re.finditer(pattern, p_text, flags=re.IGNORECASE):
                    k_s, k_e = m.start(), m.end()
                    if any(s[0] <= k_s and k_e <= s[1] for s in snippet_spans):
                        for i in range(max(0, k_s), min(n, k_e)):
                            char_bold[i] = True

            # 4. Collapse contiguous slices of identical styling
            i = 0
            while i < n:
                c = char_color[i]
                b = char_bold[i]
                start_i = i
                while i < n and char_color[i] == c and char_bold[i] == b:
                    i += 1
                end_i = i

                if c is not None or b:
                    abs_s = p_orig_start + shift + start_i
                    abs_e = p_orig_start + shift + end_i
                    if abs_s >= abs_e:
                        continue

                    text_style: Dict[str, Any] = {}
                    fields: List[str] = []
                    if c is not None:
                        text_style["backgroundColor"] = {
                            "color": {"rgbColor": hex_to_rgb_color(c)}
                        }
                        fields.append("backgroundColor")
                    if b:
                        text_style["bold"] = True
                        fields.append("bold")

                    requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": abs_s, "endIndex": abs_e},
                            "textStyle": text_style,
                            "fields": ",".join(fields),
                        }
                    })

        return requests

    def mutate(
        self,
        document_id: str,
        parsed: ParsedDocument,
        matches: List[LemmaMatch],
        findings_data: FindingsData,
        docs_service: Optional[Any] = None,
        storage_provider: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Applies summary block and highlights in-place via Docs API batchUpdate."""
        doc_id = document_id
        if storage_provider is not None and hasattr(storage_provider, "_resolve_target"):
            try:
                item = storage_provider._resolve_target(document_id)
                doc_id = item.id
            except Exception:
                doc_id = str(document_id)

        service = (
            docs_service
            or getattr(storage_provider, "docs_service", None)
            or self.docs_service
        )
        if service is None:
            import gdrive_auth
            service = gdrive_auth.get_docs_service()

        doc_data = service.documents().get(documentId=doc_id).execute()
        requests = self.build_mutation_requests(doc_data, parsed, matches, findings_data)
        if requests:
            return service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests},
            ).execute()
        return {"documentId": doc_id, "replies": []}

