from __future__ import annotations
import json
from .config import load_config, DATA_DIR
from .collectors import collect_all
from .scoring import score_signal
from .storage import init_db, is_new_and_mark
from .notifiers import notify
from .dashboard import render_dashboard


def run() -> list[dict]:
    config = load_config()
    init_db()
    raw = collect_all(config)
    scored = [score_signal(s, config) for s in raw]
    qualified = [s for s in scored if s.status in ("urgent", "digest")]
    qualified_sorted = sorted(qualified, key=lambda x: x.total_score, reverse=True)

    alerts = []
    max_items = int(config["alerts"].get("max_items_per_email", 5))
    for sig in qualified_sorted:
        if is_new_and_mark(sig.channel, sig.url, sig.title):
            alerts.append(sig)
        if len(alerts) >= max_items:
            break

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "latest_alerts.json").write_text(json.dumps([s.to_dict() for s in alerts], ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "latest_signals.json").write_text(json.dumps([s.to_dict() for s in qualified_sorted[:200]], ensure_ascii=False, indent=2), encoding="utf-8")

    render_dashboard(qualified_sorted)

    if alerts:
        notify(alerts)
    else:
        print("No new qualified opportunities to notify")

    print(f"Collected={len(raw)} Qualified={len(qualified_sorted)} Alerts={len(alerts)}")
    return [s.to_dict() for s in alerts]


if __name__ == "__main__":
    run()
