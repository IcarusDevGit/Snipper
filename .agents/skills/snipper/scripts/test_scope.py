import sys
from pathlib import Path
import tempfile

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from scope import ScopeResolver, ScopeResult


def build_test_library(root: Path):
    """Sets up a test Library hierarchy:
    root/
      library.keywords.txt (GDPR, Compliance)
      library.concepts.txt (Security Baseline: Standard security (Source: https://example.com/sec))
      ModuleA/
        module.keywords.txt (Authentication, IAM)
        SubModule1/
          access.docx
          access.txt
          access.questions.txt
          access.findings.json
        SubModule2/
          network.docx
          network.txt
          network.findings.json
      ModuleB/
        module.keywords.txt (Billing)
        SubModule3/
          invoice.docx
          invoice.txt
          invoice.findings.json
    """
    (root / "library.keywords.txt").write_text("GDPR, Compliance\n", encoding="utf-8")
    (root / "library.concepts.txt").write_text(
        "Security Baseline - Standard security baseline (Source: https://example.com/sec)\n",
        encoding="utf-8",
    )

    mod_a = root / "ModuleA"
    mod_a.mkdir(parents=True)
    (mod_a / "module.keywords.txt").write_text("Authentication, IAM\n", encoding="utf-8")

    sub1 = mod_a / "SubModule1"
    sub1.mkdir(parents=True)
    (sub1 / "access.docx").write_text("dummy docx", encoding="utf-8")
    (sub1 / "access.txt").write_text("[P0] Access control text\n", encoding="utf-8")
    (sub1 / "access.questions.txt").write_text("Q1: Who has access?\n", encoding="utf-8")
    (sub1 / "access.findings.json").write_text('{"findings": []}', encoding="utf-8")

    sub2 = mod_a / "SubModule2"
    sub2.mkdir(parents=True)
    (sub2 / "network.docx").write_text("dummy docx", encoding="utf-8")
    (sub2 / "network.txt").write_text("[P0] Network text\n", encoding="utf-8")
    (sub2 / "network.findings.json").write_text('{"findings": []}', encoding="utf-8")

    mod_b = root / "ModuleB"
    mod_b.mkdir(parents=True)
    (mod_b / "module.keywords.txt").write_text("Billing\n", encoding="utf-8")

    sub3 = mod_b / "SubModule3"
    sub3.mkdir(parents=True)
    (sub3 / "invoice.docx").write_text("dummy docx", encoding="utf-8")
    (sub3 / "invoice.txt").write_text("[P0] Invoice text\n", encoding="utf-8")
    (sub3 / "invoice.findings.json").write_text('{"findings": []}', encoding="utf-8")


def test_scope_local_submodule(tmp_path: Path):
    build_test_library(tmp_path)
    resolver = ScopeResolver(default_library_root=tmp_path)

    target_file = tmp_path / "ModuleA" / "SubModule1" / "access.docx"
    res = resolver.resolve(target_file, scope="local")

    assert res.scope_type == "local"
    assert res.is_in_scope(target_file)
    assert res.is_in_scope(tmp_path / "ModuleA" / "SubModule1" / "access.txt")
    # Sibling sub-module is out of scope
    assert not res.is_in_scope(tmp_path / "ModuleA" / "SubModule2" / "network.docx")
    assert not res.is_in_scope(tmp_path / "ModuleB" / "SubModule3" / "invoice.docx")
    # Local scope does not inherit ancestors
    assert res.inherited_keywords == []
    assert res.inherited_concepts == []

    findings = res.get_scoped_findings_files()
    assert len(findings) == 1
    assert findings[0].name == "access.findings.json"


def test_scope_local_module(tmp_path: Path):
    build_test_library(tmp_path)
    resolver = ScopeResolver(default_library_root=tmp_path)

    target_mod = tmp_path / "ModuleA"
    res = resolver.resolve(target_mod, scope="local")

    assert res.scope_type == "local"
    # All sub-modules in ModuleA are in scope
    assert res.is_in_scope(tmp_path / "ModuleA" / "SubModule1" / "access.docx")
    assert res.is_in_scope(tmp_path / "ModuleA" / "SubModule2" / "network.docx")
    # ModuleB is out of scope
    assert not res.is_in_scope(tmp_path / "ModuleB" / "SubModule3" / "invoice.docx")

    findings = res.get_scoped_findings_files()
    assert len(findings) == 2
    f_names = [f.name for f in findings]
    assert "access.findings.json" in f_names
    assert "network.findings.json" in f_names


def test_scope_hierarchical_inheritance(tmp_path: Path):
    build_test_library(tmp_path)
    resolver = ScopeResolver(default_library_root=tmp_path)

    target_sub1 = tmp_path / "ModuleA" / "SubModule1"
    res = resolver.resolve(target_sub1, scope="hierarchical")

    assert res.scope_type == "hierarchical"
    # Inherits from root and ModuleA
    assert "GDPR" in res.inherited_keywords
    assert "Compliance" in res.inherited_keywords
    assert "Authentication" in res.inherited_keywords
    assert "IAM" in res.inherited_keywords
    # Does NOT inherit from sibling ModuleB
    assert "Billing" not in res.inherited_keywords

    assert len(res.inherited_concepts) == 1
    assert res.inherited_concepts[0].name == "Security Baseline"
    assert "https://example.com/sec" in res.inherited_concepts[0].source_url


def test_scope_global(tmp_path: Path):
    build_test_library(tmp_path)
    resolver = ScopeResolver(default_library_root=tmp_path)

    res = resolver.resolve(scope="global", library_root=tmp_path)
    assert res.scope_type == "global"
    assert res.is_in_scope(tmp_path / "ModuleA" / "SubModule1" / "access.docx")
    assert res.is_in_scope(tmp_path / "ModuleB" / "SubModule3" / "invoice.docx")

    findings = res.get_scoped_findings_files()
    assert len(findings) == 3


def test_scope_hierarchical_module_metadata_local(tmp_path: Path):
    """Verifies that module.metadata with combined keywords and concepts is inherited in hierarchical scope."""
    root = tmp_path / "lib"
    root.mkdir(parents=True)
    mod = root / "SecurityModule"
    mod.mkdir(parents=True)
    sub = mod / "IAM"
    sub.mkdir(parents=True)
    (sub / "doc.docx").write_text("content", encoding="utf-8")

    # Combined metadata document
    (mod / "module.metadata").write_text(
        "# Keywords\n"
        "ZeroTrust, RBAC, OAuth2\n\n"
        "# Concepts\n"
        "Least Privilege - Strict minimal access granted (Source: https://example.com/least-privilege)\n",
        encoding="utf-8",
    )

    resolver = ScopeResolver(default_library_root=root)
    res = resolver.resolve(sub / "doc.docx", scope="hierarchical")

    assert res.scope_type == "hierarchical"
    assert "ZeroTrust" in res.inherited_keywords
    assert "RBAC" in res.inherited_keywords
    assert "OAuth2" in res.inherited_keywords
    assert len(res.inherited_concepts) == 1
    assert res.inherited_concepts[0].name == "Least Privilege"
    assert "https://example.com/least-privilege" in res.inherited_concepts[0].source_url


def test_scope_hierarchical_module_metadata_remote():
    """Verifies that module.metadata is discovered and parsed in memory over remote storage provider."""
    from unittest.mock import MagicMock
    from storage import DriveItem

    mock_storage = MagicMock()
    mock_storage.library_folder_id = "lib-root-id"

    item = DriveItem(id="file-123", name="doc.gdoc", parent_id="sub-folder-id", is_folder=False)
    mock_storage._resolve_target.return_value = item

    def fake_exists(path):
        return str(path) in ("ModuleCloud/module.metadata", "ModuleCloud/module.metadata.gdoc")

    mock_storage.exists.side_effect = fake_exists
    mock_storage.read_text.return_value = (
        "## Keywords\n"
        "CloudSecurity, KMS\n\n"
        "## Concepts\n"
        "Envelope Encryption: Encrypting data key with master key (Source: https://cloud.google.com/kms)\n"
    )

    resolver = ScopeResolver(storage_provider=mock_storage)
    res = resolver.resolve("ModuleCloud/SubFolder/doc.gdoc", scope="hierarchical")

    assert res.scope_type == "hierarchical"
    assert "CloudSecurity" in res.inherited_keywords
    assert "KMS" in res.inherited_keywords
    assert len(res.inherited_concepts) == 1
    assert res.inherited_concepts[0].name == "Envelope Encryption"
    assert "https://cloud.google.com/kms" in res.inherited_concepts[0].source_url


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        test_scope_local_submodule(tpath)
        test_scope_local_module(tpath)
        test_scope_hierarchical_inheritance(tpath)
        test_scope_global(tpath)
    print("Scope tests passed!")
