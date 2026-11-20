"""Configuration loader for Snipper constraint and palette files."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import List, Optional
import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_PALETTE = [
    "#ea7286",
    "#eab281",
    "#e3e19f",
    "#a9c484",
    "#5d937b",
    "#a07ca7",
    "#f4a4bf",
    "#f5d1b6",
    "#eeede3",
    "#d6cec2",
    "#a2a6a9",
    "#777f8f",
    "#a3b2d2",
    "#bfded8",
    "#bf796d",
]


def resolve_constraints_path(
    path: Optional[Path | str] = None,
    document_path: Optional[Path | str] = None,
) -> Optional[Path]:
    """Resolves the CustomConstraints.md configuration file from candidate locations."""
    if path:
        p = Path(path)
        if p.exists():
            return p

    candidates: List[Path] = []
    # 1. Skill root relative paths (parent of scripts directory is skill root)
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    candidates.append(skill_root / "references" / "CustomConstraints.md")
    candidates.append(skill_root / "CustomConstraints.md")

    # 2. Document location relative paths
    if document_path:
        doc_p = Path(document_path)
        candidates.append(doc_p.parent / "CustomConstraints.md")
        candidates.append(doc_p.parent / "references" / "CustomConstraints.md")

    # 3. Standard skill directory locations
    candidates.append(Path(".agents/skills/snipper/references/CustomConstraints.md"))
    candidates.append(Path(".agents/skills/snipper/CustomConstraints.md"))
    candidates.append(Path("test-skill-directory/references/CustomConstraints.md"))
    candidates.append(Path("references/CustomConstraints.md"))
    candidates.append(Path("CustomConstraints.md"))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def resolve_palette_file(document_path: Optional[Path | str] = None) -> Optional[Path]:
    """Resolves palette.md from candidate locations."""
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    candidates = [
        skill_root / "assets" / "palette.md",
        Path(".agents/skills/snipper/assets/palette.md"),
        Path("test-skill-directory/assets/palette.md"),
        Path("assets/palette.md"),
    ]
    if document_path:
        doc_p = Path(document_path)
        candidates.append(doc_p.parent / "assets" / "palette.md")

    for c in candidates:
        if c.exists():
            return c
    return None


def load_palette_from_file(palette_file: Path) -> List[str]:
    """Loads hex color list from palette.md file."""
    try:
        content = palette_file.read_text(encoding="utf-8")
        colors = []
        for line in content.splitlines():
            line = line.strip().strip('"').strip("'")
            if line.startswith("#") and len(line) == 7:
                colors.append(line)
        return colors if colors else list(DEFAULT_PALETTE)
    except Exception:
        return list(DEFAULT_PALETTE)


@dataclass
class SnipperConfig:
    language: str = "auto"
    allow_web_search: bool = False
    proper_nouns_only: bool = False
    palette_mode: str = "hex"
    palette_order: str = "sequential"
    palette: List[str] = field(default_factory=lambda: list(DEFAULT_PALETTE))
    storage_backend: str = "local"
    library_folder_id: Optional[str] = None
    metadata_filename: str = "module.metadata"

    @classmethod
    def from_file(
        cls,
        path: Optional[Path | str] = None,
        document_path: Optional[Path | str] = None,
    ) -> "SnipperConfig":
        resolved_path = resolve_constraints_path(path, document_path)
        palette_file = resolve_palette_file(document_path)
        file_palette = load_palette_from_file(palette_file) if palette_file else list(DEFAULT_PALETTE)

        if not resolved_path:
            return cls(palette=file_palette)

        content = resolved_path.read_text(encoding="utf-8")
        # Extract YAML from code fence if present
        yaml_match = re.search(r"```yaml\s*(.*?)\s*```", content, re.DOTALL)
        raw_text = yaml_match.group(1) if yaml_match else content

        try:
            parsed = yaml.safe_load(raw_text) or {}
            cfg = parsed.get("configuration", parsed)
            if not isinstance(cfg, dict):
                return cls(palette=file_palette)

            # Palette precedence: YAML config > assets/palette.md > DEFAULT_PALETTE
            palette_val = cfg.get("palette")
            if palette_val and isinstance(palette_val, list):
                active_palette = list(palette_val)
            else:
                active_palette = file_palette

            # Storage configuration (flat or nested)
            storage_dict = cfg.get("storage", {}) if isinstance(cfg.get("storage"), dict) else {}
            storage_backend = str(
                cfg.get("storage_backend", storage_dict.get("backend", "local"))
            ).lower().strip()
            library_folder_id = cfg.get("library_folder_id", storage_dict.get("library_folder_id"))
            if library_folder_id is not None:
                library_folder_id = str(library_folder_id).strip()
            metadata_filename = str(
                cfg.get("metadata_filename", storage_dict.get("metadata_filename", "module.metadata"))
            ).strip()

            return cls(
                language=str(cfg.get("language", "auto")).strip(),
                allow_web_search=bool(cfg.get("allow_web_search", False)),
                proper_nouns_only=bool(cfg.get("proper_nouns_only", False)),
                palette_mode=str(cfg.get("palette_mode", "hex")).lower().strip(),
                palette_order=str(cfg.get("palette_order", "sequential")).lower().strip(),
                palette=active_palette,
                storage_backend=storage_backend,
                library_folder_id=library_folder_id,
                metadata_filename=metadata_filename,
            )
        except Exception:
            return cls(palette=file_palette)


# Compatibility aliases
HighlighterConfig = SnipperConfig
HighliterConfig = SnipperConfig
