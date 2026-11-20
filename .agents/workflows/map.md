---
description: "Convert hierarchical .map notes and Google Docs into structured, zero-line modular Draw.io mental maps with directional arrows and harmonic palettes."
---

# /map Workflow

Transform hierarchical notes, lecture summaries, and study documents (`.map` files, Markdown `.md`, or Google Docs) into modular, zero-line Draw.io (`.drawio`) diagrams with curved directional arrows, dynamic card height calculation, adaptive row wrapping, and harmonic palettes.

**Input**:
- Target path to `.map`, `.md`, or `.gdoc` file, Google Docs URL, or Google Doc ID.
- Optional flags:
  - `--overwrite`: Overwrite existing diagram files (default is to preserve previous versions with `(v2)`, `(v3)...`).
  - `--open`: Automatically launch the diagram in your web browser ([app.diagrams.net](https://app.diagrams.net)).
  - `-o, --output <path>`: Custom destination path or directory.
  - `--no-gdrive`: Local filesystem save only (skip Google Drive cloud upload).

---

## Steps

### 1. Identify Target Document
1. If the user provided a Google Docs URL or Doc ID:
   - Example: `https://docs.google.com/document/d/<document_id>/edit` or `<document_id>`
2. If the user provided a local file or Google Drive mount path (`G:\`):
   - Example: `"examples/mental-map/Equipping Agents with Agent Skills.map"`
   - Example: `"G:\My Drive\Notes\Study Topic.map"`

### 2. Execution
Run the mental-map CLI generator:

```bash
# Standard run (preserves existing files with versioning)
python .agents/skills/mental-map/scripts/cli.py "<target_path_or_url>"

# In-place overwrite (updates diagram while preserving Google Drive file ID)
python .agents/skills/mental-map/scripts/cli.py "<target_path_or_url>" --overwrite

# Open directly in browser upon generation
python .agents/skills/mental-map/scripts/cli.py "<target_path_or_url>" --open
```

### 3. Pipeline Invariants & Output Verification
1. **Title Stripping**: The document title is the filename stripped of `.map`, `.gdoc`, or `.md`.
2. **Subtitle Bolding**: Subtitles formatted in bold (or Markdown `## ` / `**bold**`) become distinct section headers.
3. **Curved Directional Arrows**: Bullet points (`•`, `- `) translate into curved orthogonal arrows (`exitX=1, exitY=0.5` to `entryX=0, entryY=0.5`). Multi-tier nested bullets ($A \rightarrow B \rightarrow C$) render chained arrows.
4. **Adaptive Layout**:
   - 1–3 sections: Panoramic horizontal columns.
   - 4+ sections: Wrapped multi-row grid matrix (e.g. 2 rows of 2–3 columns).
5. **Dynamic Height**: Card heights are dynamically computed to ensure full verbatim sentences remain visible without clipping.
6. **Strict XML Validation**: The diagram is pre-validated with `xml.etree.ElementTree` before disk write to guarantee zero Draw.io syntax errors.
7. **Cloud & Local Links**: Output provides local file path, Google Drive cloud file ID, and a 1-click launch link (`https://app.diagrams.net/#G<file_id>`).
