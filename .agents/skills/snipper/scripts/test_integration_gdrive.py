"""End-to-end integration tests verifying local mode independence and Google Drive zero-disk-write operations."""

import io
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import docx
import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cli import main
from storage import GoogleDriveStorage, DriveItem


def _create_sample_docx_bytes() -> bytes:
    """Creates a sample docx in memory and returns its bytes."""
    doc = docx.Document()
    doc.add_paragraph("Questions")
    doc.add_paragraph("1. What encryption standard is used?")
    doc.add_paragraph("Body")
    doc.add_paragraph("All sensitive customer data is protected using AES-256 encryption.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- 1. Local Mode Independence Tests (Zero Google dependencies) ---

def test_local_mode_without_google_dependencies(tmp_path: Path, monkeypatch):
    """Verifies all local CLI subcommands work seamlessly when Google packages are not importable."""
    # Ensure google packages cannot be imported
    monkeypatch.setitem(sys.modules, "googleapiclient", None)
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "google.auth", None)

    doc_path = tmp_path / "local_test.docx"
    doc_path.write_bytes(_create_sample_docx_bytes())

    # 1. snip
    ret = main(["snip", str(doc_path)])
    assert ret == 0
    txt_path = tmp_path / "local_test.snipper.txt"
    assert txt_path.exists()
    assert "AES-256 encryption" in txt_path.read_text(encoding="utf-8")

    # 2. lookup
    f_path = tmp_path / "local_test.findings.json"
    f_path.write_text(
        """{
            "findings": [
                {
                    "target_ids": ["Q1"],
                    "snippet_text": "All sensitive customer data is protected using AES-256 encryption.",
                    "keywords": ["AES-256", "encryption"]
                }
            ],
            "unanswered_targets": []
        }""",
        encoding="utf-8",
    )
    ret = main(["lookup", "--q", "AES-256", "--dir", str(tmp_path)])
    assert ret == 0

    # 3. hlt
    ret = main(["hlt", str(doc_path)])
    assert ret == 0
    mutated = docx.Document(doc_path)
    paras = [p.text for p in mutated.paragraphs]
    assert any("=== SNIPPER SUMMARY START ===" in p for p in paras)


def test_gdrive_mode_missing_dependencies_emits_friendly_error(tmp_path: Path, monkeypatch, capsys):
    """Verifies that selecting gdrive backend without required libraries gives a clear error."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdrive
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    # Block googleapiclient import
    monkeypatch.setitem(sys.modules, "googleapiclient", None)

    ret = main(["snip", "Module 1/doc.docx", "--config", str(cfg_file)])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Google Drive extension requires optional dependencies" in captured.err
    assert "pip install -r requirements-gdrive.txt" in captured.err


# --- 2. Google Drive Mode: Zero Bytes Written to Local Disk ---

def test_gdrive_snip_zero_disk_writes(tmp_path: Path, monkeypatch):
    """Verifies snip subcommand reads and writes companion text in Drive with zero local disk writes."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdrive
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    doc_bytes = _create_sample_docx_bytes()

    mock_service = MagicMock()
    mock_service.files().get_media().execute.return_value = doc_bytes
    mock_service.files().create().execute.return_value = {"id": "companion-txt-id-999"}

    # Mock resolver
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="file-id-001", name="entry.docx", parent_id="folder-id-100", is_folder=False
    )

    storage = GoogleDriveStorage(mock_service, library_folder_id="root-lib-folder-123", resolver=mock_resolver)
    storage.exists = MagicMock(return_value=True)
    storage.read_stream = MagicMock(side_effect=lambda target: io.BytesIO(doc_bytes))
    storage.read_text = MagicMock(return_value="Q1: What encryption standard is used?\n")
    storage.write_text = MagicMock(return_value="companion-txt-id-999")

    # Sandbox folder to track file creations
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["snip", "Module 1/entry.docx", "--config", str(cfg_file)])
        assert ret == 0

    # Verify zero files created on local disk
    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    # Verify storage provider was used
    storage.read_stream.assert_called_with("Module 1/entry.docx")
    storage.write_text.assert_called()


def test_gdrive_hlt_zero_disk_writes(tmp_path: Path, monkeypatch):
    """Verifies hlt subcommand reads doc and findings, mutates in-memory, and updates Drive with zero local disk writes."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdrive
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    doc_bytes = _create_sample_docx_bytes()
    findings_json = """{
        "findings": [
            {
                "target_ids": ["Q1"],
                "snippet_text": "All sensitive customer data is protected using AES-256 encryption.",
                "keywords": ["AES-256", "encryption"]
            }
        ],
        "unanswered_targets": []
    }"""

    mock_service = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="file-id-001", name="entry.docx", parent_id="folder-id-100", is_folder=False
    )

    storage = GoogleDriveStorage(mock_service, library_folder_id="root-lib-folder-123", resolver=mock_resolver)
    storage.exists = MagicMock(return_value=True)
    storage.read_stream = MagicMock(return_value=io.BytesIO(doc_bytes))
    storage.read_text = MagicMock(return_value=findings_json)
    storage.write_text = MagicMock(return_value="companion-txt-id-999")
    storage.update_stream = MagicMock()

    sandbox_dir = tmp_path / "sandbox_hlt"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["hlt", "Module 1/entry.docx", "--config", str(cfg_file)])
        assert ret == 0

    # Verify zero files created on local disk
    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    # Verify update_stream was called with updated docx bytes
    storage.update_stream.assert_called()
    called_target, called_stream = storage.update_stream.call_args[0][:2]
    assert called_target == "Module 1/entry.docx"
    assert isinstance(called_stream, (io.BytesIO, io.BufferedIOBase))
    
    # Verify mutated stream has summary block
    mutated_doc = docx.Document(called_stream)
    paras = [p.text for p in mutated_doc.paragraphs]
    assert any("=== SNIPPER SUMMARY START ===" in p for p in paras)


def test_gdrive_lookup_zero_disk_writes(tmp_path: Path, monkeypatch, capsys):
    """Verifies lookup subcommand scans remote findings into memory with zero local disk writes."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdrive
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    findings_json = """{
        "findings": [
            {
                "target_ids": ["Q1"],
                "snippet_text": "All sensitive customer data is protected using AES-256 encryption.",
                "keywords": ["AES-256", "encryption"]
            }
        ],
        "unanswered_targets": []
    }"""

    mock_service = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="mod1-folder-id", name="Module 1", is_folder=True
    )

    storage = GoogleDriveStorage(mock_service, library_folder_id="root-lib-folder-123", resolver=mock_resolver)
    storage.list_files = MagicMock(return_value=["findings-file-id-123"])
    storage.read_text = MagicMock(side_effect=lambda target: findings_json if "findings" in str(target) else "[P0] Sensitive data...")
    storage._resolve_target = MagicMock(return_value=DriveItem(id="findings-file-id-123", name="entry.findings.json", is_folder=False))

    sandbox_dir = tmp_path / "sandbox_lookup"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["lookup", "--q", "encryption", "--dir", "Module 1", "--config", str(cfg_file)])
        assert ret == 0

    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    captured = capsys.readouterr()
    assert "[Found 1 relevant snippets" in captured.out
    assert "AES-256 encryption" in captured.out


# --- 3. Google Docs Mode: Zero .txt and Zero .docx Files Created or Required ---

def test_gdoc_snip_zero_txt_and_zero_docx(tmp_path: Path, monkeypatch):
    """Verifies that in gdoc mode, snip ingests a native Google Doc and companion questions in RAM with zero .txt or .docx files written."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdoc
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    gdoc_text = "Data at rest must be encrypted using AES-256.\nNetwork perimeter enforces TLS 1.3.\n"
    q_text = "Q1: What is the encryption requirement?\n  - Keywords: AES-256, encrypted\n"

    mock_service = MagicMock()
    mock_docs_service = MagicMock()

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="gdoc-file-id-100",
        name="Lesson",
        parent_id="folder-id-100",
        is_folder=False,
        mime_type="application/vnd.google-apps.document",
    )

    storage = GoogleDriveStorage(
        mock_service,
        library_folder_id="root-lib-folder-123",
        resolver=mock_resolver,
        docs_service=mock_docs_service,
        backend="gdoc",
    )
    storage.exists = MagicMock(return_value=True)
    storage.read_stream = MagicMock(side_effect=lambda target: io.BytesIO(gdoc_text.encode("utf-8")))
    storage.read_text = MagicMock(return_value=q_text)
    storage.write_text = MagicMock()

    sandbox_dir = tmp_path / "sandbox_gdoc_snip"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["snip", "Module1/Lesson.gdoc", "--config", str(cfg_file)])
        assert ret == 0

    # Verify zero files on local disk
    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    # Verify storage.write_text was NEVER called (no .txt uploaded to Drive)
    storage.write_text.assert_not_called()


def test_gdoc_hlt_zero_txt_and_zero_docx(tmp_path: Path, monkeypatch):
    """Verifies that in gdoc mode, hlt mutates Google Docs via Docs API batchUpdate without .docx binary update or .txt companion."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdoc
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    gdoc_text = "Data at rest must be encrypted using AES-256.\n"
    q_text = "Q1: What is the encryption requirement?\n"
    findings_json = """{
        "findings": [
            {
                "target_ids": ["Q1"],
                "snippet_text": "Data at rest must be encrypted using AES-256.",
                "keywords": ["AES-256", "encrypted"]
            }
        ],
        "unanswered_targets": []
    }"""

    mock_service = MagicMock()
    mock_docs_service = MagicMock()
    mock_docs = MagicMock()
    mock_docs_service.documents.return_value = mock_docs

    mock_docs.get.return_value.execute.return_value = {
        "body": {
            "content": [
                {"endIndex": 1},
                {
                    "startIndex": 1,
                    "endIndex": 47,
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Data at rest must be encrypted using AES-256.\n"}}
                        ]
                    },
                },
            ]
        }
    }
    mock_docs.batchUpdate.return_value.execute.return_value = {
        "documentId": "gdoc-file-id-100",
        "replies": [],
    }

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="gdoc-file-id-100",
        name="Lesson",
        parent_id="folder-id-100",
        is_folder=False,
        mime_type="application/vnd.google-apps.document",
    )

    storage = GoogleDriveStorage(
        mock_service,
        library_folder_id="root-lib-folder-123",
        resolver=mock_resolver,
        docs_service=mock_docs_service,
        backend="gdoc",
    )
    storage.exists = MagicMock(return_value=True)
    storage.read_stream = MagicMock(return_value=io.BytesIO(gdoc_text.encode("utf-8")))
    storage.read_text = MagicMock(side_effect=lambda target: findings_json if "findings" in str(target) else q_text)
    storage.write_text = MagicMock()
    storage.update_stream = MagicMock()

    sandbox_dir = tmp_path / "sandbox_gdoc_hlt"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["hlt", "Module1/Lesson.gdoc", "--config", str(cfg_file)])
        assert ret == 0

    # Verify zero files created locally
    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    # Verify storage.update_stream was NOT called (no binary .docx upload)
    storage.update_stream.assert_not_called()

    # Verify Docs API batchUpdate was called with styling & summary block
    mock_docs.batchUpdate.assert_called_once()
    call_kwargs = mock_docs.batchUpdate.call_args[1]
    assert call_kwargs["documentId"] == "gdoc-file-id-100"
    requests = call_kwargs["body"]["requests"]
    assert any("insertText" in r for r in requests)
    assert any("updateTextStyle" in r for r in requests)


def test_gdoc_lookup_with_module_metadata(tmp_path: Path, monkeypatch, capsys):
    """Verifies that lookup works seamlessly under gdoc mode, inheriting module.metadata without disk writes."""
    cfg_file = tmp_path / "CustomConstraints.md"
    cfg_file.write_text(
        """
```yaml
storage:
  backend: gdoc
  library_folder_id: root-lib-folder-123
```
""",
        encoding="utf-8",
    )

    findings_json = """{
        "findings": [
            {
                "target_ids": ["Q1"],
                "snippet_text": "Customer PII is encrypted with AES-256.",
                "keywords": ["encrypted", "PII"]
            }
        ],
        "unanswered_targets": []
    }"""
    metadata_text = """# Keywords\nSecurity, Compliance\n\n# Concepts\nPII Protection: Safeguarding personal information (Source: https://example.com/pii)\n"""

    mock_service = MagicMock()
    mock_docs_service = MagicMock()
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = DriveItem(
        id="mod1-folder-id", name="Module1", is_folder=True
    )

    storage = GoogleDriveStorage(
        mock_service,
        library_folder_id="root-lib-folder-123",
        resolver=mock_resolver,
        docs_service=mock_docs_service,
        backend="gdoc",
    )
    storage.list_files = MagicMock(return_value=["findings-id-456"])
    storage.exists = MagicMock(side_effect=lambda path: "metadata" in str(path) or "findings" in str(path))
    storage.read_text = MagicMock(side_effect=lambda path: metadata_text if "metadata" in str(path) else findings_json)
    storage._resolve_target = MagicMock(return_value=DriveItem(id="findings-id-456", name="Lesson.findings.json", is_folder=False))

    sandbox_dir = tmp_path / "sandbox_gdoc_lookup"
    sandbox_dir.mkdir()
    monkeypatch.chdir(sandbox_dir)

    with patch("cli.get_storage_provider", return_value=storage):
        ret = main(["lookup", "--q", "encrypted", "--dir", "Module1", "--config", str(cfg_file)])
        assert ret == 0

    local_files = list(sandbox_dir.rglob("*"))
    assert len(local_files) == 0, f"Expected 0 local files, found: {local_files}"

    captured = capsys.readouterr()
    assert "[Found 1 relevant snippets" in captured.out
    assert "Customer PII is encrypted with AES-256." in captured.out
