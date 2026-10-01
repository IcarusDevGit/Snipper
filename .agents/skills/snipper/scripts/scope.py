"""Scope resolution and ancestor metadata inheritance for Library hierarchies."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import List, Optional, Set, Union

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from document import Concept


@dataclass
class ScopeResult:
    scope_type: str  # "local", "hierarchical", "global"
    target_path: Path
    library_root: Path
    scoped_directories: List[Path] = field(default_factory=list)
    scoped_files: List[Path] = field(default_factory=list)
    inherited_keywords: List[str] = field(default_factory=list)
    inherited_concepts: List[Concept] = field(default_factory=list)

    def is_in_scope(self, path: Path | str) -> bool:
        p = Path(path).resolve()
        for d in self.scoped_directories:
            try:
                p.relative_to(d)
                return True
            except ValueError:
                continue
        return False

    def get_scoped_findings_files(self) -> List[Path]:
        findings_files: List[Path] = []
        for d in self.scoped_directories:
            if d.is_dir():
                for f in d.glob("*.findings.json"):
                    if f not in findings_files:
                        findings_files.append(f)
            elif d.is_file() and d.name.endswith(".findings.json"):
                if d not in findings_files:
                    findings_files.append(d)
        return sorted(findings_files)

    def get_scoped_text_files(self) -> List[Path]:
        text_files: List[Path] = []
        for d in self.scoped_directories:
            if d.is_dir():
                for f in d.glob("*.txt"):
                    if (
                        not f.name.endswith(".keywords.txt")
                        and not f.name.endswith(".concepts.txt")
                        and not f.name.endswith(".questions.txt")
                        and f not in text_files
                    ):
                        text_files.append(f)
        return sorted(text_files)


class ScopeResolver:
    """Evaluates and enforces query boundaries and ancestor metadata inheritance."""

    def __init__(self, default_library_root: Optional[Path | str] = None):
        self.default_library_root = Path(default_library_root).resolve() if default_library_root else None

    def find_library_root(self, start_path: Path) -> Path:
        """Finds the root of the Library by looking for library markers or workspace root."""
        if self.default_library_root and self.default_library_root.exists():
            return self.default_library_root

        cur = start_path if start_path.is_dir() else start_path.parent
        cur = cur.resolve()

        # Check ancestors for library markers or workspace root
        for ancestor in [cur] + list(cur.parents):
            if (
                (ancestor / "library.keywords.txt").exists()
                or (ancestor / "library.concepts.txt").exists()
                or (ancestor / "openspec").exists()
                or (ancestor / ".git").exists()
            ):
                return ancestor

        return cur

    def parse_keywords_file(self, path: Path) -> List[str]:
        """Parses comma-separated or line-separated keywords from a file."""
        if not path.exists():
            return []
        keywords: List[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [k.strip() for k in re.split(r"[,;]", line) if k.strip()]
            keywords.extend(parts)
        return keywords

    def parse_concepts_file(self, path: Path) -> List[Concept]:
        """Parses concept definitions and citations from a concepts file."""
        if not path.exists():
            return []
        concepts: List[Concept] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Strip leading list markers
            cleaned = re.sub(r"^[-*•]\s*(?:concept:\s*)?", "", line, flags=re.IGNORECASE).strip()

            # Parse Name - Definition (Source: URL)
            source_url = None
            src_match = re.search(r"[\(\[]\s*source\s*:\s*([^\)\]]+)[\)\]]", cleaned, re.IGNORECASE)
            if src_match:
                source_url = src_match.group(1).strip()
                cleaned = re.sub(r"[\(\[]\s*source\s*:\s*[^\)\]]+[\)\]]", "", cleaned, flags=re.IGNORECASE).strip()

            if "-" in cleaned:
                parts = cleaned.split("-", 1)
                c_name = parts[0].strip()
                c_def = parts[1].strip()
            elif ":" in cleaned:
                parts = cleaned.split(":", 1)
                c_name = parts[0].strip()
                c_def = parts[1].strip()
            else:
                c_name = cleaned.strip()
                c_def = ""

            if c_name:
                concepts.append(
                    Concept(
                        name=c_name,
                        definition=c_def,
                        source_url=source_url,
                    )
                )
        return concepts

    def resolve(
        self,
        target_path: Optional[Path | str] = None,
        scope: Optional[str] = None,
        library_root: Optional[Path | str] = None,
    ) -> ScopeResult:
        """Resolves active scope directories, files, and inherited metadata."""
        # 1. Determine scope type
        if target_path is None or str(target_path).strip() == "":
            scope_type = "global"
        else:
            scope_type = (scope or "local").lower().strip()

        if scope_type not in ("local", "hierarchical", "global"):
            raise ValueError(f"Invalid scope type '{scope_type}'. Must be 'local', 'hierarchical', or 'global'.")

        # 2. Determine target path and library root
        if target_path is not None and str(target_path).strip():
            target = Path(target_path).resolve()
        else:
            target = Path(library_root).resolve() if library_root else Path.cwd().resolve()

        root = Path(library_root).resolve() if library_root else self.find_library_root(target)

        # 3. Resolve active scoped directories and files
        scoped_dirs: List[Path] = []
        scoped_files: List[Path] = []

        if scope_type == "global":
            scoped_dirs = [root]
            if root.is_dir():
                for item in root.rglob("*"):
                    if item.is_dir():
                        scoped_dirs.append(item)
                    elif item.is_file():
                        scoped_files.append(item)
        elif target.is_dir():
            # Module or Sub-module directory
            scoped_dirs = [target]
            for item in target.rglob("*"):
                if item.is_dir():
                    scoped_dirs.append(item)
                elif item.is_file():
                    scoped_files.append(item)
        else:
            # Specific entry file
            parent_dir = target.parent
            scoped_dirs = [parent_dir]
            prefix = target.stem
            # Include companion files sharing the prefix
            if parent_dir.is_dir():
                for item in parent_dir.iterdir():
                    if item.is_file() and (item.name.startswith(f"{prefix}.") or item.name == prefix):
                        scoped_files.append(item)

        # 4. Resolve inherited metadata (Hierarchical Scope)
        inherited_keywords: List[str] = []
        inherited_concepts: List[Concept] = []

        if scope_type == "hierarchical":
            start_dir = target if target.is_dir() else target.parent
            # Climb up from start_dir's parent to library root (inclusive)
            ancestors = []
            cur = start_dir.parent
            while True:
                ancestors.append(cur)
                if cur == root or cur == cur.parent:
                    break
                cur = cur.parent

            # Read from root down to parent
            for ancestor in reversed(ancestors):
                # Keywords files
                for kw_file in [ancestor / "library.keywords.txt", ancestor / "module.keywords.txt"]:
                    if kw_file.exists():
                        for kw in self.parse_keywords_file(kw_file):
                            if kw not in inherited_keywords:
                                inherited_keywords.append(kw)

                # Concepts files
                for c_file in [ancestor / "library.concepts.txt", ancestor / "module.concepts.txt"]:
                    if c_file.exists():
                        for concept in self.parse_concepts_file(c_file):
                            if not any(c.name.lower() == concept.name.lower() for c in inherited_concepts):
                                inherited_concepts.append(concept)

        return ScopeResult(
            scope_type=scope_type,
            target_path=target,
            library_root=root,
            scoped_directories=scoped_dirs,
            scoped_files=scoped_files,
            inherited_keywords=inherited_keywords,
            inherited_concepts=inherited_concepts,
        )
