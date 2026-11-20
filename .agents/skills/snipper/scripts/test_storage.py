"""Unit tests for storage providers, factory, DrivePathResolver, and gdrive_auth."""

import io
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig
from storage import (
    DriveItem,
    DrivePathResolver,
    GoogleDriveStorage,
    LocalStorageProvider,
    get_storage_provider,
)


# --- 1. LocalStorageProvider Tests ---

def test_local_storage_provider_crud(tmp_path):
    provider = LocalStorageProvider()
    test_file = tmp_path / "hello.txt"

    # Write text
    written = provider.write_text(tmp_path, "hello.txt", "Hello World!")
    assert Path(written).exists()
    assert provider.exists(test_file)

    # Read text
    assert provider.read_text(test_file) == "Hello World!"

    # Read stream
    stream = provider.read_stream(test_file)
    assert stream.getvalue() == b"Hello World!"

    # Update stream
    new_stream = io.BytesIO(b"Updated Content")
    provider.update_stream(test_file, new_stream)
    assert provider.read_text(test_file) == "Updated Content"

    # List files
    files = provider.list_files(tmp_path, "*.txt")
    assert str(test_file.resolve()) in [str(Path(f).resolve()) for f in files]


# --- 2. Factory and Lazy Loading Tests ---

def test_get_storage_provider_default_local():
    cfg = SnipperConfig()
    provider = get_storage_provider(cfg)
    assert isinstance(provider, LocalStorageProvider)


def test_get_storage_provider_missing_dependencies_error():
    cfg = SnipperConfig(storage_backend="gdrive", library_folder_id="fake-id")
    # Simulate googleapiclient not being importable
    with patch.dict(sys.modules, {"googleapiclient": None}):
        with pytest.raises(RuntimeError) as exc_info:
            get_storage_provider(cfg)
        assert "requirements-gdrive.txt" in str(exc_info.value)


def test_get_storage_provider_missing_folder_id():
    cfg = SnipperConfig(storage_backend="gdrive", library_folder_id=None)
    with patch.dict(sys.modules, {"googleapiclient": MagicMock(), "gdrive_auth": MagicMock()}):
        with pytest.raises(ValueError) as exc_info:
            get_storage_provider(cfg)
        assert "library_folder_id" in str(exc_info.value)


# --- 3. DrivePathResolver Tests ---

def test_drive_path_resolver_success():
    mock_service = MagicMock()
    # Mock files().list().execute()
    # 1st call for "Module 1"
    # 2nd call for "entry.docx"
    mock_service.files().list().execute.side_effect = [
        {"files": [{"id": "mod1-id", "name": "Module 1", "mimeType": "application/vnd.google-apps.folder"}]},
        {"files": [{"id": "entry-id", "name": "entry.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}]},
    ]

    resolver = DrivePathResolver(mock_service, root_folder_id="root-123")
    item = resolver.resolve("Module 1/entry.docx")

    assert item.id == "entry-id"
    assert item.name == "entry.docx"
    assert item.parent_id == "mod1-id"
    assert item.is_folder is False


def test_drive_path_resolver_not_found():
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {"files": []}

    resolver = DrivePathResolver(mock_service, root_folder_id="root-123")
    with pytest.raises(FileNotFoundError) as exc_info:
        resolver.resolve("NonExistent/doc.docx")
    assert "NonExistent" in str(exc_info.value)


# --- 4. GoogleDriveStorage Stream I/O Tests ---

def test_gdrive_storage_in_memory_read_and_write():
    mock_service = MagicMock()
    # Mock media download
    mock_service.files().get_media().execute.return_value = b"Mocked File Content"

    # Mock resolver
    resolver = MagicMock()
    resolver.resolve.return_value = DriveItem(id="file-999", name="test.docx", parent_id="folder-111", is_folder=False)

    # Mock list (empty, so it creates new file)
    mock_service.files().list().execute.return_value = {"files": []}
    mock_service.files().create().execute.return_value = {"id": "new-file-123"}

    # Mock media upload helper module in sys.modules
    mock_http = MagicMock()
    with patch.dict(sys.modules, {"googleapiclient.http": mock_http}):
        storage = GoogleDriveStorage(mock_service, library_folder_id="root-123", resolver=resolver)

        # 1. Read stream
        stream = storage.read_stream("test.docx")
        assert stream.getvalue() == b"Mocked File Content"

        # 2. Read text
        text = storage.read_text("test.docx")
        assert text == "Mocked File Content"

        # 3. Write text
        created_id = storage.write_text("folder-111", "notes.txt", "Some notes")
        assert created_id == "new-file-123"

        # 4. Update stream
        update_stream = io.BytesIO(b"Updated Doc Bytes")
        storage.update_stream("test.docx", update_stream)
        mock_service.files().update.assert_called()


# --- 5. gdrive_auth Tests ---

def test_gdrive_auth_service_account(tmp_path):
    sa_file = tmp_path / "sa.json"
    sa_file.write_text('{"type": "service_account"}', encoding="utf-8")

    mock_google = MagicMock()
    mock_oauth2 = MagicMock()
    mock_sa = MagicMock()
    mock_discovery = MagicMock()
    mock_google.oauth2 = mock_oauth2
    mock_oauth2.service_account = mock_sa

    with patch.dict(sys.modules, {
        "google": mock_google,
        "google.oauth2": mock_oauth2,
        "google.oauth2.service_account": mock_sa,
        "googleapiclient": MagicMock(),
        "googleapiclient.discovery": mock_discovery,
    }):
        import gdrive_auth
        assert "https://www.googleapis.com/auth/documents" in gdrive_auth.SCOPES
        assert "https://www.googleapis.com/auth/drive" in gdrive_auth.SCOPES

        gdrive_auth.get_drive_service(service_account_path=sa_file)
        mock_sa.Credentials.from_service_account_file.assert_called_with(
            str(sa_file), scopes=gdrive_auth.SCOPES
        )
        mock_discovery.build.assert_called_with(
            "drive", "v3", credentials=mock_sa.Credentials.from_service_account_file.return_value
        )

        # Test docs service initialization
        gdrive_auth.get_docs_service(service_account_path=sa_file)
        mock_discovery.build.assert_called_with(
            "docs", "v1", credentials=mock_sa.Credentials.from_service_account_file.return_value
        )


# --- 6. Scope and Retrieval with GoogleDriveStorage Tests ---

def test_scope_resolver_with_gdrive_storage():
    from scope import ScopeResolver

    mock_service = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(id="mod1-folder-id", name="Module 1", is_folder=True)

    storage = GoogleDriveStorage(mock_service, library_folder_id="lib-root-id", resolver=mock_resolver)
    resolver = ScopeResolver(storage_provider=storage)

    # 1. Global scope
    res_global = resolver.resolve(target_path=None, scope="global")
    assert res_global.scope_type == "global"
    assert res_global.library_root == "lib-root-id"
    assert "lib-root-id" in res_global.scoped_directories

    # 2. Local scope
    res_local = resolver.resolve(target_path="Module 1", scope="local")
    assert res_local.scope_type == "local"
    assert "mod1-folder-id" in res_local.scoped_directories


def test_lookup_snippets_with_gdrive_storage():
    from retrieval import lookup_snippets

    mock_service = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(id="mod1-folder-id", name="Module 1", is_folder=True)

    storage = GoogleDriveStorage(mock_service, library_folder_id="lib-root-id", resolver=mock_resolver)

    # Mock list_files returning a findings file ID
    storage.list_files = MagicMock(return_value=["findings-file-id-123"])

    # Mock read_text for findings and companion txt
    findings_json = """
    {
      "findings": [
        {
          "question_numbers": [1],
          "target_ids": ["Q1"],
          "snippet_text": "OAuth 2.0 access token expires in one hour.",
          "keywords": ["OAuth", "token"]
        }
      ]
    }
    """
    storage.read_text = MagicMock(side_effect=lambda target: findings_json if "findings" in str(target) else "[P0] OAuth 2.0 access token expires in one hour.")
    storage._resolve_target = MagicMock(return_value=DriveItem(id="findings-file-id-123", name="auth.findings.json", is_folder=False))

    candidates, scope_res = lookup_snippets(
        query="OAuth token",
        target_path="Module 1",
        scope="local",
        limit=5,
        storage_provider=storage,
    )

    assert len(candidates) == 1
    assert candidates[0].target_id == "Q1"
    assert "OAuth 2.0 access token" in candidates[0].snippet_text
    assert candidates[0].score > 0


def test_gdoc_storage_read_and_export():
    mock_service = MagicMock()
    mock_service.files().export().execute.return_value = b"Plain text exported from native Google Doc."
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="gdoc-123",
        name="lesson",
        parent_id="folder-1",
        is_folder=False,
        mime_type="application/vnd.google-apps.document",
    )

    storage = GoogleDriveStorage(mock_service, library_folder_id="root-1", resolver=mock_resolver)
    
    # 1. read_stream on native .gdoc calls export(mimeType="text/plain")
    stream = storage.read_stream("Module 1/lesson.gdoc")
    assert stream.getvalue() == b"Plain text exported from native Google Doc."
    mock_service.files().export.assert_called_with(fileId="gdoc-123", mimeType="text/plain")

    # 2. list_files with *.gdoc
    storage.list_files("Module 1", "*.gdoc")
    call_args = mock_service.files().list.call_args[1]
    assert "mimeType = 'application/vnd.google-apps.document'" in call_args["q"]


def test_get_storage_provider_gdoc():
    cfg = SnipperConfig(storage_backend="gdoc", library_folder_id="lib-folder-999")
    mock_drive_service = MagicMock()
    mock_docs_service = MagicMock()

    with patch.dict(sys.modules, {"googleapiclient": MagicMock()}):
        with patch("gdrive_auth.get_drive_service", return_value=mock_drive_service), \
             patch("gdrive_auth.get_docs_service", return_value=mock_docs_service):
            provider = get_storage_provider(cfg)
            assert isinstance(provider, GoogleDriveStorage)
            assert provider.service == mock_drive_service
            assert provider.docs_service == mock_docs_service



