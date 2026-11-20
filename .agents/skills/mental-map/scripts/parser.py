"""Document Parser for mental-map skill.

Parses .map documents from Google Docs (via Docs API or G: drive virtual mount)
and local Markdown / plain text .map files into a structured MentalMapModel.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
import re
import os
import sys
import json

# Ensure snipper scripts directory is in path for gdrive_auth if needed
_SNIPPER_SCRIPTS = Path(__file__).resolve().parents[2] / "snipper" / "scripts"
if _SNIPPER_SCRIPTS.exists() and str(_SNIPPER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SNIPPER_SCRIPTS))


@dataclass
class BulletNode:
    text: str
    nesting_level: int = 0
    id: str = ""
    parent_id: Optional[str] = None
    children: List["BulletNode"] = field(default_factory=list)


@dataclass
class ConceptNode:
    id: str
    text: str
    bullets: List[BulletNode] = field(default_factory=list)

    @property
    def is_parent(self) -> bool:
        return len(self.bullets) > 0


@dataclass
class SectionNode:
    id: str
    title: str
    concepts: List[ConceptNode] = field(default_factory=list)


@dataclass
class MentalMapModel:
    title: str
    sections: List[SectionNode] = field(default_factory=list)


def clean_title(raw_title: str) -> str:
    """Strip .map, .gdoc, .md extensions and extraneous formatting from title."""
    title = raw_title.strip()
    for ext in [".map.gdoc", ".gdoc", ".map", ".md", ".txt"]:
        if title.lower().endswith(ext):
            title = title[: -len(ext)].strip()
    return title


def find_gdoc_id_by_filename(filename: str) -> Optional[str]:
    """Find a Google Doc ID on Google Drive by matching filename variations."""
    try:
        import gdrive_auth  # type: ignore

        drive = gdrive_auth.get_drive_service()
        candidates = []
        name = filename.strip()
        if name.lower().endswith(".gdoc"):
            candidates.append(name[:-5].strip())
        if name.lower().endswith(".map.gdoc"):
            candidates.append(name[:-9].strip())
        candidates.append(clean_title(name))
        candidates.append(name)

        # 1. Exact match on candidates
        for cand in candidates:
            cand_escaped = cand.replace("'", "\\'")
            q = f"name = '{cand_escaped}' and trashed = false"
            res = drive.files().list(q=q, fields="files(id, name, mimeType)").execute()
            files = res.get("files", [])
            for f in files:
                if f.get("mimeType") == "application/vnd.google-apps.document":
                    return f["id"]

        # 2. Contains match on clean title
        base = clean_title(name).replace("'", "\\'")
        q = f"name contains '{base}' and trashed = false"
        res = drive.files().list(q=q, fields="files(id, name, mimeType)").execute()
        files = res.get("files", [])
        for f in files:
            if f.get("mimeType") == "application/vnd.google-apps.document":
                return f["id"]
    except Exception:
        pass
    return None


def extract_gdoc_id(source: str) -> Optional[str]:
    """Extract Google Doc ID from a URL, a raw ID string, or a .gdoc file."""
    # Match URL pattern
    url_match = re.search(r"/document/d/([a-zA-Z0-9_-]{25,})", source)
    if url_match:
        return url_match.group(1)

    # Check if string looks like a naked doc ID (typically 33-45 chars, alphanumeric with - and _)
    if re.fullmatch(r"[a-zA-Z0-9_-]{30,60}", source.strip()):
        return source.strip()

    # Check if it's a file path
    path = Path(source)
    if not path.exists() and path.parent.exists():
        target_stem = clean_title(path.name).lower()
        candidates = [f for f in path.parent.iterdir() if f.name.lower().endswith(".gdoc")]
        if ".map" in path.name.lower():
            map_candidates = [f for f in candidates if ".map" in f.name.lower()]
            if map_candidates:
                candidates = map_candidates
        for f in candidates:
            f_clean = clean_title(f.name).lower()
            if f_clean == target_stem or (len(f_clean) >= 5 and f_clean[:5] in target_stem):
                path = f
                break

    is_gdoc_ext = path.suffix.lower() == ".gdoc" or path.name.lower().endswith(".map.gdoc")
    if is_gdoc_ext or path.exists():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(content)
            if "doc_id" in data:
                return data["doc_id"]
            if "url" in data:
                url_m = re.search(r"/document/d/([a-zA-Z0-9_-]{25,})", data["url"])
                if url_m:
                    return url_m.group(1)
        except Exception:
            pass

        # If reading locally failed (e.g., G: drive virtual mount OSError 22) and it's a .gdoc,
        # search Drive API by filename
        if is_gdoc_ext or "G:\\" in str(source) or "G:/" in str(source):
            doc_id = find_gdoc_id_by_filename(path.name)
            if doc_id:
                return doc_id

    return None


def parse_google_doc(doc_id: str) -> MentalMapModel:
    """Fetch and parse a Google Doc via Google Docs API."""
    import gdrive_auth  # type: ignore

    docs_service = gdrive_auth.get_docs_service()
    doc = docs_service.documents().get(documentId=doc_id).execute()

    raw_title = doc.get("title", "Mapa Mental")
    title = clean_title(raw_title)

    body_content = doc.get("body", {}).get("content", [])
    sections: List[SectionNode] = []
    current_section: Optional[SectionNode] = None
    current_concept: Optional[ConceptNode] = None

    sec_idx = 0
    c_idx = 0
    b_idx = 0

    for elem in body_content:
        if "paragraph" not in elem:
            continue

        p = elem["paragraph"]
        p_style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        bullet = p.get("bullet")
        nesting_level = bullet.get("nestingLevel", 0) if bullet else None

        runs = []
        for pe in p.get("elements", []):
            if "textRun" in pe:
                tr = pe["textRun"]
                txt = tr.get("content", "")
                bold = tr.get("textStyle", {}).get("bold", False)
                runs.append((txt, bold))

        full_text = "".join(t for t, _ in runs).strip()
        if not full_text:
            continue

        # Check if non-whitespace text is bold
        non_ws_runs = [(t, b) for t, b in runs if t.strip()]
        is_all_bold = bool(non_ws_runs) and all(b for _, b in non_ws_runs)
        is_heading = p_style.startswith("HEADING_") or is_all_bold

        if is_heading and bullet is None:
            # New section
            sec_idx += 1
            current_section = SectionNode(
                id=f"sec_{sec_idx}",
                title=full_text,
                concepts=[]
            )
            sections.append(current_section)
            current_concept = None
            continue

        # Ensure we have an active section
        if current_section is None:
            sec_idx += 1
            current_section = SectionNode(
                id=f"sec_{sec_idx}",
                title="Geral",
                concepts=[]
            )
            sections.append(current_section)

        if bullet is not None:
            b_idx += 1
            lvl = nesting_level or 0
            bullet_node = BulletNode(
                text=full_text,
                nesting_level=lvl,
                id=f"b_{sec_idx}_{b_idx}"
            )

            # If no concept precedes, create an implicit parent
            if current_concept is None:
                c_idx += 1
                current_concept = ConceptNode(
                    id=f"c_{sec_idx}_{c_idx}",
                    text=current_section.title,
                    bullets=[]
                )
                current_section.concepts.append(current_concept)

            if lvl == 0:
                bullet_node.parent_id = current_concept.id
                current_concept.bullets.append(bullet_node)
            else:
                # Find parent bullet at lvl - 1 in the current concept
                parent_candidate: Optional[BulletNode] = None
                for prev_b in reversed(current_concept.bullets):
                    if prev_b.nesting_level == lvl - 1:
                        parent_candidate = prev_b
                        break
                    # Also search inside children recursively
                    def find_in_tree(node: BulletNode, target_lvl: int) -> Optional[BulletNode]:
                        if node.nesting_level == target_lvl:
                            return node
                        for ch in reversed(node.children):
                            res = find_in_tree(ch, target_lvl)
                            if res:
                                return res
                        return None
                    found = find_in_tree(prev_b, lvl - 1)
                    if found:
                        parent_candidate = found
                        break

                if parent_candidate:
                    bullet_node.parent_id = parent_candidate.id
                    parent_candidate.children.append(bullet_node)
                else:
                    # Fallback to current concept parent
                    bullet_node.parent_id = current_concept.id
                current_concept.bullets.append(bullet_node)
        else:
            # Concept Statement
            c_idx += 1
            current_concept = ConceptNode(
                id=f"c_{sec_idx}_{c_idx}",
                text=full_text,
                bullets=[]
            )
            current_section.concepts.append(current_concept)

    return MentalMapModel(title=title, sections=sections)


def parse_markdown_or_text(text: str, default_title: str = "Mapa Mental") -> MentalMapModel:
    """Parse local Markdown or plain text content."""
    lines = text.splitlines()
    title = default_title

    # Check if first non-empty line is a markdown title #
    first_lines = [l.strip() for l in lines if l.strip()]
    if first_lines and first_lines[0].startswith("# "):
        title = first_lines[0][2:].strip()
        lines = lines[lines.index(first_lines[0]) + 1 :]

    title = clean_title(title)

    sections: List[SectionNode] = []
    current_section: Optional[SectionNode] = None
    current_concept: Optional[ConceptNode] = None

    sec_idx = 0
    c_idx = 0
    b_idx = 0

    bullet_pattern = re.compile(r"^(\s*)[-*+]\s+(.*)$")
    subtitle_bold_pattern = re.compile(r"^\*\*(.+?)\*\*[:]?$")

    for raw_line in lines:
        line_stripped = raw_line.strip()
        if not line_stripped:
            continue

        # Check section subtitle: ## Subtitle or **Subtitle**
        is_heading = False
        subtitle_text = ""
        if line_stripped.startswith("## ") or line_stripped.startswith("### "):
            is_heading = True
            subtitle_text = line_stripped.lstrip("#").strip()
        elif subtitle_bold_pattern.match(line_stripped):
            is_heading = True
            m = subtitle_bold_pattern.match(line_stripped)
            subtitle_text = m.group(1).strip() if m else line_stripped

        if is_heading:
            sec_idx += 1
            current_section = SectionNode(
                id=f"sec_{sec_idx}",
                title=subtitle_text,
                concepts=[]
            )
            sections.append(current_section)
            current_concept = None
            continue

        # Ensure active section
        if current_section is None:
            sec_idx += 1
            current_section = SectionNode(
                id=f"sec_{sec_idx}",
                title="Geral",
                concepts=[]
            )
            sections.append(current_section)

        # Bullet check
        b_match = bullet_pattern.match(raw_line)
        if b_match:
            b_idx += 1
            indent_spaces = len(b_match.group(1))
            lvl = indent_spaces // 2  # 2 spaces per level
            bullet_text = b_match.group(2).strip()

            bullet_node = BulletNode(
                text=bullet_text,
                nesting_level=lvl,
                id=f"b_{sec_idx}_{b_idx}"
            )

            if current_concept is None:
                c_idx += 1
                current_concept = ConceptNode(
                    id=f"c_{sec_idx}_{c_idx}",
                    text=current_section.title,
                    bullets=[]
                )
                current_section.concepts.append(current_concept)

            if lvl == 0:
                bullet_node.parent_id = current_concept.id
            else:
                # Find parent bullet at lvl - 1
                parent_candidate: Optional[BulletNode] = None
                for prev_b in reversed(current_concept.bullets):
                    if prev_b.nesting_level == lvl - 1:
                        parent_candidate = prev_b
                        break
                if parent_candidate:
                    bullet_node.parent_id = parent_candidate.id
                    parent_candidate.children.append(bullet_node)
                else:
                    bullet_node.parent_id = current_concept.id

            current_concept.bullets.append(bullet_node)
        else:
            # Normal concept statement
            c_idx += 1
            current_concept = ConceptNode(
                id=f"c_{sec_idx}_{c_idx}",
                text=line_stripped,
                bullets=[]
            )
            current_section.concepts.append(current_concept)

    return MentalMapModel(title=title, sections=sections)


def parse_document(source: Union[str, Path]) -> MentalMapModel:
    """Unified entry point to parse a document from URL, Doc ID, file path, or text."""
    src_str = str(source).strip()

    # 1. Try Google Doc ID / URL / .gdoc extraction
    gdoc_id = extract_gdoc_id(src_str)
    if gdoc_id:
        return parse_google_doc(gdoc_id)

    path = Path(src_str)
    is_gdoc_ext = path.suffix.lower() == ".gdoc" or path.name.lower().endswith(".map.gdoc")

    # If it's a .gdoc file, resolve via Google Drive API
    if is_gdoc_ext:
        doc_id = find_gdoc_id_by_filename(path.name)
        if doc_id:
            return parse_google_doc(doc_id)

    # 2. Local file path (non-gdoc)
    if path.exists() and path.is_file() and not is_gdoc_ext:
        default_title = clean_title(path.name)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return parse_markdown_or_text(text, default_title=default_title)
        except OSError:
            pass

    # 3. Check if path is in G: drive virtual mount
    if "G:\\" in src_str or "G:/" in src_str:
        doc_id = find_gdoc_id_by_filename(path.name)
        if doc_id:
            return parse_google_doc(doc_id)

    # 4. Fallback: Fail clearly if source looks like a missing file path; otherwise parse raw text
    if "\n" not in src_str and path.suffix.lower() in (".map", ".md", ".txt", ".gdoc"):
        raise FileNotFoundError(f"Input file not found: {src_str}")

    return parse_markdown_or_text(src_str)

