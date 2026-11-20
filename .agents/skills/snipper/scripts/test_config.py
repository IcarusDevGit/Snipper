import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config import SnipperConfig, HighlighterConfig, HighliterConfig


def test_default_config():
    cfg = SnipperConfig()
    assert cfg.language == "auto"
    assert cfg.allow_web_search is False
    assert cfg.proper_nouns_only is False
    assert cfg.palette_mode == "hex"
    assert cfg.palette_order == "sequential"
    assert len(cfg.palette) == 15
    assert "#ea7286" in cfg.palette


def test_aliases():
    assert HighlighterConfig is SnipperConfig
    assert HighliterConfig is SnipperConfig


def test_load_from_custom_constraints():
    constraints_path = Path(".agents/skills/snipper/references/CustomConstraints.md")
    if not constraints_path.exists():
        constraints_path = _SCRIPT_DIR.parent / "references" / "CustomConstraints.md"
    if not constraints_path.exists():
        constraints_path = Path(".agents/skills/snipper/CustomConstraints.md")
    cfg = SnipperConfig.from_file(constraints_path)
    assert cfg.language == "auto"
    assert cfg.allow_web_search is False
    assert cfg.proper_nouns_only is False
    assert cfg.palette_mode == "hex"
    assert "#ea7286" in cfg.palette
    assert len(cfg.palette) == 15


def test_storage_config_defaults():
    cfg = SnipperConfig()
    assert cfg.storage_backend == "local"
    assert cfg.library_folder_id is None


def test_storage_config_from_yaml(tmp_path):
    # Test flat format
    yaml_file = tmp_path / "CustomConstraints.md"
    yaml_file.write_text("""
```yaml
configuration:
  storage_backend: gdrive
  library_folder_id: "test-folder-123"
```
""", encoding="utf-8")
    cfg = SnipperConfig.from_file(yaml_file)
    assert cfg.storage_backend == "gdrive"
    assert cfg.library_folder_id == "test-folder-123"

    # Test nested storage format
    yaml_file.write_text("""
```yaml
configuration:
  storage:
    backend: gdrive
    library_folder_id: "nested-folder-456"
```
""", encoding="utf-8")
    cfg_nested = SnipperConfig.from_file(yaml_file)
    assert cfg_nested.storage_backend == "gdrive"
    assert cfg_nested.library_folder_id == "nested-folder-456"

    # Test gdoc storage format
    yaml_file.write_text("""
```yaml
configuration:
  storage:
    backend: gdoc
    library_folder_id: "gdoc-folder-789"
    metadata_filename: "custom.metadata"
```
""", encoding="utf-8")
    cfg_gdoc = SnipperConfig.from_file(yaml_file)
    assert cfg_gdoc.storage_backend == "gdoc"
    assert cfg_gdoc.library_folder_id == "gdoc-folder-789"
    assert cfg_gdoc.metadata_filename == "custom.metadata"


if __name__ == "__main__":
    test_default_config()
    test_aliases()
    test_load_from_custom_constraints()
    test_storage_config_defaults()
    print("Config tests passed!")

