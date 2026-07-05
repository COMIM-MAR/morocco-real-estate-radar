import json

from collectors import collect_all
from .config import DATA_DIR, load_config
from .dashboard import build
from .database import existing_project_ids, init_db, load_projects, upsert_projects
from .entity_resolution import resolve_projects
from .notifier import notify


def run():
    config = load_config()
    DATA_DIR.mkdir(exist_ok=True)
    init_db()
    known_project_ids = existing_project_ids()
    signals = collect_all(config)
    projects = resolve_projects(signals, config)
    upsert_projects(projects)
    persisted_projects = load_projects()
    (DATA_DIR / "all_signals.json").write_text(
        json.dumps([signal.to_dict() for signal in signals], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DATA_DIR / "projects.json").write_text(
        json.dumps([project.to_dict() for project in projects], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DATA_DIR / "knowledge_base.json").write_text(
        json.dumps([project.to_dict() for project in persisted_projects], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    build(persisted_projects[:100])
    alerts = []
    for project in projects:
        if project.project_id in known_project_ids:
            continue
        if project.confidence_score < config["alerts"]["immediate_confidence_threshold"]:
            continue
        if not any(signal.is_primary for signal in project.signals):
            continue
        alerts.append(project)
        if len(alerts) >= config["alerts"]["max_items_per_email"]:
            break
    if alerts:
        notify(alerts)
    else:
        print("No new high-confidence project to email")
    (DATA_DIR / "latest_alerts.json").write_text(
        json.dumps([project.to_dict() for project in alerts], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Collected={len(signals)} Projects={len(projects)} Alerts={len(alerts)}")
