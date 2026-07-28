from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from core.database import connect

DEVELOPER_MENTION_PATTERN = re.compile(
    r"(?:promoteur(?:\s+immobilier)?|développeur(?:\s+immobilier)?|developpeur(?:\s+immobilier)?|"
    r"promotion immobilière|promotion immobiliere)\s*[:\-]?\s+([A-ZÀ-Ü][\w'’.\-]*(?:\s+[A-ZÀ-Ü][\w'’.\-]*){0,3})"
)

GENERIC_NAME_BLOCKLIST = {
    "meta page",
    "google news",
    "google search",
    "facebook",
    "instagram",
    "linkedin",
}

MIN_CANDIDATE_NAME_LENGTH = 3


def normalize_candidate_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", name or "").strip()


def is_plausible_candidate(name: str, tracked_promoters: set[str]) -> bool:
    normalized = normalize_candidate_name(name)
    if len(normalized) < MIN_CANDIDATE_NAME_LENGTH:
        return False
    lowered = normalized.lower()
    if lowered in GENERIC_NAME_BLOCKLIST:
        return False
    if lowered in {promoter.lower() for promoter in tracked_promoters}:
        return False
    return True


def extract_candidates_from_signal(signal, tracked_promoters: set[str]) -> list[dict]:
    candidates: list[dict] = []
    metadata = getattr(signal, "metadata", None) or {}
    if signal.channel == "advertising" and not getattr(signal, "promoter_hint", None):
        page_name = metadata.get("page_name") or signal.source
        if page_name and is_plausible_candidate(page_name, tracked_promoters):
            candidates.append(
                {
                    "name": normalize_candidate_name(page_name),
                    "reason": "page Meta Ad Library non reconnue comme promoteur suivi",
                    "url": signal.url,
                    "confidence": 55,
                }
            )
    text = f"{signal.title} {signal.text}"
    for match in DEVELOPER_MENTION_PATTERN.finditer(text):
        name = normalize_candidate_name(match.group(1))
        if is_plausible_candidate(name, tracked_promoters):
            candidates.append(
                {
                    "name": name,
                    "reason": "mention explicite \"promoteur/développeur\" détectée dans le texte",
                    "url": signal.url,
                    "confidence": 40,
                }
            )
    return candidates


def discover_candidates(signals, config: dict) -> list[dict]:
    tracked_promoters = set(config.get("promoters", {}).get("tracked", []))
    discovered: list[dict] = []
    for signal in signals:
        discovered.extend(extract_candidates_from_signal(signal, tracked_promoters))
    return discovered


def init_candidate_table() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidate_promoters (
                name TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL DEFAULT 0,
                confidence INTEGER NOT NULL DEFAULT 0,
                reasons_json TEXT NOT NULL DEFAULT '[]',
                example_urls_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending'
            );
            """
        )


def upsert_candidates(candidates: list[dict]) -> None:
    if not candidates:
        return
    init_candidate_table()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        for candidate in candidates:
            existing = connection.execute(
                "SELECT occurrence_count, confidence, reasons_json, example_urls_json "
                "FROM candidate_promoters WHERE name = ?",
                (candidate["name"],),
            ).fetchone()
            if existing:
                reasons = json.loads(existing["reasons_json"])
                urls = json.loads(existing["example_urls_json"])
                if candidate["reason"] not in reasons:
                    reasons.append(candidate["reason"])
                if candidate["url"] not in urls:
                    urls.append(candidate["url"])
                occurrence_count = existing["occurrence_count"] + 1
                confidence = min(95, max(existing["confidence"], candidate["confidence"]) + min(occurrence_count, 5) * 3)
                connection.execute(
                    """
                    UPDATE candidate_promoters
                    SET last_seen_at = ?, occurrence_count = ?, confidence = ?,
                        reasons_json = ?, example_urls_json = ?
                    WHERE name = ?
                    """,
                    (
                        now,
                        occurrence_count,
                        confidence,
                        json.dumps(reasons[:5], ensure_ascii=False),
                        json.dumps(urls[:5], ensure_ascii=False),
                        candidate["name"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO candidate_promoters (
                        name, first_seen_at, last_seen_at, occurrence_count,
                        confidence, reasons_json, example_urls_json, status
                    ) VALUES (?, ?, ?, 1, ?, ?, ?, 'pending')
                    """,
                    (
                        candidate["name"],
                        now,
                        now,
                        candidate["confidence"],
                        json.dumps([candidate["reason"]], ensure_ascii=False),
                        json.dumps([candidate["url"]], ensure_ascii=False),
                    ),
                )


def load_pending_candidates(min_confidence: int = 0) -> list[dict]:
    init_candidate_table()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT name, first_seen_at, last_seen_at, occurrence_count, confidence,
                   reasons_json, example_urls_json, status
            FROM candidate_promoters
            WHERE status = 'pending' AND confidence >= ?
            ORDER BY confidence DESC, occurrence_count DESC
            """,
            (min_confidence,),
        ).fetchall()
    return [
        {
            "name": row["name"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "occurrence_count": row["occurrence_count"],
            "confidence": row["confidence"],
            "reasons": json.loads(row["reasons_json"]),
            "example_urls": json.loads(row["example_urls_json"]),
            "status": row["status"],
        }
        for row in rows
    ]
