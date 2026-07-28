import json
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
DATABASE_PATH = DATA_DIR / "intelligence.db"
CONFIG_PATH = ROOT / "config" / "profile.yml"
APPROVED_PROMOTERS_PATH = DATA_DIR / "approved_promoters.json"


def load_approved_promoters() -> list[dict]:
    if not APPROVED_PROMOTERS_PATH.exists():
        return []
    try:
        return json.loads(APPROVED_PROMOTERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def merge_approved_promoters(config: dict) -> dict:
    approved = load_approved_promoters()
    if not approved:
        return config
    tracked = config.setdefault("promoters", {}).setdefault("tracked", [])
    promoter_sources = config.setdefault("sources", {}).setdefault("promoters", [])
    existing_names = {name.lower() for name in tracked}
    existing_urls = {entry.get("url") for entry in promoter_sources if isinstance(entry, dict)}
    for entry in approved:
        name = entry.get("name")
        if not name:
            continue
        if name.lower() not in existing_names:
            tracked.append(name)
            existing_names.add(name.lower())
        url = entry.get("url")
        if url and url not in existing_urls:
            promoter_sources.append({"name": name, "url": url})
            existing_urls.add(url)
    return config


def load_config() -> dict:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return merge_approved_promoters(config)
