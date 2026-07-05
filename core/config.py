from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
DATABASE_PATH = DATA_DIR / "intelligence.db"
CONFIG_PATH = ROOT / "config" / "profile.yml"
def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
