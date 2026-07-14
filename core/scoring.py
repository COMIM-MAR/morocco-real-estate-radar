from __future__ import annotations

import re

from core.enrichment import enrich_project_intelligence
from core.models import ProjectRecord, SignalEvent

RENTAL_MARKERS = ["à louer", "a louer", "location", "par mois", "/mois", "mensuel"]
LAUNCH_MARKERS = [
    "lancement",
    "pré-commercialisation",
    "pre-commercialisation",
    "réservation",
    "reservation",
    "ouverture des ventes",
    "commercialisation",
    "nouveau projet",
    "lotissement",
]
ASSET_PATTERNS = [
    ("villa", r"\b(villa|villas)\b"),
    ("land_r4_plus", r"\b(r\+4|r4|r\+5|r5|terrain|lotissement|immeuble)\b"),
    ("penthouse", r"\bpenthouse\b"),
    ("apartment_3_bed", r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b"),
    ("apartment_2_bed", r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b"),
    ("studio", r"\bstudio\b"),
]


def has_any(text: str, markers: list[str]) -> bool:
    return any(marker.lower() in text for marker in markers)


def detect_price(text: str) -> int | None:
    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)",
        r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)",
        r"(?:prix|à partir de|a partir de)\s*(?:de)?\s*(\d[\d\s.,]{4,})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            raw = match.group(1)
            full = match.group(0).lower()
            if "mdh" in full or "million" in full:
                try:
                    return int(float(raw.replace(",", ".")) * 1_000_000)
                except ValueError:
                    continue
            value = int(re.sub(r"\D", "", raw) or 0)
            if 100_000 <= value <= 30_000_000:
                return value
    return None


def detect_asset_type(text: str, preferences: dict) -> tuple[str | None, int]:
    lowered = text.lower()
    for name, pattern in ASSET_PATTERNS:
        if re.search(pattern, lowered):
            return name, preferences.get(name, 0)
    if re.search(r"\b(appartement|appart|résidence|residence)\b", lowered):
        return "apartment_unknown", 35
    return None, 0


def detect_city_zone(text: str, config: dict) -> tuple[str | None, str | None]:
    lowered = text.lower()
    for city_key, city_cfg in config.get("cities", {}).items():
        city_label = city_cfg["label"].lower()
        city_match = city_key in lowered or city_label in lowered
        zone_match = None
        for zone in city_cfg.get("zones", []):
            if zone.lower() in lowered:
                zone_match = zone
                city_match = True
                break
        if city_match:
            return city_cfg["label"], zone_match
    return None, None


def detect_promoter(text: str, config: dict) -> str | None:
    lowered = text.lower()
    for promoter in config.get("promoters", {}).get("tracked", []):
        if promoter.lower() in lowered:
            return promoter
    return None


def channel_label(channel: str) -> str:
    labels = {
        "project_discovery": "page promoteur",
        "advertising": "publicité Meta",
        "google_discovery": "indexation Google",
        "urbanism": "document urbanisme",
        "news": "presse",
        "social": "social",
        "listing": "listing",
    }
    return labels.get(channel, channel)


def normalized_contains(haystack: str | None, needle: str | None) -> bool:
    if not haystack or not needle:
        return False
    return re.sub(r"\s+", " ", needle.lower()).strip() in re.sub(r"\s+", " ", haystack.lower()).strip()


def signal_matches_project(signal: SignalEvent, project: ProjectRecord) -> bool:
    promoter_sensitive_channels = {"advertising", "project_discovery", "google_discovery", "social", "news"}
    promoter_ok = True
    if project.promoter:
        if signal.channel in promoter_sensitive_channels:
            promoter_ok = (
                (signal.promoter_hint or "").lower() == project.promoter.lower()
                or normalized_contains(signal.title, project.promoter)
                or normalized_contains(signal.text, project.promoter)
                or normalized_contains(signal.url, project.promoter)
                or normalized_contains(signal.source, project.promoter)
            )
    city_ok = True
    if project.city:
        city_ok = (
            (signal.city_hint or "").lower() == project.city.lower()
            or normalized_contains(signal.title, project.city)
            or normalized_contains(signal.text, project.city)
            or normalized_contains(signal.url, project.city)
            or normalized_contains(signal.source, project.city)
        )
    zone_ok = True
    if project.zone:
        if signal.zone_hint:
            zone_ok = (signal.zone_hint or "").lower() == project.zone.lower()
        else:
            zone_ok = True
    return promoter_ok and city_ok and zone_ok


def signal_proof_level(signal: SignalEvent) -> str:
    if signal.signal_type in {"search_result", "urbanism_page", "project_page", "promoter_page", "listing_page", "listing_detail", "news_result", "social_post", "meta_ad"}:
        return "direct"
    return "watch"


def signal_proof_note(signal: SignalEvent) -> str:
    if signal.signal_type == "meta_ad":
        ad_id = signal.metadata.get("ad_id") if isinstance(signal.metadata, dict) else None
        return f"Publicité Meta exacte détectée{f' (ad_id {ad_id})' if ad_id else ''}."
    if signal.signal_type == "meta_watch":
        return "Recherche Meta Ad Library, pas encore publicité unitaire extraite."
    if signal.signal_type == "search_watch":
        return "Requête Google de veille, pas encore résultat cible confirmé."
    if signal.signal_type == "urbanism_watch":
        return "Source urbanisme surveillée, sans document précis extrait sur ce run."
    if signal.signal_type == "search_result":
        return "Résultat Google réellement détecté."
    if signal.signal_type == "urbanism_page":
        return "Page ou document urbanisme réellement détecté."
    return "Signal détecté par le moteur."


def proof_payload(signal: SignalEvent) -> dict:
    return {
        "title": signal.title,
        "url": signal.url,
        "source": signal.source,
        "channel": signal.channel,
        "channel_label": channel_label(signal.channel),
        "signal_type": signal.signal_type,
        "proof_level": signal_proof_level(signal),
        "proof_note": signal_proof_note(signal),
    }


def representative_signals(project: ProjectRecord, channel: str, limit: int = 2) -> list[dict]:
    filtered = [
        signal
        for signal in project.signals
        if signal.channel == channel
        and signal.is_primary
        and signal_proof_level(signal) == "direct"
        and signal_matches_project(signal, project)
    ]
    filtered.sort(
        key=lambda signal: (
            0 if signal_proof_level(signal) == "direct" else 1,
            -signal.confidence_weight,
            -signal.launch_weight,
        )
    )
    return [proof_payload(signal) for signal in filtered[:limit]]


def confirmation_matrix(project: ProjectRecord) -> dict:
    project_primary_signals = [
        signal
        for signal in project.signals
        if signal.is_primary and signal_matches_project(signal, project)
    ]
    direct_project_signals = [
        signal for signal in project_primary_signals if signal_proof_level(signal) == "direct"
    ]
    primary_channels = sorted({signal.channel for signal in project_primary_signals})
    secondary_channels = sorted({signal.channel for signal in project.signals if not signal.is_primary})
    strong_pairs = [
        ("project_discovery", "advertising"),
        ("project_discovery", "google_discovery"),
        ("project_discovery", "urbanism"),
        ("advertising", "google_discovery"),
        ("urbanism", "google_discovery"),
        ("news", "project_discovery"),
    ]
    confirmations = []
    confirmation_details = []
    direct_channel_set = {signal.channel for signal in direct_project_signals}
    for left, right in strong_pairs:
        left_proofs = representative_signals(project, left)
        right_proofs = representative_signals(project, right)
        if left in direct_channel_set and right in direct_channel_set and left_proofs and right_proofs:
            label = f"{channel_label(left)} + {channel_label(right)}"
            confirmations.append(label)
            confirmation_details.append(
                {
                    "id": f"{left}__{right}",
                    "label": label,
                    "channels": [left, right],
                    "proofs": left_proofs + right_proofs,
                }
            )
    return {
        "primary_channels": primary_channels,
        "secondary_channels": secondary_channels,
        "confirmations": confirmations,
        "confirmation_details": confirmation_details,
    }


def enrich_signal(signal: SignalEvent, config: dict) -> SignalEvent:
    text = f"{signal.title} {signal.text}".lower()
    signal.price_mad = detect_price(text)
    signal.asset_type_hint, asset_weight = detect_asset_type(text, config.get("asset_preferences", {}))
    signal.city_hint, signal.zone_hint = detect_city_zone(
        f"{signal.source} {signal.title} {signal.text} {signal.url}",
        config,
    )
    signal.promoter_hint = signal.metadata.get("promoter_hint") or detect_promoter(text, config)
    if signal.price_mad:
        signal.reasons.append(f"prix détecté: {signal.price_mad} MAD")
    if signal.asset_type_hint:
        signal.reasons.append(f"type: {signal.asset_type_hint}")
    if signal.city_hint:
        signal.reasons.append(f"ville: {signal.city_hint}")
    if signal.zone_hint:
        signal.reasons.append(f"zone: {signal.zone_hint}")
    if has_any(text, RENTAL_MARKERS):
        signal.launch_weight = max(signal.launch_weight - 20, 0)
        signal.confidence_weight = max(signal.confidence_weight - 10, 0)
        signal.reasons.append("signal de location, faible priorité")
    if has_any(text, LAUNCH_MARKERS):
        signal.launch_weight += 12
        signal.confidence_weight += 8
        signal.reasons.append("marqueur de lancement détecté")
    if signal.channel == "google_discovery" and signal.signal_type == "search_result":
        signal.confidence_weight += 6
        signal.reasons.append("page détectée via Google")
    if signal.channel == "urbanism":
        signal.launch_weight += 6
        signal.reasons.append("source urbanisme prioritaire")
    if asset_weight:
        signal.confidence_weight += round(asset_weight * 0.05)
    return signal


def enrich_project(project: ProjectRecord, config: dict) -> ProjectRecord:
    primary_signals = [signal for signal in project.signals if signal.is_primary]
    listing_signals = [signal for signal in project.signals if signal.channel == "listing"]
    matrix = confirmation_matrix(project)
    confirmation_bonus = min(len(matrix["confirmations"]) * 14, 35)
    primary_bonus = min(len(matrix["primary_channels"]) * 6, 24)
    listing_bonus = min(len(listing_signals) * 3, 9)
    launch_score = sum(signal.launch_weight for signal in primary_signals) + listing_bonus + round(confirmation_bonus * 0.6)
    confidence_score = sum(signal.confidence_weight for signal in primary_signals) + min(len(project.sources) * 6, 24) + confirmation_bonus + primary_bonus
    investment_score = 0
    if project.city:
        city_config = next(
            (cfg for cfg in config.get("cities", {}).values() if cfg["label"] == project.city),
            None,
        )
        if city_config:
            investment_score += round(city_config["priority"] * 0.45)
    if project.zone:
        investment_score += 16
    if project.asset_type:
        investment_score += round(config.get("asset_preferences", {}).get(project.asset_type, 0) * 0.4)
    min_price = project.prices.get("min")
    if min_price:
        if min_price <= config["profile"]["cash_ready"]:
            investment_score += 15
        elif min_price <= config["profile"]["max_budget"]:
            investment_score += 8
        else:
            investment_score -= 18
    urgency_score = round((launch_score * 0.45) + (confidence_score * 0.35) + (investment_score * 0.2))
    project.launch_score = min(100, max(0, launch_score))
    project.confidence_score = min(100, max(0, confidence_score))
    project.investment_score = min(100, max(0, investment_score))
    project.urgency_score = min(100, max(0, urgency_score))
    project.evidence = {
        "signal_count": len(project.signals),
        "primary_signal_count": len(primary_signals),
        "listing_signal_count": len(listing_signals),
        "source_count": len(project.sources),
        "channel_count": len(project.channels),
        "primary_channels": matrix["primary_channels"],
        "secondary_channels": matrix["secondary_channels"],
        "confirmations": matrix["confirmations"],
        "confirmation_details": matrix["confirmation_details"],
        "confirmation_count": len(matrix["confirmations"]),
    }
    if matrix["confirmations"]:
        project.reasons = matrix["confirmations"][:4] + project.reasons
    if project.confidence_score >= config["alerts"]["immediate_confidence_threshold"]:
        project.status = "urgent"
        project.recommendation = "Buy"
    elif project.confidence_score >= config["alerts"]["digest_confidence_threshold"]:
        project.status = "watch"
        project.recommendation = "Watch"
    else:
        project.status = "monitor"
        project.recommendation = "Monitor"
    enrich_project_intelligence(project, config)
    project.summary = build_summary(project)
    return project


def build_summary(project: ProjectRecord) -> str:
    confirmation_text = ", ".join(project.evidence.get("confirmations", [])[:3]) or "confirmation en cours"
    price_text = project.evidence.get("price_evolution", {}).get("summary", "prix à confirmer")
    parts = [
        project.name,
        f"Promoteur: {project.promoter or 'à confirmer'}",
        f"Ville: {project.city or 'à confirmer'}",
        f"Zone: {project.zone or 'à confirmer'}",
        f"Confirmations: {confirmation_text}",
        price_text,
    ]
    return " | ".join(parts)
