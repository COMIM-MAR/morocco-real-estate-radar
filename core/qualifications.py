from __future__ import annotations

import os

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
QUALIFICATIONS_TABLE = "project_qualifications"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("SUPABASE_REQUEST_TIMEOUT_SECONDS", "8"))

SUPPRESSED_ALERT_STATUSES = {"archived"}


def supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def fetch_qualifications() -> dict[str, dict]:
    if not supabase_configured():
        return {}
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{QUALIFICATIONS_TABLE}"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    params = {"select": "project_id,status,notes,updated_at"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        rows = response.json()
    except Exception as error:
        print(f"WARN supabase qualification fetch failed: {error}")
        return {}
    return {row["project_id"]: row for row in rows if row.get("project_id")}


def attach_qualifications(projects, qualifications: dict[str, dict]):
    for project in projects:
        record = qualifications.get(project.project_id)
        project.evidence["qualification"] = {
            "status": record.get("status", "new") if record else "new",
            "notes": record.get("notes", "") if record else "",
        }
    return projects


def is_alert_suppressed(project_id: str, qualifications: dict[str, dict]) -> bool:
    record = qualifications.get(project_id)
    if not record:
        return False
    return record.get("status") in SUPPRESSED_ALERT_STATUSES
