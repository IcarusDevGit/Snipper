"""Draw.io XML Emitter and Exporter for mental-map skill.

Transforms DiagramLayout into strictly-escaped, ElementTree-validated Draw.io XML
and saves the result to local filesystem and/or Google Drive with versioning / overwrite support.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import xml.sax.saxutils as saxutils
import xml.etree.ElementTree as ET
import sys
import io

from layout import DiagramLayout, LayoutNode, LayoutEdge

# Ensure snipper scripts directory is in path for gdrive_auth if needed
_SNIPPER_SCRIPTS = Path(__file__).resolve().parents[2] / "snipper" / "scripts"
if _SNIPPER_SCRIPTS.exists() and str(_SNIPPER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SNIPPER_SCRIPTS))


PALETTES = [
    # 0: Indigo
    {
        "header_fill": "#e0e7ff",
        "header_stroke": "#a5b4fc",
        "header_font": "#3730a3",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#a5b4fc",
        "parent_font": "#1e293b",
        "b0_fill": "#fdf4ff",
        "b0_stroke": "#f0abfc",
        "b0_font": "#86198f",
        "b1_fill": "#fae8ff",
        "b1_stroke": "#e879f9",
        "b1_font": "#701a75",
        "edge_l0": "#6366f1",
        "edge_l1": "#a855f7",
    },
    # 1: Emerald
    {
        "header_fill": "#d1fae5",
        "header_stroke": "#6ee7b7",
        "header_font": "#065f46",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#6ee7b7",
        "parent_font": "#1e293b",
        "b0_fill": "#ecfdf5",
        "b0_stroke": "#a7f3d0",
        "b0_font": "#065f46",
        "b1_fill": "#d1fae5",
        "b1_stroke": "#34d399",
        "b1_font": "#047857",
        "edge_l0": "#10b981",
        "edge_l1": "#059669",
    },
    # 2: Amber
    {
        "header_fill": "#fef3c7",
        "header_stroke": "#fcd34d",
        "header_font": "#92400e",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#fcd34d",
        "parent_font": "#1e293b",
        "b0_fill": "#fffbeb",
        "b0_stroke": "#fde68a",
        "b0_font": "#92400e",
        "b1_fill": "#fef3c7",
        "b1_stroke": "#f59e0b",
        "b1_font": "#78350f",
        "edge_l0": "#f59e0b",
        "edge_l1": "#d97706",
    },
    # 3: Rose
    {
        "header_fill": "#ffe4e6",
        "header_stroke": "#fda4af",
        "header_font": "#9f1239",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#fda4af",
        "parent_font": "#1e293b",
        "b0_fill": "#fff1f2",
        "b0_stroke": "#fecdd3",
        "b0_font": "#9f1239",
        "b1_fill": "#ffe4e6",
        "b1_stroke": "#fb7185",
        "b1_font": "#881337",
        "edge_l0": "#f43f5e",
        "edge_l1": "#e11d48",
    },
    # 4: Cyan / Sky
    {
        "header_fill": "#e0f2fe",
        "header_stroke": "#7dd3fc",
        "header_font": "#0369a1",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#7dd3fc",
        "parent_font": "#1e293b",
        "b0_fill": "#f0f9ff",
        "b0_stroke": "#bae6fd",
        "b0_font": "#0369a1",
        "b1_fill": "#e0f2fe",
        "b1_stroke": "#38bdf8",
        "b1_font": "#0c4a6e",
        "edge_l0": "#0284c7",
        "edge_l1": "#0369a1",
    },
    # 5: Slate / Violet
    {
        "header_fill": "#ede9fe",
        "header_stroke": "#c4b5fd",
        "header_font": "#5b21b6",
        "parent_fill": "#f8fafc",
        "parent_stroke": "#c4b5fd",
        "parent_font": "#1e293b",
        "b0_fill": "#f5f3ff",
        "b0_stroke": "#ddd6fe",
        "b0_font": "#5b21b6",
        "b1_fill": "#ede9fe",
        "b1_stroke": "#a78bfa",
        "b1_font": "#4c1d95",
        "edge_l0": "#8b5cf6",
        "edge_l1": "#7c3aed",
    },
]


def esc(text: str) -> str:
    """Strictly escape text and attribute strings for Draw.io XML."""
    return saxutils.escape(str(text), {'"': "&quot;", "'": "&apos;"})


def get_palette(section_index: int) -> Dict[str, str]:
    """Cycle palette based on section index (1-based)."""
    idx = max(0, section_index - 1) % len(PALETTES)
    return PALETTES[idx]


def build_node_style(node: LayoutNode) -> str:
    """Generate mxGraph styling string for a node."""
    if node.node_type == "banner":
        return (
            "rounded=1;whiteSpace=wrap;html=1;fillColor=#0f172a;strokeColor=#1e293b;"
            "fontColor=#ffffff;fontStyle=1;fontSize=16;arcSize=8;shadow=1;"
        )

    pal = get_palette(node.section_index)

    if node.node_type == "section_header":
        return (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={pal['header_fill']};"
            f"strokeColor={pal['header_stroke']};fontColor={pal['header_font']};"
            f"fontStyle=1;fontSize=14;arcSize=10;shadow=1;"
        )
    elif node.node_type == "parent":
        return (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={pal['parent_fill']};"
            f"strokeColor={pal['parent_stroke']};fontColor={pal['parent_font']};"
            f"fontSize=12;fontStyle=1;align=center;shadow=1;"
        )
    elif node.node_type == "bullet":
        if node.nesting_level == 0:
            return (
                f"rounded=1;whiteSpace=wrap;html=1;fillColor={pal['b0_fill']};"
                f"strokeColor={pal['b0_stroke']};fontColor={pal['b0_font']};"
                f"fontSize=11;align=left;spacingLeft=10;shadow=1;"
            )
        else:
            return (
                f"rounded=1;whiteSpace=wrap;html=1;fillColor={pal['b1_fill']};"
                f"strokeColor={pal['b1_stroke']};fontColor={pal['b1_font']};"
                f"fontSize=10;align=left;spacingLeft=8;shadow=1;"
            )
    elif node.node_type == "horizontal_card":
        return (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor={pal['header_stroke']};"
            f"fontColor=#1e293b;fontSize=11;align=left;spacing=10;shadow=1;strokeWidth=1.5;"
        )
    else:
        # Default concept card
        return (
            "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#cbd5e1;"
            "fontColor=#1e293b;fontSize=12;align=left;spacingLeft=12;spacingRight=12;shadow=1;"
        )


def build_edge_style(edge: LayoutEdge, section_index: int = 1, is_chained: bool = False) -> str:
    """Generate mxGraph styling string for an orthogonal curved edge."""
    pal = get_palette(section_index)
    color = pal["edge_l1"] if is_chained else pal["edge_l0"]
    return (
        f"edgeStyle=orthogonalEdgeStyle;curved=1;endArrow=classic;html=1;"
        f"strokeColor={color};strokeWidth={edge.stroke_width};fillColor={color};"
        f"entryX=0;entryY=0.5;entryDx=0;entryDy=0;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
    )


def emit_drawio_xml(layout: DiagramLayout) -> str:
    """Serialize layout into strictly validated Draw.io XML."""
    xml_elements: List[str] = []

    # Map node IDs to node objects for quick lookup
    node_map = {n.id: n for n in layout.nodes}

    # 1. Emit Nodes
    for node in layout.nodes:
        style = build_node_style(node)
        tooltip_attr = f' tooltip="{esc(node.tooltip)}"' if node.tooltip else ""
        xml_elements.append(
            f'<object id="{node.id}" label="{esc(node.label)}"{tooltip_attr}>\n'
            f'  <mxCell style="{esc(style)}" vertex="1" parent="1">\n'
            f'    <mxGeometry x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" as="geometry"/>\n'
            f'  </mxCell>\n'
            f'</object>'
        )

    # 2. Emit Edges
    for edge in layout.edges:
        target_node = node_map.get(edge.target_id)
        sec_idx = target_node.section_index if target_node else 1
        is_chained = target_node.nesting_level > 0 if target_node else False
        style = build_edge_style(edge, section_index=sec_idx, is_chained=is_chained)

        xml_elements.append(
            f'<mxCell id="{edge.id}" style="{esc(style)}" parent="1" source="{edge.source_id}" target="{edge.target_id}" edge="1">\n'
            f'  <mxGeometry relative="1" as="geometry"/>\n'
            f'</mxCell>'
        )

    xml_body = "\n        ".join(xml_elements)
    clean_diagram_name = esc(layout.title)

    drawio_xml = f"""<mxfile host="app.diagrams.net" agent="MentalMap" version="21.0.0" type="google">
  <diagram id="MentalMap" name="{clean_diagram_name}">
    <mxGraphModel dx="{layout.canvas_width + 400}" dy="{layout.canvas_height + 400}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{layout.canvas_width}" pageHeight="{layout.canvas_height}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        {xml_body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""

    # Strict ElementTree validation
    try:
        ET.fromstring(drawio_xml)
    except ET.ParseError as e:
        raise ValueError(f"CRITICAL XML VALIDATION FAILURE: Draw.io XML has invalid syntax: {e}")

    return drawio_xml


def get_versioned_path(target_path: Path) -> Path:
    """Generate a versioned filepath if the target already exists (e.g., 'File (v2).drawio')."""
    if not target_path.exists():
        return target_path

    base_stem = target_path.stem
    ext = target_path.suffix
    parent = target_path.parent

    # If stem already has (vN), strip it
    import re
    m = re.match(r"^(.*?)\s*\(v(\d+)\)$", base_stem)
    if m:
        base_stem = m.group(1)

    version = 2
    while True:
        candidate = parent / f"{base_stem} (v{version}){ext}"
        if not candidate.exists():
            return candidate
        version += 1


def save_diagram(
    xml_content: str,
    output_path: Path,
    overwrite: bool = False,
    sync_gdrive: bool = True
) -> Dict[str, Any]:
    """Save XML to local disk and/or Google Drive with overwrite support."""
    result: Dict[str, Any] = {
        "local_path": None,
        "gdrive_file_id": None,
        "diagrams_net_url": None,
        "overwritten": False,
    }

    # Determine final local path
    final_path = output_path
    if output_path.exists() and not overwrite:
        final_path = get_versioned_path(output_path)
        result["overwritten"] = False
    else:
        result["overwritten"] = output_path.exists()

    final_path.parent.mkdir(parents=True, exist_ok=True)
    drawio_bytes = xml_content.encode("utf-8")
    final_path.write_bytes(drawio_bytes)
    result["local_path"] = str(final_path)

    # If file is on G:\ or sync_gdrive is True, handle Google Drive sync
    is_on_g_drive = "G:\\" in str(final_path) or "G:/" in str(final_path)
    if sync_gdrive or is_on_g_drive:
        try:
            import gdrive_auth  # type: ignore
            from googleapiclient.http import MediaIoBaseUpload  # type: ignore

            drive = gdrive_auth.get_drive_service()
            filename = final_path.name
            mime_type = "application/vnd.jgraph.mxfile"

            # Search if file already exists on Drive
            q = f"name = '{filename}' and trashed = false"
            res = drive.files().list(q=q, fields="files(id, name, webViewLink, parents)").execute()
            files = res.get("files", [])

            # Identify parent folder on Drive if path is within a folder
            parent_folder_id = None
            if "My Drive" in str(final_path.parent) or final_path.parent.name:
                folder_name = final_path.parent.name
                fq = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                try:
                    fres = drive.files().list(q=fq, fields="files(id, name)").execute()
                    ffiles = fres.get("files", [])
                    if ffiles:
                        parent_folder_id = ffiles[0]["id"]
                except Exception:
                    pass

            media = MediaIoBaseUpload(io.BytesIO(drawio_bytes), mimetype=mime_type, resumable=True)

            if files and overwrite:
                file_id = files[0]["id"]
                updated = drive.files().update(fileId=file_id, media_body=media, fields="id, name, webViewLink").execute()
                result["gdrive_file_id"] = updated["id"]
                result["diagrams_net_url"] = f"https://app.diagrams.net/#G{updated['id']}"
            else:
                body = {"name": filename, "mimeType": mime_type}
                if parent_folder_id:
                    body["parents"] = [parent_folder_id]
                if files and not overwrite:
                    # Create versioned on drive if exists
                    body["name"] = final_path.name
                created = drive.files().create(body=body, media_body=media, fields="id, name, webViewLink").execute()
                result["gdrive_file_id"] = created["id"]
                result["diagrams_net_url"] = f"https://app.diagrams.net/#G{created['id']}"
        except Exception as e:
            result["gdrive_sync_error"] = str(e)

    return result
