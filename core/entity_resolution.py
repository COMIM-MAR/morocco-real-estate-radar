from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from urllib.parse import urlparse

from core.models import ProjectRecord, SignalEvent
from core.scoring import enrich_project, enrich_signal

PROJECT_STOPWORDS = {
    "maroc",
    "morocco",
    "immobilier",
    "immobiliere",
    "residence",
    "résidence",
    "projet",
    "programme",
    "appartement",
    "appartements",
    "villas",
    "villa",
    "lotissement",
}


def normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ\s-]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def project_tokens(text: str) -> list[str]:
    words = normalize(text).split()
    return [word for word in words if len(word) > 2 and word not in PROJECT_STOPWORDS]


def infer_project_name(signal: SignalEvent) -> str:
    text = f"{signal.title} {signal.url}"
    patterns = [
        r"(sun[\s-]?hills?)",
        r"(prestigia[\s-][a-z0-9-]+)",
        r"(résidence[\s-][a-z0-9-]+)",
        r"(residence[\s-][a-z0-9-]+)",
        r"(lotissement[\s-][a-z0-9-]+)",
        r"(projet[\s-][a-z0-9-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalize(text), re.I)
        if match:
            return match.group(1).replace("-", " ").title()
    slug = urlparse(signal.url).path.split("/")[-1]
    slug_tokens = [token for token in slug.replace("-", " ").split() if len(token) > 2]
    if slug_tokens:
        return " ".join(word.capitalize() for word in slug_tokens[:4])
    tokens = project_tokens(signal.title)
    return " ".join(word.capitalize() for word in tokens[:4]) or signal.source


def project_key(signal: SignalEvent) -> str:
    name = infer_project_name(signal)
    city = signal.city_hint or ""
    promoter = signal.promoter_hint or signal.source
    raw = f"{normalize(name)}|{normalize(city)}|{normalize(promoter)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def resolve_projects(signals: list[SignalEvent], config: dict) -> list[ProjectRecord]:
    enriched = [enrich_signal(signal, config) for signal in signals]
    grouped: dict[str, list[SignalEvent]] = defaultdict(list)
    for signal in enriched:
        grouped[project_key(signal)].append(signal)
    projects = [build_project(project_id, group, config) for project_id, group in grouped.items()]
    projects.sort(key=lambda project: (project.confidence_score, project.investment_score), reverse=True)
    return projects


def build_project(project_id: str, signals: list[SignalEvent], config: dict) -> ProjectRecord:
    signals.sort(key=lambda signal: signal.discovered_at)
    primary = [signal for signal in signals if signal.is_primary]
    exemplar = primary[0] if primary else signals[0]
    sources = sorted({signal.source for signal in signals})
    reasons: list[str] = []
    for signal in signals:
        reasons.extend(signal.reasons)
    unique_reasons = list(dict.fromkeys(reasons))[:10]
    prices = [signal.price_mad for signal in signals if signal.price_mad]
    project = ProjectRecord(
        project_id=project_id,
        name=infer_project_name(exemplar),
        city=exemplar.city_hint,
        zone=exemplar.zone_hint,
        promoter=exemplar.promoter_hint,
        asset_type=exemplar.asset_type_hint,
        first_detected_at=signals[0].discovered_at,
        last_updated_at=signals[-1].discovered_at,
        launch_score=0,
        confidence_score=0,
        investment_score=0,
        urgency_score=0,
        recommendation="Watch",
        status="watch",
        summary="",
        prices={"min": min(prices) if prices else None, "max": max(prices) if prices else None},
        sources=sources,
        reasons=unique_reasons,
        signals=signals,
    )
    return enrich_project(project, config)

