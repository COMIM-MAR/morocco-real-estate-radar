import json, hashlib
from pathlib import Path
from .config import DATA_DIR
SEEN = DATA_DIR / "seen_urls.json"
def _load():
    if not SEEN.exists(): return set()
    try: return set(json.loads(SEEN.read_text(encoding="utf-8")))
    except Exception: return set()
def _save(s):
    DATA_DIR.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(sorted(s), ensure_ascii=False, indent=2), encoding="utf-8")
def fingerprint(channel, url):
    return hashlib.sha1(f"{channel}|{url}".encode()).hexdigest()
def is_new(channel, url):
    seen=_load(); fp=fingerprint(channel,url)
    if fp in seen: return False
    seen.add(fp); _save(seen); return True
