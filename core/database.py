from __future__ import annotations

import json
import sqlite3

from core.config import DATABASE_PATH
from core.models import ProjectRecord, SignalEvent


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                zone TEXT,
                promoter TEXT,
                asset_type TEXT,
                first_detected_at TEXT NOT NULL,
                last_updated_at TEXT NOT NULL,
                launch_score INTEGER NOT NULL,
                confidence_score INTEGER NOT NULL,
                investment_score INTEGER NOT NULL,
                urgency_score INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_count INTEGER NOT NULL,
                signal_count INTEGER NOT NULL,
                prices_json TEXT NOT NULL,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                channels_json TEXT NOT NULL DEFAULT '[]',
                sources_json TEXT NOT NULL,
                source_urls_json TEXT NOT NULL DEFAULT '[]',
                evidence_json TEXT NOT NULL DEFAULT '{}',
                reasons_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                collector TEXT NOT NULL,
                channel TEXT NOT NULL,
                source TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                text TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                is_primary INTEGER NOT NULL,
                launch_weight INTEGER NOT NULL,
                confidence_weight INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS project_updates (
                update_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                launch_score INTEGER NOT NULL,
                confidence_score INTEGER NOT NULL,
                investment_score INTEGER NOT NULL,
                urgency_score INTEGER NOT NULL,
                source_count INTEGER NOT NULL,
                signal_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );
            """
        )
        ensure_column(connection, "projects", "aliases_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(connection, "projects", "channels_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(connection, "projects", "source_urls_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(connection, "projects", "evidence_json", "TEXT NOT NULL DEFAULT '{}'")


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def existing_project_ids() -> set[str]:
    with connect() as connection:
        rows = connection.execute("SELECT project_id FROM projects").fetchall()
    return {row["project_id"] for row in rows}


def upsert_projects(projects: list[ProjectRecord]) -> None:
    with connect() as connection:
        for project in projects:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, name, city, zone, promoter, asset_type,
                    first_detected_at, last_updated_at, launch_score,
                    confidence_score, investment_score, urgency_score,
                    recommendation, status, summary, source_count,
                    signal_count, prices_json, aliases_json, channels_json,
                    sources_json, source_urls_json, evidence_json, reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name=excluded.name,
                    city=excluded.city,
                    zone=excluded.zone,
                    promoter=excluded.promoter,
                    asset_type=excluded.asset_type,
                    last_updated_at=excluded.last_updated_at,
                    launch_score=excluded.launch_score,
                    confidence_score=excluded.confidence_score,
                    investment_score=excluded.investment_score,
                    urgency_score=excluded.urgency_score,
                    recommendation=excluded.recommendation,
                    status=excluded.status,
                    summary=excluded.summary,
                    source_count=excluded.source_count,
                    signal_count=excluded.signal_count,
                    prices_json=excluded.prices_json,
                    aliases_json=excluded.aliases_json,
                    channels_json=excluded.channels_json,
                    sources_json=excluded.sources_json,
                    source_urls_json=excluded.source_urls_json,
                    evidence_json=excluded.evidence_json,
                    reasons_json=excluded.reasons_json
                """,
                (
                    project.project_id,
                    project.name,
                    project.city,
                    project.zone,
                    project.promoter,
                    project.asset_type,
                    project.first_detected_at,
                    project.last_updated_at,
                    project.launch_score,
                    project.confidence_score,
                    project.investment_score,
                    project.urgency_score,
                    project.recommendation,
                    project.status,
                    project.summary,
                    len(project.sources),
                    len(project.signals),
                    json.dumps(project.prices, ensure_ascii=False),
                    json.dumps(project.aliases, ensure_ascii=False),
                    json.dumps(project.channels, ensure_ascii=False),
                    json.dumps(project.sources, ensure_ascii=False),
                    json.dumps(project.source_urls, ensure_ascii=False),
                    json.dumps(project.evidence, ensure_ascii=False),
                    json.dumps(project.reasons, ensure_ascii=False),
                ),
            )
            for signal in project.signals:
                upsert_signal(connection, project.project_id, signal)
            insert_project_update(connection, project)
        prune_stale_projects(connection, {project.project_id for project in projects})


def upsert_signal(connection: sqlite3.Connection, project_id: str, signal: SignalEvent) -> None:
    connection.execute(
        """
        INSERT INTO signals (
            signal_id, project_id, collector, channel, source, signal_type,
            title, url, text, discovered_at, is_primary, launch_weight,
            confidence_weight, metadata_json, reasons_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(signal_id) DO UPDATE SET
            title=excluded.title,
            text=excluded.text,
            discovered_at=excluded.discovered_at,
            metadata_json=excluded.metadata_json,
            reasons_json=excluded.reasons_json
        """,
        (
            signal.signal_id,
            project_id,
            signal.collector,
            signal.channel,
            signal.source,
            signal.signal_type,
            signal.title,
            signal.url,
            signal.text,
            signal.discovered_at,
            int(signal.is_primary),
            signal.launch_weight,
            signal.confidence_weight,
            json.dumps(signal.metadata, ensure_ascii=False),
            json.dumps(signal.reasons, ensure_ascii=False),
        ),
    )


def insert_project_update(connection: sqlite3.Connection, project: ProjectRecord) -> None:
    existing = connection.execute(
        "SELECT 1 FROM project_updates WHERE project_id = ? AND observed_at = ? LIMIT 1",
        (project.project_id, project.last_updated_at),
    ).fetchone()
    if existing:
        return
    connection.execute(
        """
        INSERT INTO project_updates (
            project_id, observed_at, launch_score, confidence_score,
            investment_score, urgency_score, source_count, signal_count,
            status, recommendation, reasons_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project.project_id,
            project.last_updated_at,
            project.launch_score,
            project.confidence_score,
            project.investment_score,
            project.urgency_score,
            len(project.sources),
            len(project.signals),
            project.status,
            project.recommendation,
            json.dumps(project.reasons, ensure_ascii=False),
        ),
    )


def prune_stale_projects(connection: sqlite3.Connection, active_project_ids: set[str]) -> None:
    if not active_project_ids:
        return
    placeholders = ", ".join("?" for _ in active_project_ids)
    stale_rows = connection.execute(
        f"SELECT project_id FROM projects WHERE project_id NOT IN ({placeholders})",
        tuple(active_project_ids),
    ).fetchall()
    stale_ids = [row["project_id"] for row in stale_rows]
    if not stale_ids:
        return
    stale_placeholders = ", ".join("?" for _ in stale_ids)
    connection.execute(
        f"DELETE FROM signals WHERE project_id IN ({stale_placeholders})",
        tuple(stale_ids),
    )
    connection.execute(
        f"DELETE FROM project_updates WHERE project_id IN ({stale_placeholders})",
        tuple(stale_ids),
    )
    connection.execute(
        f"DELETE FROM projects WHERE project_id IN ({stale_placeholders})",
        tuple(stale_ids),
    )


def load_projects() -> list[ProjectRecord]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT project_id, name, city, zone, promoter, asset_type,
                   first_detected_at, last_updated_at, launch_score,
                   confidence_score, investment_score, urgency_score,
                   recommendation, status, summary, prices_json,
                   aliases_json, channels_json, sources_json,
                   source_urls_json, evidence_json, reasons_json
            FROM projects
            ORDER BY confidence_score DESC, investment_score DESC, last_updated_at DESC
            """
        ).fetchall()
    return [
        ProjectRecord(
            project_id=row["project_id"],
            name=row["name"],
            city=row["city"],
            zone=row["zone"],
            promoter=row["promoter"],
            asset_type=row["asset_type"],
            first_detected_at=row["first_detected_at"],
            last_updated_at=row["last_updated_at"],
            launch_score=row["launch_score"],
            confidence_score=row["confidence_score"],
            investment_score=row["investment_score"],
            urgency_score=row["urgency_score"],
            recommendation=row["recommendation"],
            status=row["status"],
            summary=row["summary"],
            prices=json.loads(row["prices_json"]),
            aliases=json.loads(row["aliases_json"]),
            channels=json.loads(row["channels_json"]),
            sources=json.loads(row["sources_json"]),
            source_urls=json.loads(row["source_urls_json"]),
            evidence=json.loads(row["evidence_json"]),
            reasons=json.loads(row["reasons_json"]),
            timeline=load_project_timeline(row["project_id"]),
            signals=[],
        )
        for row in rows
    ]


def load_project_map() -> dict[str, ProjectRecord]:
    return {project.project_id: project for project in load_projects()}


def load_project_timeline(project_id: str, limit: int = 20) -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT observed_at, launch_score, confidence_score, investment_score,
                   urgency_score, status, recommendation
            FROM project_updates
            WHERE project_id = ?
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return [
        {
            "observed_at": row["observed_at"],
            "launch_score": row["launch_score"],
            "confidence_score": row["confidence_score"],
            "investment_score": row["investment_score"],
            "urgency_score": row["urgency_score"],
            "status": row["status"],
            "recommendation": row["recommendation"],
        }
        for row in rows
    ]
