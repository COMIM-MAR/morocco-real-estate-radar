from __future__ import annotations
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "profile.yml"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
