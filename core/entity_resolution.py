from __future__ import annotations

import hashlib
import re
from collections import Counter
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


def canonical_name(name: str) -> str:
    return " ".join(project_tokens(name)) or normalize(name)


def alias_candidates(signal: SignalEvent) -> list[str]:
    candidates = [signal.project_name_hint or "", infer_project_name(signal), signal.title]
    slug = urlparse(signal.url).path.split("/")[-1].replace("-", " ").strip()
    if slug:
        candidates.append(slug.title())
    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        key = normalize(candidate)
        if key in seen:
            continue
        seen.add(key)
        aliases.append(candidate)
    return aliases


def signal_identity(signal: SignalEvent) -> dict:
    aliases = alias_candidates(signal)
    token_sets = [set(project_tokens(alias)) for alias in aliases]
    primary_tokens = max(token_sets, key=len, default=set())
    promoter = normalize(signal.promoter_hint or signal.source)
    city = normalize(signal.city_hint or "")
    zone = normalize(signal.zone_hint or "")
    return {
        "aliases": aliases,
        "tokens": primary_tokens,
        "promoter": promoter,
        "city": city,
        "zone": zone,
        "source": normalize(signal.source),
    }


def project_key(name: str, city: str | None, promoter: str | None) -> str:
    raw = f"{canonical_name(name)}|{normalize(city or '')}|{normalize(promoter or '')}"
    return hashlib.sha1(raw.encode()).hexdigest()


def score_group_match(group: dict, signal: SignalEvent) -> int:
    identity = signal_identity(signal)
    score = 0
    group_tokens = group["tokens"]
    overlap = len(group_tokens & identity["tokens"])
    name_match = any(canonical_name(alias) in group["alias_keys"] for alias in identity["aliases"])
    exactish_signals = {"meta_ad", "promoter_page", "project_page", "listing_detail", "search_result", "urbanism_page"}
    if signal.signal_type in exactish_signals and overlap == 0 and not name_match:
        return 0
    if overlap >= 2:
        score += 50
    elif overlap == 1:
        score += 18
    if group["promoter"] and identity["promoter"] and group["promoter"] == identity["promoter"]:
        score += 25
    if group["city"] and identity["city"] and group["city"] == identity["city"]:
        score += 20
    if group["zone"] and identity["zone"] and group["zone"] == identity["zone"]:
        score += 8
    if group["source"] == identity["source"]:
        score += 5
    if name_match:
        score += 30
    return score


def add_signal_to_group(group: dict, signal: SignalEvent) -> None:
    identity = signal_identity(signal)
    group["signals"].append(signal)
    group["tokens"].update(identity["tokens"])
    group["alias_keys"].update(canonical_name(alias) for alias in identity["aliases"])
    group["aliases"].update(identity["aliases"])
    if not group["promoter"] and identity["promoter"]:
        group["promoter"] = identity["promoter"]
    if not group["city"] and identity["city"]:
        group["city"] = identity["city"]
    if not group["zone"] and identity["zone"]:
        group["zone"] = identity["zone"]


def best_group(groups: list[dict], signal: SignalEvent) -> dict | None:
    ranked = sorted(((score_group_match(group, signal), group) for group in groups), key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < 45:
        return None
    return ranked[0][1]


def resolve_projects(signals: list[SignalEvent], config: dict) -> list[ProjectRecord]:
    enriched = [enrich_signal(signal, config) for signal in signals]
    enriched.sort(key=lambda signal: (signal.promoter_hint or "", signal.city_hint or "", signal.discovered_at))
    groups: list[dict] = []
    for signal in enriched:
        group = best_group(groups, signal)
        if group is None:
            identity = signal_identity(signal)
            group = {
                "signals": [],
                "tokens": set(identity["tokens"]),
                "aliases": set(identity["aliases"]),
                "alias_keys": {canonical_name(alias) for alias in identity["aliases"]},
                "promoter": identity["promoter"],
                "city": identity["city"],
                "zone": identity["zone"],
                "source": identity["source"],
            }
            groups.append(group)
        add_signal_to_group(group, signal)
    projects = [build_project(group["signals"], config) for group in groups]
    projects.sort(key=lambda project: (project.confidence_score, project.investment_score), reverse=True)
    return projects


def choose_name(signals: list[SignalEvent]) -> tuple[str, list[str]]:
    aliases: list[str] = []
    for signal in signals:
        aliases.extend(alias_candidates(signal))
    counts = Counter(canonical_name(alias) for alias in aliases if alias.strip())
    if not counts:
        return signals[0].source, [signals[0].source]
    best_key = counts.most_common(1)[0][0]
    normalized_to_display: dict[str, str] = {}
    for alias in aliases:
        normalized_to_display.setdefault(canonical_name(alias), alias)
    best_name = normalized_to_display.get(best_key, aliases[0])
    unique_aliases = list(dict.fromkeys(alias for alias in aliases if canonical_name(alias) == best_key or len(project_tokens(alias)) >= 2))
    return best_name, unique_aliases[:6]


def build_project(signals: list[SignalEvent], config: dict) -> ProjectRecord:
    signals.sort(key=lambda signal: signal.discovered_at)
    primary = [signal for signal in signals if signal.is_primary]
    exemplar = primary[0] if primary else signals[0]
    project_name, aliases = choose_name(signals)
    sources = sorted({signal.source for signal in signals})
    channels = sorted({signal.channel for signal in signals})
    source_urls = list(dict.fromkeys(signal.url for signal in signals))[:12]
    reasons: list[str] = []
    for signal in signals:
        reasons.extend(signal.reasons)
    unique_reasons = list(dict.fromkeys(reasons))[:10]
    prices = [signal.price_mad for signal in signals if signal.price_mad]
    promoter = exemplar.promoter_hint or next((signal.promoter_hint for signal in signals if signal.promoter_hint), None)
    city = exemplar.city_hint or next((signal.city_hint for signal in signals if signal.city_hint), None)
    zone = exemplar.zone_hint or next((signal.zone_hint for signal in signals if signal.zone_hint), None)
    asset_type = exemplar.asset_type_hint or next((signal.asset_type_hint for signal in signals if signal.asset_type_hint), None)
    timeline = [
        {
            "detected_at": signal.discovered_at,
            "channel": signal.channel,
            "source": signal.source,
            "title": signal.title[:160],
            "url": signal.url,
        }
        for signal in signals[:20]
    ]
    project = ProjectRecord(
        project_id=project_key(project_name, city, promoter),
        name=project_name,
        city=city,
        zone=zone,
        promoter=promoter,
        asset_type=asset_type,
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
        aliases=aliases,
        channels=channels,
        sources=sources,
        source_urls=source_urls,
        evidence={},
        reasons=unique_reasons,
        timeline=timeline,
        signals=signals,
    )
    return enrich_project(project, config)
