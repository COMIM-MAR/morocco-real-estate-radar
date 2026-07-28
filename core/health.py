from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import DATA_DIR

HEALTH_STATE_PATH = DATA_DIR / "collector_health.json"
WATCH_SIGNAL_TYPES = {"meta_watch", "search_watch", "news_watch", "social_watch", "urbanism_watch"}
DEFAULT_WINDOW = 14
DEFAULT_MIN_HISTORICAL_AVG = 3.0


def load_health_history() -> dict:
    if not HEALTH_STATE_PATH.exists():
        return {"collectors": {}}
    try:
        return json.loads(HEALTH_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"collectors": {}}


def save_health_history(history: dict) -> None:
    HEALTH_STATE_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def historical_average(history: dict, name: str) -> float:
    entries = history.get("collectors", {}).get(name, [])
    if not entries:
        return 0.0
    return sum(entry["real_primary"] for entry in entries) / len(entries)


def detect_degraded_collectors(
    history: dict,
    stats: dict,
    min_historical_avg: float = DEFAULT_MIN_HISTORICAL_AVG,
) -> list[dict]:
    degraded = []
    for name, today_stats in stats.items():
        avg = historical_average(history, name)
        if avg >= min_historical_avg and today_stats.get("real_primary", 0) == 0:
            degraded.append(
                {
                    "collector": name,
                    "historical_avg": round(avg, 2),
                    "today_real_primary": today_stats.get("real_primary", 0),
                    "today_error": today_stats.get("error"),
                }
            )
    return degraded


def update_health_history(history: dict, stats: dict, window: int = DEFAULT_WINDOW) -> dict:
    collectors = history.setdefault("collectors", {})
    today = datetime.now(timezone.utc).date().isoformat()
    for name, today_stats in stats.items():
        entries = collectors.setdefault(name, [])
        entries.append(
            {
                "date": today,
                "total": today_stats.get("total", 0),
                "real_primary": today_stats.get("real_primary", 0),
                "error": today_stats.get("error"),
            }
        )
        collectors[name] = entries[-window:]
    return history
