"""Scope resolution and ancestor metadata inheritance for Library hierarchies."""

from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import Any, List, Optional, Set, Tuple, Union

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from document import Concept


@dataclass
class ScopeResult:
    scope_type: str  # "local", "hierarchical", "global"
    target_path: Union[Path, str]
    library_root: Union[Path, str]
    scoped_directories: List[Union[Path, str]] = field(default_factory=list)
    scoped_files: List[Union[Path, str]] = field(default_factory=list)
    inherited_keywords: List[str] = field(default_factory=list)
    inherited_concepts: List[Concept] = field(default_factory=list)
    storage_provider: Optional[Any] = None

    def is_in_scope(self, path: Path | str) -> bool:
        if self.storage_provider is not None:
            p_str = str(path)
            for d in self.scoped_directories:
                if str(d) == p_str or p_str.startswith(str(d)):
                    return True
            return False

        p = Path(path).resolve()
        for d in self.scoped_directories:
            try:
                p.relative_to(Path(d).resolve())
                return True
            except ValueError:
                continue
        return False

    def get_scoped_findings_files(self) -> List[Union[Path, str]]:
        if self.storage_provider is not None:
            findings_files: List[Union[Path, str]] = []
            for d in self.scoped_directories:
                for f in self.storage_provider.list_files(d, "*.findings.json"):
                    if f not in findings_files:
                        findings_files.append(f)
            return sorted(findings_files, key=str)

        findings_files: List[Path] = []
        for d in self.scoped_directories:
            p_d = Path(d)
            if p_d.is_dir():
                for f in p_d.glob("*.findings.json"):
                    if f not in findings_files:
                        findings_files.append(f)
            elif p_d.is_file() and p_d.name.endswith(".findings.json"):
                if p_d not in findings_files:
                    findings_files.append(p_d)
        return sorted(findings_files)

    def get_scoped_text_files(self) -> List[Union[Path, str]]:
        if self.storage_provider is not None:
            text_files: List[Union[Path, str]] = []
            for d in self.scoped_directories:
                for f in self.storage_provider.list_files(d, "*.txt"):
                    f_str = str(f)
                    if (
                        not f_str.endswith(".keywords.txt")
                        and not f_str.endswith(".concepts.txt")
                        and not f_str.endswith(".questions.txt")
                        and f not in text_files
                    ):
                        text_files.append(f)
            return sorted(text_files, key=str)

        text_files: List[Path] = []
        for d in self.scoped_directories:
            p_d = Path(d)
            if p_d.is_dir():
                for f in p_d.glob("*.txt"):
                    if (
                        not f.name.endswith(".keywords.txt")
                        and not f.name.endswith(".concepts.txt")
                        and not f.name.endswith(".questions.txt")
                        and f not in text_files
                    ):
                        text_files.append(f)
        return sorted(text_files)


def parse_metadata_text(text: str) -> Tuple[List[str], List[Concept]]:
    """Parses combined keywords and concepts from a module.metadata text string."""
    keywords: List[str] = []
    concepts: List[Concept] = []
    current_section: Optional[str] = None

    kw_header_re = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*|__)?(?:keywords?|palavras-chave)(?:\*\*|__)?\s*:?\s*(.*)$",
        re.IGNORECASE,
    )
    concept_header_re = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*|__)?(?:concepts?|conceitos?)(?:\*\*|__)?\s*:?\s*(.*)$",
        re.IGNORECASE,
    )
    kw_bullet_re = re.compile(
        r"^\s*[-*•]\s*(?:keywords?|palavras-chave)\s*:\s*(.+)$",
        re.IGNORECASE,
    )
    concept_bullet_re = re.compile(
        r"^\s*[-*•]\s*(?:concepts?|conceitos?)\s*:\s*(.+)$",
        re.IGNORECASE,
    )

    def _parse_concept_item(raw_item: str) -> Optional[Concept]:
        cleaned = re.sub(r"^[-*•]\s*(?:concept:\s*)?", "", raw_item, flags=re.IGNORECASE).strip()
        source_url = None
        src_match = re.search(r"[\(\[]\s*source\s*:\s*([^\)\]]+)[\)\]]", cleaned, re.IGNORECASE)
        if src_match:
            source_url = src_match.group(1).strip()
            cleaned = re.sub(r"[\(\[]\s*source\s*:\s*[^\)\]]+[\)\]]", "", cleaned, flags=re.IGNORECASE).strip()

        web_search = bool(re.search(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", cleaned, re.IGNORECASE))
        cleaned = re.sub(r"[\(\[]\s*web(?:\s*:\s*true)?\s*[\)\]]", "", cleaned, flags=re.IGNORECASE).strip()

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
            return Concept(name=c_name, definition=c_def, source_url=source_url, web_search=web_search)
        return None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        kw_b = kw_bullet_re.match(line)
        if kw_b:
            for item in re.split(r"[,;]", kw_b.group(1)):
                k = item.strip()
                if k and k not in keywords:
                    keywords.append(k)
            continue

        cp_b = concept_bullet_re.match(line)
        if cp_b:
            c_obj = _parse_concept_item(cp_b.group(1))
            if c_obj and not any(c.name.lower() == c_obj.name.lower() for c in concepts):
                concepts.append(c_obj)
            continue

        kw_h = kw_header_re.match(line)
        if kw_h:
            current_section = "keywords"
            rest = kw_h.group(1).strip()
            if rest:
                for item in re.split(r"[,;]", rest):
                    k = item.strip()
                    if k and k not in keywords:
                        keywords.append(k)
            continue

        cp_h = concept_header_re.match(line)
        if cp_h:
            current_section = "concepts"
            rest = cp_h.group(1).strip()
            if rest:
                c_obj = _parse_concept_item(rest)
                if c_obj and not any(c.name.lower() == c_obj.name.lower() for c in concepts):
                    concepts.append(c_obj)
            continue

        if current_section == "keywords":
            cleaned = re.sub(r"^[-*•]\s*", "", line).strip()
            for item in re.split(r"[,;]", cleaned):
                k = item.strip()
                if k and k not in keywords:
                    keywords.append(k)
        elif current_section == "concepts":
            c_obj = _parse_concept_item(line)
            if c_obj and not any(c.name.lower() == c_obj.name.lower() for c in concepts):
                concepts.append(c_obj)

    return keywords, concepts


class ScopeResolver:
    """Evaluates and enforces query boundaries and ancestor metadata inheritance."""

    def __init__(
        self,
        default_library_root: Optional[Union[Path, str]] = None,
        storage_provider: Optional[Any] = None,
    ):
        self.storage_provider = storage_provider
        if default_library_root and not isinstance(default_library_root, str):
            self.default_library_root = Path(default_library_root).resolve()
        else:
            self.default_library_root = default_library_root

    def find_library_root(self, start_path: Path) -> Path:
        """Finds the root of the Library by looking for library markers or workspace root."""
        if self.default_library_root and isinstance(self.default_library_root, Path) and self.default_library_root.exists():
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

    def parse_keywords_text(self, text: str) -> List[str]:
        """Parses comma-separated or line-separated keywords from text."""
        keywords: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [k.strip() for k in re.split(r"[,;]", line) if k.strip()]
            keywords.extend(parts)
        return keywords

    def parse_keywords_file(self, path: Path) -> List[str]:
        """Parses comma-separated or line-separated keywords from a file."""
        if not path.exists():
            return []
        return self.parse_keywords_text(path.read_text(encoding="utf-8"))

    def parse_concepts_text(self, text: str) -> List[Concept]:
        """Parses concept definitions and citations from text."""
        concepts: List[Concept] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            cleaned = re.sub(r"^[-*•]\s*(?:concept:\s*)?", "", line, flags=re.IGNORECASE).strip()
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

    def parse_concepts_file(self, path: Path) -> List[Concept]:
        """Parses concept definitions and citations from a concepts file."""
        if not path.exists():
            return []
        return self.parse_concepts_text(path.read_text(encoding="utf-8"))

    def parse_metadata_file(self, path: Path) -> Tuple[List[str], List[Concept]]:
        """Parses combined keywords and concepts from a module.metadata file."""
        if not path.exists():
            return [], []
        return parse_metadata_text(path.read_text(encoding="utf-8"))

    def resolve(
        self,
        target_path: Optional[Union[Path, str]] = None,
        scope: Optional[str] = None,
        library_root: Optional[Union[Path, str]] = None,
    ) -> ScopeResult:
        """Resolves active scope directories, files, and inherited metadata."""
        # 1. Determine scope type
        if target_path is None or str(target_path).strip() == "":
            scope_type = "global"
        else:
            scope_type = (scope or "local").lower().strip()

        if scope_type not in ("local", "hierarchical", "global"):
            raise ValueError(f"Invalid scope type '{scope_type}'. Must be 'local', 'hierarchical', or 'global'.")

        # 2. Check if storage_provider handles Google Drive / remote storage
        if self.storage_provider is not None and getattr(self.storage_provider, "library_folder_id", None):
            root_id = getattr(self.storage_provider, "library_folder_id")
            target_str = str(target_path or "")
            target_item = self.storage_provider._resolve_target(target_str) if target_str else None

            if scope_type == "global":
                scoped_dirs = [root_id]
            elif target_item:
                target_folder_id = target_item.id if target_item.is_folder else (target_item.parent_id or root_id)
                scoped_dirs = [target_folder_id]
            else:
                scoped_dirs = [root_id]

            inherited_keywords: List[str] = []
            inherited_concepts: List[Concept] = []

            if scope_type == "hierarchical":
                normalized_target = target_str.replace("\\", "/").strip("/")
                if target_item and not target_item.is_folder and "/" in normalized_target:
                    start_dir = normalized_target.rsplit("/", 1)[0]
                elif target_item and not target_item.is_folder:
                    start_dir = ""
                else:
                    start_dir = normalized_target

                ancestors: List[str] = []
                cur = start_dir.rsplit("/", 1)[0] if "/" in start_dir else ("" if start_dir else "")
                while True:
                    ancestors.append(cur)
                    if not cur:
                        break
                    cur = cur.rsplit("/", 1)[0] if "/" in cur else ""

                for ancestor in reversed(ancestors):
                    prefix = f"{ancestor}/" if ancestor else ""
                    # Check module.metadata
                    meta_candidates = [
                        f"{prefix}module.metadata",
                        f"{prefix}module.metadata.gdoc",
                        f"{prefix}module.metadata.txt",
                    ]
                    if not ancestor:
                        meta_candidates.extend([
                            "library.metadata",
                            "library.metadata.gdoc",
                            "library.metadata.txt",
                        ])
                    for mc in meta_candidates:
                        if self.storage_provider.exists(mc):
                            m_text = self.storage_provider.read_text(mc)
                            kws, cpts = parse_metadata_text(m_text)
                            for kw in kws:
                                if kw not in inherited_keywords:
                                    inherited_keywords.append(kw)
                            for cpt in cpts:
                                if not any(c.name.lower() == cpt.name.lower() for c in inherited_concepts):
                                    inherited_concepts.append(cpt)
                            break

                    # Check keywords
                    kw_candidates = [f"{prefix}module.keywords.txt"]
                    if not ancestor:
                        kw_candidates.append("library.keywords.txt")
                    for kc in kw_candidates:
                        if self.storage_provider.exists(kc):
                            k_text = self.storage_provider.read_text(kc)
                            for kw in self.parse_keywords_text(k_text):
                                if kw not in inherited_keywords:
                                    inherited_keywords.append(kw)

                    # Check concepts
                    c_candidates = [f"{prefix}module.concepts.txt"]
                    if not ancestor:
                        c_candidates.append("library.concepts.txt")
                    for cc in c_candidates:
                        if self.storage_provider.exists(cc):
                            c_text = self.storage_provider.read_text(cc)
                            for cpt in self.parse_concepts_text(c_text):
                                if not any(c.name.lower() == cpt.name.lower() for c in inherited_concepts):
                                    inherited_concepts.append(cpt)

            return ScopeResult(
                scope_type=scope_type,
                target_path=target_str,
                library_root=root_id,
                scoped_directories=scoped_dirs,
                scoped_files=[],
                inherited_keywords=inherited_keywords,
                inherited_concepts=inherited_concepts,
                storage_provider=self.storage_provider,
            )

        # 3. Determine target path and library root for local storage
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
                # Combined module.metadata
                for meta_file in [
                    ancestor / "module.metadata",
                    ancestor / "module.metadata.gdoc",
                    ancestor / "module.metadata.txt",
                    ancestor / "library.metadata",
                    ancestor / "library.metadata.gdoc",
                    ancestor / "library.metadata.txt",
                ]:
                    if meta_file.exists():
                        kws, cpts = self.parse_metadata_file(meta_file)
                        for kw in kws:
                            if kw not in inherited_keywords:
                                inherited_keywords.append(kw)
                        for concept in cpts:
                            if not any(c.name.lower() == concept.name.lower() for c in inherited_concepts):
                                inherited_concepts.append(concept)
                        break

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
