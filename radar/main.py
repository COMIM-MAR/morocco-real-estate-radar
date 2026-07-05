from __future__ import annotations

import json
from .config import load_config, DATA_DIR
from .scrapers import collect_all
from .scoring import score_opportunity
from .storage import is_new_and_mark, init_db
from .notifiers import notify


MAX_EMAIL_ITEMS = 5


def run() -> list[dict]:
    config = load_config()
    init_db()

    raw = collect_all(config)
    scored = [score_opportunity(op, config) for op in raw]
    scored_sorted = sorted(scored, key=lambda x: x.score, reverse=True)

    trigger = int(config["scoring"]["trigger_threshold"])

    alerts = []
    for op in scored_sorted:
        if op.score < trigger:
            continue

        # Do not send repeated products
        if is_new_and_mark(op.source, op.title, op.url):
            alerts.append(op)

        if len(alerts) >= MAX_EMAIL_ITEMS:
            break

    DATA_DIR.mkdir(exist_ok=True)
    latest = DATA_DIR / "latest_alerts.json"
    latest.write_text(
        json.dumps([a.to_dict() for a in alerts], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if alerts:
        notify(alerts)
    else:
        print("No new high-quality opportunities to notify")

    print(f"Collected={len(raw)} Scored={len(scored)} Alerts={len(alerts)}")
    return [a.to_dict() for a in alerts]


if __name__ == "__main__":
    run()
