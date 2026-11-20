---
name: mental-map
description: Converts hierarchical .map notes and Google Docs into zero-line modular Draw.io mental maps with directional arrows and harmonic color themes.
compatibility: Requires Python 3.10+, google-api-python-client, google-auth
allowed-tools: Bash(python:*, pytest:*)
license: MIT
metadata:
  author: mental-map
  version: "0.1"
---

# Mental Map Skill - Automated Draw.io Mind Mapper

`mental-map` transforms structured study notes, hierarchical summaries, and lecture documents (`.map`) into clean, professional Draw.io (`.drawio`) diagrams. It saves diagrams directly to your local workspace, the local Google Drive desktop mount (`G:\`), and the Google Drive cloud, providing a 1-click launch link in [app.diagrams.net](https://app.diagrams.net).

---

## 1. Document Syntax & Authoring Conventions

Authoring a `.map` document in Google Docs or Markdown follows standard, intuitive habits:

| Document Element | Authoring Rule | Rendered in Draw.io |
| :--- | :--- | :--- |
| **Title** | File name ending in `.map` | Main top header banner (stripped of `.map`) |
| **Subtitles** | Formatted in **Bold** | Section column/container headers with harmonic theme colors |
| **Statements** | Regular plain text paragraphs | Primary concept cards |
| **Bullet Points** | List items (`•` or `- `) | Child cards connected with **curved directional arrows** (`--->`) |
| **Nested Bullets** | Indented list items (Level 2+) | Chained multi-tier arrows ($A \rightarrow B \rightarrow C$) |
| **Horizontal Tables** | Concept containing `[horizontal]` or "Regras de inferência" | Rendered as a unified full-width horizontal card with structured HTML table (zero individual arrows) |

---

## 2. Workflow & CLI Usage

### Slash Command (`/map`)
```
/map <path_or_url> [--overwrite] [--open]
```
Examples:
- `/map "examples/mental-map/Equipping Agents with Agent Skills.map"`
- `/map "https://docs.google.com/document/d/<doc_id>/edit" --overwrite --open`
- `/map "G:\My Drive\Notes\Study Topic.map"`

### Python CLI
```bash
# Generate locally from a .map or .md file (skipping Google Drive upload)
python .agents/skills/mental-map/scripts/cli.py "examples/mental-map/Equipping Agents with Agent Skills.map" --no-gdrive

# Generate from a Google Doc URL
python .agents/skills/mental-map/scripts/cli.py "https://docs.google.com/document/d/<document_id>/edit"

# Overwrite existing diagram in-place (preserving Google Drive file ID)
python .agents/skills/mental-map/scripts/cli.py "<path_or_url>" --overwrite

# Automatically launch diagrams.net in default browser after generation
python .agents/skills/mental-map/scripts/cli.py "<path_or_url>" --open
```

---

## 3. Architecture & Modular Layout

```
+---------------------------------------------------------------------------------+
| TOP HEADER BANNER: Document Title                                              |
+---------------------------------------------------------------------------------+
  SECTION 1 (Indigo Theme)       SECTION 2 (Emerald Theme)      SECTION 3 (Amber)
  +-------------------------+    +-------------------------+    +---------------+
  | Bold Subtitle 1         |    | Bold Subtitle 2         |    | Bold Subtitle |
  | Base Concept Card       |    | Base Concept Card       |    | Base Card     |
  | Parent Statement        |    | Parent Statement        |    | Parent        |
  |   |                     |    |   |                     |    |   |           |
  |   +--> Bullet Card (L1) |    |   +--> Bullet Card (L1) |    |   +--> Bullet |
  |          |              |    |          |              |    +---------------+
  |          +--> L2 Chained|    |          +--> L2 Chained|
  +-------------------------+    +-------------------------+
```

* **Adaptive Row Wrapping**: Documents with 1–3 sections render as a panoramic horizontal strip. Documents with 4+ sections automatically wrap into balanced multi-row grids.
* **Harmonic Palette Cycle**: Automatically cycles through curated themes (Indigo, Emerald, Amber, Rose, Cyan, Slate).
* **Strict XML Safety**: All text is strictly XML-escaped and validated with `xml.etree.ElementTree` prior to saving.
