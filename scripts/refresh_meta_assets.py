from __future__ import annotations

import json
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import load_config
from core.dashboard import build
from core.database import init_db, load_project_map, upsert_projects
from core.entity_resolution import resolve_projects
from core.media_assets import attach_meta_media_assets, project_meta_candidates
from core.models import SignalEvent
from core.alerts import attach_changes


def main() -> None:
    config = load_config()
    init_db()
    previous_project_map = load_project_map()
    raw_signals = json.loads((ROOT / "data" / "all_signals.json").read_text(encoding="utf-8"))
    signals: list[SignalEvent] = []
    for item in raw_signals:
        payload = dict(item)
        payload.pop("signal_id", None)
        signals.append(SignalEvent(**payload))
    projects = resolve_projects(signals, config)
    projects = attach_changes(projects, previous_project_map)
    only_project = os.getenv("META_MEDIA_ONLY_PROJECT", "").strip().lower()
    if only_project:
        projects = [
            project
            for project in projects
            if only_project in project.project_id.lower()
            or only_project in project.name.lower()
            or only_project in (project.evidence.get("project_slug", "").lower())
        ]
    projects_with_meta = sum(1 for project in projects if project_meta_candidates(project))
    print(f"Preparing Meta media refresh for {len(projects)} project(s), including {projects_with_meta} with Meta ads.")
    projects = attach_meta_media_assets(projects)
    upsert_projects(projects)
    payload = [project.to_dict() for project in projects]
    (ROOT / "data" / "projects.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "data" / "knowledge_base.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    build(projects[:100])
    with_assets = sum(1 for project in projects if (project.evidence.get("images") or project.evidence.get("videos")))
    print(f"Refreshed meta assets for {len(projects)} projects; {with_assets} project(s) now have media.")


if __name__ == "__main__":
    main()
