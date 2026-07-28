import json

from .alerts import attach_changes, select_digest_projects, select_immediate_alerts
from .config import DATA_DIR, load_config
from .dashboard import build
from .database import existing_project_ids, init_db, load_project_map, load_projects, upsert_projects
from .entity_resolution import resolve_projects
from .health import detect_degraded_collectors, load_health_history, save_health_history, update_health_history
from .media_assets import attach_meta_media_assets
from .notifier import notify_digest, notify_immediate
from .promoter_discovery import discover_candidates, load_pending_candidates, upsert_candidates
from .qualifications import attach_qualifications, fetch_qualifications


def run():
    from collectors import collect_all

    config = load_config()
    DATA_DIR.mkdir(exist_ok=True)
    init_db()
    known_project_ids = existing_project_ids()
    previous_project_map = load_project_map()
    signals, collector_stats = collect_all(config)
    health_history = load_health_history()
    health_config = config.get("health", {})
    degraded_collectors = detect_degraded_collectors(
        health_history,
        collector_stats,
        min_historical_avg=health_config.get("min_historical_avg", 3.0),
    )
    for degraded in degraded_collectors:
        print(
            "::warning::collector '{collector}' produced 0 real signals today "
            "(historical average {historical_avg})".format(**degraded)
        )
    health_history = update_health_history(health_history, collector_stats)
    save_health_history(health_history)
    candidate_promoters = discover_candidates(signals, config)
    upsert_candidates(candidate_promoters)
    pending_candidates = load_pending_candidates(min_confidence=40)
    if pending_candidates:
        print(
            f"::notice::{len(pending_candidates)} promoteur(s) candidat(s) en attente de revue "
            "(voir data/candidate_promoters.json, approuver via data/approved_promoters.json)"
        )
    (DATA_DIR / "candidate_promoters.json").write_text(
        json.dumps(pending_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    projects = resolve_projects(signals, config)
    projects = attach_changes(projects, previous_project_map)
    projects = attach_meta_media_assets(projects)
    qualifications = fetch_qualifications()
    projects = attach_qualifications(projects, qualifications)
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
    alerts = select_immediate_alerts(projects, known_project_ids, config, qualifications)
    digest_projects = select_digest_projects(projects, known_project_ids, config, qualifications)
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
    print(
        f"Collected={len(signals)} Projects={len(projects)} Immediate={len(alerts)} "
        f"Digest={len(digest_projects)} DegradedCollectors={len(degraded_collectors)} "
        f"PendingPromoterCandidates={len(pending_candidates)}"
    )
