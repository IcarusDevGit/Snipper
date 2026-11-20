"""Adaptive Layout and Arrow Geometry Engine for mental-map skill.

Arranges sections panoramically (1–3 sections) or in an adaptive multi-row grid (4+ sections),
computes dynamic card heights to prevent text clipping, and generates curved orthogonal
arrows with multi-tier chained offsets (A -> B -> C).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import math
import re
from parser import MentalMapModel, SectionNode, ConceptNode, BulletNode


@dataclass
class LayoutNode:
    id: str
    label: str
    node_type: str  # 'banner', 'section_header', 'concept', 'parent', 'bullet'
    x: int
    y: int
    width: int
    height: int
    section_index: int = 0
    nesting_level: int = 0
    tooltip: str = ""


@dataclass
class LayoutEdge:
    id: str
    source_id: str
    target_id: str
    color: str = "#6366f1"
    stroke_width: int = 2


@dataclass
class DiagramLayout:
    title: str
    nodes: List[LayoutNode] = field(default_factory=list)
    edges: List[LayoutEdge] = field(default_factory=list)
    canvas_width: int = 2200
    canvas_height: int = 900


def calculate_card_height(text: str, width: int, base_padding: int = 22, line_height: int = 18, min_height: int = 40) -> int:
    """Dynamically compute card height from character count and width to prevent text clipping."""
    if not text:
        return min_height

    # Approximate character width ~7.5px with horizontal padding subtracted
    usable_width = max(60, width - 28)
    chars_per_line = max(10, int(usable_width / 7.5))

    # Account for explicit newlines as well as wrapped lines
    lines = text.split("\n")
    total_lines = 0
    for l in lines:
        stripped = l.strip()
        wrapped = max(1, math.ceil(len(stripped) / chars_per_line)) if stripped else 1
        total_lines += wrapped

    computed = base_padding + (total_lines * line_height)
    return max(min_height, computed)


def is_horizontal_concept(concept: ConceptNode) -> bool:
    """Detect if a concept should be rendered as a single horizontal table/card without arrows."""
    t = concept.text.strip().lower()
    return (
        "regras de inferência" in t
        or "regras de inferencia" in t
        or "[horizontal]" in t
        or "[tabela]" in t
        or "[card]" in t
        or "[no-arrows]" in t
    )


def build_horizontal_card_label_and_height(concept: ConceptNode, col_width: int) -> Tuple[str, int]:
    """Format bullet records of a horizontal concept into a rich, elegant HTML table/card."""
    title_text = concept.text
    for tag in ["[horizontal]", "[tabela]", "[card]", "[no-arrows]"]:
        title_text = re.sub(re.escape(tag), "", title_text, flags=re.IGNORECASE)
    title_text = title_text.strip(" :-\t")
    if not title_text:
        title_text = "REGRAS DE INFERÊNCIA"

    # Canonical logic rules data for propositional logic
    canonical_rules = {
        "adição": {
            "name": "Regra da Adição (AD)",
            "struct": "A partir de premissa <i>p</i>, conclui-se a disjunção <i>p ∨ q</i> &nbsp;(<i>p ⊢ p ∨ q</i>)",
            "example": "De \"A temperatura está baixa\" (<i>p</i>), infere-se \"A temperatura está baixa ou há nevoeiro\" (<i>p ∨ q</i>)",
        },
        "simplificação": {
            "name": "Regra da Simplificação (SIMP)",
            "struct": "A partir de premissa conjuntiva <i>p ∧ q</i>, conclui-se <i>p</i> ou <i>q</i> &nbsp;(<i>p ∧ q ⊢ p</i>)",
            "example": "De \"A temp. está baixa e há nevoeiro\" (<i>p ∧ q</i>), infere-se \"A temp. está baixa\" (<i>p</i>)",
        },
        "modus ponens": {
            "name": "Modus Ponens (MP)",
            "struct": "Dadas as premissas <i>p → q</i> e <i>p</i>, infere-se a conclusão <i>q</i> &nbsp;(<i>p → q, p ⊢ q</i>)",
            "example": "De \"Se temp. baixa então nevoeiro\" e \"temp. baixa\", conclui-se \"Há nevoeiro\" (<i>q</i>)",
        },
        "modus tollens": {
            "name": "Modus Tollens (MT)",
            "struct": "Dadas as premissas <i>p → q</i> e <i>~q</i>, infere-se a conclusão <i>~p</i> &nbsp;(<i>p → q, ~q ⊢ ~p</i>)",
            "example": "De \"Se temp. baixa então nevoeiro\" e \"Não há nevoeiro\", conclui-se \"Temp. não está baixa\" (<i>~p</i>)",
        },
        "silogismo hipotético": {
            "name": "Silogismo Hipotético (SH)",
            "struct": "Dadas premissas condicionais <i>p → q</i> e <i>q → r</i>, conclui-se <i>p → r</i> &nbsp;(<i>p → q, q → r ⊢ p → r</i>)",
            "example": "De \"Temp. baixa ⇒ nevoeiro\" e \"Nevoeiro ⇒ sem voos\", obtém-se \"Temp. baixa ⇒ sem voos\"",
        },
        "silogismo disjuntivo": {
            "name": "Silogismo Disjuntivo (SD)",
            "struct": "Dadas as premissas <i>p ∨ q</i> e <i>~p</i> (ou <i>~q</i>), conclui-se <i>q</i> (ou <i>p</i>)",
            "example": "De \"Temp. baixa ou nevoeiro\" e \"Temp. não está baixa\", conclui-se \"Há nevoeiro\" (<i>q</i>)",
        },
        "conjunção": {
            "name": "Regra da Conjunção (CONJ)",
            "struct": "Dadas duas premissas <i>p</i> e <i>q</i>, conclui-se a conjunção <i>p ∧ q</i> &nbsp;(<i>p, q ⊢ p ∧ q</i>)",
            "example": "De \"Temp. baixa\" (<i>p</i>) e \"Há nevoeiro\" (<i>q</i>), conclui-se \"Temp. baixa e há nevoeiro\" (<i>p ∧ q</i>)",
        },
    }

    # Group bullets into records
    records = []
    current_rec = None
    for b in concept.bullets:
        txt = b.text.strip()
        if b.nesting_level == 0:
            current_rec = {"title": txt.rstrip(":"), "estrutura": "", "exemplo": "", "raw": []}
            records.append(current_rec)
        else:
            if current_rec is not None:
                current_rec["raw"].append(txt)
                if txt.lower().startswith("estrutura:"):
                    current_rec["estrutura"] = txt[10:].strip()
                elif txt.lower().startswith("exemplo:"):
                    current_rec["exemplo"] = txt[8:].strip()
            else:
                records.append({"title": txt, "estrutura": "", "exemplo": "", "raw": []})

    rows_html = []
    for idx, rec in enumerate(records):
        bg = "#faf5ff" if idx % 2 == 1 else "#ffffff"
        r_name = rec["title"]
        r_struct = rec["estrutura"]
        r_ex = rec["exemplo"]

        # Check canonical match for propositional logic rules
        for k, v in canonical_rules.items():
            if k in r_name.lower():
                r_name = v["name"]
                if not r_struct or len(r_struct) < 15 or "premissa ," in r_struct:
                    r_struct = v["struct"]
                if not r_ex or len(r_ex) < 15:
                    r_ex = v["example"]
                break

        if not r_struct and rec["raw"]:
            r_struct = " &bull; ".join(rec["raw"])

        row = (
            f'<tr style="background-color: {bg}; border-bottom: 1px solid #ede9fe;">'
            f'<td style="padding: 6px 10px; font-weight: bold; color: #5b21b6; vertical-align: top; white-space: nowrap;">{r_name}</td>'
            f'<td style="padding: 6px 10px; color: #1e293b; vertical-align: top;">{r_struct}</td>'
            f'<td style="padding: 6px 10px; color: #475569; font-size: 10px; vertical-align: top;">{r_ex}</td>'
            f'</tr>'
        )
        rows_html.append(row)

    table_body = "".join(rows_html)

    html_label = (
        f'<div style="text-align: center; font-size: 13px; font-weight: bold; color: #5b21b6; margin-bottom: 8px;">'
        f'{title_text.upper()}'
        f'</div>'
        f'<table style="width: 100%; border-collapse: collapse; font-size: 11px; text-align: left;" cellpadding="4">'
        f'<thead>'
        f'<tr style="background-color: #ede9fe; color: #4c1d95; font-weight: bold; border-bottom: 1px solid #c4b5fd;">'
        f'<th style="padding: 6px 10px; width: 22%;">Regra</th>'
        f'<th style="padding: 6px 10px; width: 40%;">Estrutura Lógica</th>'
        f'<th style="padding: 6px 10px; width: 38%;">Exemplo</th>'
        f'</tr>'
        f'</thead>'
        f'<tbody>'
        f'{table_body}'
        f'</tbody>'
        f'</table>'
    )

    computed_h = 35 + 28 + (len(records) * 48) + 30
    final_h = max(180, computed_h)

    return html_label, final_h


def build_layout(model: MentalMapModel) -> DiagramLayout:
    """Build coordinates and connections for all nodes and edges."""
    sections = model.sections
    num_sections = len(sections)

    margin_x = 80
    margin_y = 40
    banner_height = 70
    col_gap = 40
    row_gap = 55
    item_gap = 14

    nodes: List[LayoutNode] = []
    edges: List[LayoutEdge] = []
    edge_counter = 0

    # 1. Determine Grid Structure
    # 1-3 sections -> 1 panoramic row
    # 4 sections -> 2 rows of 2
    # 5 sections -> Row 1 (3 cols), Row 2 (2 cols)
    # 6 sections -> 2 rows of 3
    # 7+ sections -> 3 cols per row
    if num_sections <= 3:
        rows_partition = [sections]
    elif num_sections == 4:
        rows_partition = [sections[0:2], sections[2:4]]
    elif num_sections == 5:
        rows_partition = [sections[0:3], sections[3:5]]
    elif num_sections == 6:
        rows_partition = [sections[0:3], sections[3:6]]
    else:
        # Generic 3 columns per row
        rows_partition = []
        for i in range(0, num_sections, 3):
            rows_partition.append(sections[i : i + 3])

    # Target total width: around 2000px - 2200px
    target_canvas_w = 2160
    content_w = target_canvas_w - (2 * margin_x)

    # Add Title Banner
    banner_label = (
        f"<b>{model.title.upper()}</b>"
        f"<br/><font color='#94a3b8' size='2'>Mapa Mental Conceitual &bull; Síntese Estruturada</font>"
    )
    nodes.append(
        LayoutNode(
            id="header_banner",
            label=banner_label,
            node_type="banner",
            x=margin_x,
            y=margin_y,
            width=content_w,
            height=banner_height,
            tooltip=model.title,
        )
    )

    current_row_y = margin_y + banner_height + 30
    global_sec_idx = 0

    for row_sections in rows_partition:
        cols_in_row = len(row_sections)
        total_gaps = (cols_in_row - 1) * col_gap
        col_width = (content_w - total_gaps) // cols_in_row

        row_max_bottom = current_row_y

        for col_idx, sec in enumerate(row_sections):
            global_sec_idx += 1
            sec_x = margin_x + col_idx * (col_width + col_gap)
            sec_y = current_row_y

            # Section Header
            sec_header_h = 48
            sec_label = f"<b>{global_sec_idx}. {sec.title}</b>"
            sec_header_id = f"sub_{sec.id}"
            nodes.append(
                LayoutNode(
                    id=sec_header_id,
                    label=sec_label,
                    node_type="section_header",
                    x=sec_x,
                    y=sec_y,
                    width=col_width,
                    height=sec_header_h,
                    section_index=global_sec_idx,
                    tooltip=sec.title,
                )
            )

            curr_y = sec_y + sec_header_h + item_gap

            for c_idx, concept in enumerate(sec.concepts):
                if is_horizontal_concept(concept):
                    card_label, card_h = build_horizontal_card_label_and_height(concept, col_width)
                    nodes.append(
                        LayoutNode(
                            id=concept.id,
                            label=card_label,
                            node_type="horizontal_card",
                            x=sec_x,
                            y=curr_y,
                            width=col_width,
                            height=card_h,
                            section_index=global_sec_idx,
                            tooltip=concept.text,
                        )
                    )
                    curr_y += card_h + item_gap
                elif not concept.is_parent:
                    # Standalone full-width concept card
                    c_h = calculate_card_height(concept.text, col_width)
                    nodes.append(
                        LayoutNode(
                            id=concept.id,
                            label=concept.text,
                            node_type="concept",
                            x=sec_x,
                            y=curr_y,
                            width=col_width,
                            height=c_h,
                            section_index=global_sec_idx,
                        )
                    )
                    curr_y += c_h + item_gap
                else:
                    # Concept with Bullets (Directional Curved Arrows)
                    # Check max nesting level in this concept
                    all_bullets = concept.bullets
                    max_lvl = max((b.nesting_level for b in all_bullets), default=0)

                    # Determine horizontal widths based on nesting tiers
                    arrow_gap = 45
                    if max_lvl == 0:
                        # 2 columns: Parent -> Bullets
                        parent_w = min(240, int(col_width * 0.38))
                        bullet_w = col_width - parent_w - arrow_gap
                        tier_widths = {0: bullet_w}
                        tier_offsets = {0: parent_w + arrow_gap}
                    else:
                        # Multi-tier chained arrows (Parent -> L0 -> L1 ...)
                        num_tiers = max_lvl + 1
                        parent_w = min(200, int(col_width * 0.28))
                        remaining_w = col_width - parent_w - (num_tiers * arrow_gap)
                        tier_w = max(180, remaining_w // num_tiers)

                        tier_widths = {}
                        tier_offsets = {}
                        for lvl in range(num_tiers):
                            tier_widths[lvl] = tier_w
                            tier_offsets[lvl] = parent_w + arrow_gap + lvl * (tier_w + arrow_gap)

                    # Build parent->children map for hierarchical tree layout so chained arrows stay aligned
                    bullet_by_id = {b.id: b for b in all_bullets}
                    children_map: Dict[str, List[BulletNode]] = {b.id: [] for b in all_bullets}
                    root_bullets: List[BulletNode] = []
                    for b in all_bullets:
                        if b.parent_id and b.parent_id in bullet_by_id and b.parent_id != b.id:
                            children_map[b.parent_id].append(b)
                        else:
                            root_bullets.append(b)

                    bullet_gap = 10
                    own_heights: Dict[str, int] = {}
                    subtree_heights: Dict[str, int] = {}

                    def _compute_heights(node: BulletNode) -> int:
                        b_w = tier_widths.get(node.nesting_level, 200)
                        own_h = calculate_card_height(node.text, b_w, base_padding=18, min_height=38)
                        own_heights[node.id] = own_h
                        kids = children_map[node.id]
                        if not kids:
                            subtree_heights[node.id] = own_h
                            return own_h
                        kids_total_h = sum(_compute_heights(k) for k in kids) + bullet_gap * (len(kids) - 1)
                        sub_h = max(own_h, kids_total_h)
                        subtree_heights[node.id] = sub_h
                        return sub_h

                    for rb in root_bullets:
                        _compute_heights(rb)

                    bullet_layout_items: List[Tuple[BulletNode, int, int, int, int]] = []

                    def _place_subtree(node: BulletNode, y_top: int) -> None:
                        b_lvl = node.nesting_level
                        b_w = tier_widths.get(b_lvl, 200)
                        b_x = sec_x + tier_offsets.get(b_lvl, parent_w + arrow_gap)
                        own_h = own_heights[node.id]
                        sub_h = subtree_heights[node.id]

                        # Vertically center node within its subtree band so single-child arrows are straight
                        b_y = y_top + (sub_h - own_h) // 2
                        bullet_layout_items.append((node, b_x, b_y, b_w, own_h))

                        kids = children_map[node.id]
                        if kids:
                            kids_total_h = sum(subtree_heights[k.id] for k in kids) + bullet_gap * (len(kids) - 1)
                            kid_y = y_top + (sub_h - kids_total_h) // 2
                            for kid in kids:
                                _place_subtree(kid, kid_y)
                                kid_y += subtree_heights[kid.id] + bullet_gap

                    b_y_cursor = curr_y
                    for rb in root_bullets:
                        _place_subtree(rb, b_y_cursor)
                        b_y_cursor += subtree_heights[rb.id] + bullet_gap

                    total_bullets_h = max(40, b_y_cursor - curr_y - bullet_gap)
                    parent_h = max(calculate_card_height(concept.text, parent_w, min_height=45), total_bullets_h)

                    # Add parent card
                    nodes.append(
                        LayoutNode(
                            id=concept.id,
                            label=concept.text,
                            node_type="parent",
                            x=sec_x,
                            y=curr_y,
                            width=parent_w,
                            height=parent_h,
                            section_index=global_sec_idx,
                        )
                    )

                    # Add bullet nodes and connecting edges
                    for b, bx, by, bw, bh in bullet_layout_items:
                        nodes.append(
                            LayoutNode(
                                id=b.id,
                                label=b.text,
                                node_type="bullet",
                                x=bx,
                                y=by,
                                width=bw,
                                height=bh,
                                section_index=global_sec_idx,
                                nesting_level=b.nesting_level,
                            )
                        )

                        # Create Edge: parent_id -> b.id
                        source_id = b.parent_id if b.parent_id else concept.id
                        edge_counter += 1
                        edges.append(
                            LayoutEdge(
                                id=f"edge_{edge_counter}",
                                source_id=source_id,
                                target_id=b.id,
                            )
                        )

                    curr_y = max(curr_y + parent_h, b_y_cursor) + item_gap

            row_max_bottom = max(row_max_bottom, curr_y)

        # Move cursor for next row
        current_row_y = row_max_bottom + row_gap

    canvas_h = max(900, current_row_y + 40)
    return DiagramLayout(
        title=model.title,
        nodes=nodes,
        edges=edges,
        canvas_width=target_canvas_w,
        canvas_height=canvas_h,
    )
