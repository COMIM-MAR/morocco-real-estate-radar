import json

from .alerts import attach_changes, select_digest_projects, select_immediate_alerts
from .config import DATA_DIR, load_config
from .dashboard import build
from .database import existing_project_ids, init_db, load_project_map, load_projects, upsert_projects
from .entity_resolution import resolve_projects
from .notifier import notify_digest, notify_immediate


def run():
    from collectors import collect_all

    config = load_config()
    DATA_DIR.mkdir(exist_ok=True)
    init_db()
    known_project_ids = existing_project_ids()
    previous_project_map = load_project_map()
    signals = collect_all(config)
    projects = resolve_projects(signals, config)
    projects = attach_changes(projects, previous_project_map)
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
    alerts = select_immediate_alerts(projects, known_project_ids, config)
    digest_projects = select_digest_projects(projects, known_project_ids, config)
    if alerts:
        notify_immediate(alerts)
    elif config["alerts"].get("digest_when_no_alerts", True) and digest_projects:
        notify_digest(digest_projects)
    else:
        print("No immediate or digest-worthy project to email")
    (DATA_DIR / "latest_alerts.json").write_text(
        json.dumps(
            {
                "immediate": [project.to_dict() for project in alerts],
                "digest": [project.to_dict() for project in digest_projects],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Collected={len(signals)} Projects={len(projects)} Immediate={len(alerts)} Digest={len(digest_projects)}")
