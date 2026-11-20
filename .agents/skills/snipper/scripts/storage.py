"""Storage abstraction layer supporting local filesystem and Google Drive in-memory operations."""

from dataclasses import dataclass
import io
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig


class StorageProvider(Protocol):
    """Protocol defining file and stream operations across storage backends."""

    def read_stream(self, target: Union[str, Path]) -> io.BytesIO:
        """Reads file content into an in-memory byte buffer."""
        ...

    def read_text(self, target: Union[str, Path], encoding: str = "utf-8") -> str:
        """Reads text content from file."""
        ...

    def write_stream(
        self,
        target_dir: Union[str, Path],
        filename: str,
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> str:
        """Writes byte stream to a target directory, returning the created file identifier/path."""
        ...

    def write_text(
        self,
        target_dir: Union[str, Path],
        filename: str,
        text: str,
        encoding: str = "utf-8",
    ) -> str:
        """Writes text content to a target directory, returning the created file identifier/path."""
        ...

    def update_stream(
        self,
        target: Union[str, Path],
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> None:
        """Updates an existing document in-place using new stream bytes."""
        ...

    def exists(self, target: Union[str, Path]) -> bool:
        """Checks if a file or directory exists."""
        ...

    def list_files(
        self,
        target_dir: Union[str, Path],
        pattern: Optional[str] = None,
    ) -> List[str]:
        """Lists file paths or identifiers in a directory matching an optional glob/name pattern."""
        ...


class LocalStorageProvider:
    """Standard local filesystem storage provider backed by pathlib.Path."""

    def __init__(self, backend: str = "local"):
        self.backend = backend
        self.storage_backend = backend

    def read_stream(self, target: Union[str, Path]) -> io.BytesIO:
        p = Path(target).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Local file not found: {p}")
        return io.BytesIO(p.read_bytes())

    def read_text(self, target: Union[str, Path], encoding: str = "utf-8") -> str:
        p = Path(target).resolve()
        return p.read_text(encoding=encoding)

    def write_stream(
        self,
        target_dir: Union[str, Path],
        filename: str,
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> str:
        p_dir = Path(target_dir).resolve()
        p_dir.mkdir(parents=True, exist_ok=True)
        dest = p_dir / filename
        dest.write_bytes(stream.getvalue())
        return str(dest)

    def write_text(
        self,
        target_dir: Union[str, Path],
        filename: str,
        text: str,
        encoding: str = "utf-8",
    ) -> str:
        p_dir = Path(target_dir).resolve()
        p_dir.mkdir(parents=True, exist_ok=True)
        dest = p_dir / filename
        dest.write_text(text, encoding=encoding)
        return str(dest)

    def update_stream(
        self,
        target: Union[str, Path],
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> None:
        dest = Path(target).resolve()
        dest.write_bytes(stream.getvalue())

    def exists(self, target: Union[str, Path]) -> bool:
        return Path(target).resolve().exists()

    def list_files(
        self,
        target_dir: Union[str, Path],
        pattern: Optional[str] = None,
    ) -> List[str]:
        p = Path(target_dir).resolve()
        if not p.exists():
            return []
        if p.is_file():
            return [str(p)]
        pat = pattern or "*"
        return [str(f) for f in p.glob(pat) if f.is_file()]


@dataclass
class DriveItem:
    id: str
    name: str
    parent_id: Optional[str] = None
    is_folder: bool = False
    mime_type: Optional[str] = None


class DrivePathResolver:
    """Resolves slash-separated Drive Paths ('Module/SubModule/entry.docx') to Drive IDs."""

    def __init__(self, drive_service: Any, root_folder_id: str):
        self.service = drive_service
        self.root_folder_id = root_folder_id
        self._cache: Dict[Tuple[str, str], DriveItem] = {}

    def resolve(self, path_str: str) -> DriveItem:
        """Resolves a slash-separated path relative to root_folder_id."""
        cleaned = path_str.strip().strip("/").strip("\\")
        if not cleaned:
            return DriveItem(id=self.root_folder_id, name="root", is_folder=True)

        segments = [s for s in re.split(r"[/\\]+", cleaned) if s]
        lower_segs = [s.lower() for s in segments]
        if "library" in lower_segs:
            idx = lower_segs.index("library")
            segments = segments[idx + 1:]

        current_parent = self.root_folder_id
        current_item = DriveItem(id=self.root_folder_id, name="root", is_folder=True)

        for segment in segments:
            cache_key = (current_parent, segment)
            if cache_key in self._cache:
                current_item = self._cache[cache_key]
                current_parent = current_item.id
                continue

            clean_seg = segment[:-5] if segment.endswith(".gdoc") else segment
            if clean_seg != segment:
                name_filter = f"(name = '{segment}' or name = '{clean_seg}')"
            else:
                name_filter = f"name = '{segment}'"

            query = (
                f"'{current_parent}' in parents and {name_filter} and trashed = false"
            )
            response = (
                self.service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, parents)",
                    pageSize=10,
                )
                .execute()
            )
            files = response.get("files", [])
            if not files:
                raise FileNotFoundError(
                    f"Drive path component '{segment}' not found under folder '{current_parent}'"
                )

            item_data = files[0]
            is_folder = (
                item_data.get("mimeType") == "application/vnd.google-apps.folder"
            )
            current_item = DriveItem(
                id=item_data["id"],
                name=item_data["name"],
                parent_id=current_parent,
                is_folder=is_folder,
                mime_type=item_data.get("mimeType"),
            )
            self._cache[cache_key] = current_item
            current_parent = current_item.id

        return current_item


class GoogleDriveStorage:
    """In-memory Google Drive storage provider operating via Drive API v3 without local disk persistence."""

    def __init__(
        self,
        drive_service: Any,
        library_folder_id: str,
        resolver: Optional[DrivePathResolver] = None,
        docs_service: Optional[Any] = None,
        backend: str = "gdrive",
    ):
        self.service = drive_service
        self.library_folder_id = library_folder_id
        self.resolver = resolver or DrivePathResolver(drive_service, library_folder_id)
        self.docs_service = docs_service
        self.backend = backend
        self.storage_backend = backend

    def _resolve_target(self, target: Union[str, Path]) -> DriveItem:
        t_str = str(target)
        # If already an exact Google Drive alphanumeric ID (length >= 25 without slashes)
        if re.match(r"^[a-zA-Z0-9_-]{25,}$", t_str):
            res = (
                self.service.files()
                .get(fileId=t_str, fields="id, name, mimeType, parents")
                .execute()
            )
            is_folder = res.get("mimeType") == "application/vnd.google-apps.folder"
            parents = res.get("parents", [])
            return DriveItem(
                id=res["id"],
                name=res["name"],
                parent_id=parents[0] if parents else None,
                is_folder=is_folder,
                mime_type=res.get("mimeType"),
            )
        return self.resolver.resolve(t_str)

    def read_stream(self, target: Union[str, Path]) -> io.BytesIO:
        item = self._resolve_target(target)
        if item.mime_type == "application/vnd.google-apps.document":
            response_bytes = (
                self.service.files()
                .export(fileId=item.id, mimeType="text/plain")
                .execute()
            )
            if isinstance(response_bytes, str):
                response_bytes = response_bytes.encode("utf-8")
            return io.BytesIO(response_bytes)

        response_bytes = (
            self.service.files().get_media(fileId=item.id).execute()
        )
        if isinstance(response_bytes, str):
            response_bytes = response_bytes.encode("utf-8")
        return io.BytesIO(response_bytes)

    def read_text(self, target: Union[str, Path], encoding: str = "utf-8") -> str:
        stream = self.read_stream(target)
        return stream.getvalue().decode(encoding)

    def write_stream(
        self,
        target_dir: Union[str, Path],
        filename: str,
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> str:
        from googleapiclient.http import MediaIoBaseUpload

        folder_item = self._resolve_target(target_dir)
        parent_id = folder_item.id

        # Check if file with exact name already exists in target folder
        query = f"'{parent_id}' in parents and name = '{filename}' and trashed = false"
        res = self.service.files().list(q=query, fields="files(id)").execute()
        files = res.get("files", [])

        stream.seek(0)
        media = MediaIoBaseUpload(stream, mimetype=mimetype, resumable=False)

        if files:
            file_id = files[0]["id"]
            self.service.files().update(fileId=file_id, media_body=media).execute()
            return file_id

        meta = {"name": filename, "parents": [parent_id]}
        created = (
            self.service.files()
            .create(body=meta, media_body=media, fields="id")
            .execute()
        )
        return created["id"]

    def write_text(
        self,
        target_dir: Union[str, Path],
        filename: str,
        text: str,
        encoding: str = "utf-8",
    ) -> str:
        stream = io.BytesIO(text.encode(encoding))
        return self.write_stream(
            target_dir=target_dir,
            filename=filename,
            stream=stream,
            mimetype="text/plain; charset=utf-8",
        )

    def update_stream(
        self,
        target: Union[str, Path],
        stream: io.BytesIO,
        mimetype: str = "application/octet-stream",
    ) -> None:
        from googleapiclient.http import MediaIoBaseUpload

        item = self._resolve_target(target)
        stream.seek(0)
        media = MediaIoBaseUpload(stream, mimetype=mimetype, resumable=False)
        self.service.files().update(fileId=item.id, media_body=media).execute()

    def exists(self, target: Union[str, Path]) -> bool:
        try:
            self._resolve_target(target)
            return True
        except Exception:
            return False

    def list_files(
        self,
        target_dir: Union[str, Path],
        pattern: Optional[str] = None,
    ) -> List[str]:
        folder_item = self._resolve_target(target_dir)
        query = f"'{folder_item.id}' in parents and trashed = false"
        if pattern:
            # Simple wildcard conversion
            if pattern == "*.gdoc":
                query += " and mimeType = 'application/vnd.google-apps.document'"
            elif pattern.startswith("*."):
                ext = pattern[1:]  # e.g. .docx or .findings.json
                query += f" and name contains '{ext}'"
            elif "*" not in pattern:
                query += f" and name = '{pattern}'"

        res = (
            self.service.files()
            .list(q=query, fields="files(id, name, mimeType)")
            .execute()
        )
        items = res.get("files", [])
        return [
            item["id"]
            for item in items
            if item.get("mimeType") != "application/vnd.google-apps.folder"
        ]


def get_storage_provider(config: Optional[SnipperConfig] = None) -> StorageProvider:
    """Factory creating the active StorageProvider based on SnipperConfig.storage_backend."""
    cfg = config or SnipperConfig()
    backend = cfg.storage_backend.lower().strip()

    if backend in ("gdrive", "gdoc"):
        try:
            import googleapiclient  # noqa: F401
            import gdrive_auth
        except ImportError as e:
            raise RuntimeError(
                "[!] Google Drive extension requires optional dependencies.\n"
                "[!] Install them with: pip install -r requirements-gdrive.txt"
            ) from e

        if not cfg.library_folder_id:
            raise ValueError(
                "[!] Google Drive backend requires 'library_folder_id' configured in config.py or CustomConstraints.md"
            )

        drive_service = gdrive_auth.get_drive_service()
        docs_service = gdrive_auth.get_docs_service() if backend == "gdoc" else None
        return GoogleDriveStorage(
            drive_service,
            cfg.library_folder_id,
            docs_service=docs_service,
            backend=backend,
        )

    return LocalStorageProvider()

