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


if __name__ == "__main__":
    test_default_config()
    test_aliases()
    test_load_from_custom_constraints()
    print("Config tests passed!")
