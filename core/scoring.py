from __future__ import annotations

import re

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


def enrich_signal(signal: SignalEvent, config: dict) -> SignalEvent:
    text = f"{signal.title} {signal.text}".lower()
    signal.price_mad = detect_price(text)
    signal.asset_type_hint, asset_weight = detect_asset_type(text, config.get("asset_preferences", {}))
    signal.city_hint, signal.zone_hint = detect_city_zone(f"{signal.source} {signal.title} {signal.url}", config)
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
    if asset_weight:
        signal.confidence_weight += round(asset_weight * 0.05)
    return signal


def enrich_project(project: ProjectRecord, config: dict) -> ProjectRecord:
    primary_signals = [signal for signal in project.signals if signal.is_primary]
    listing_signals = [signal for signal in project.signals if signal.channel == "listing"]
    launch_score = sum(signal.launch_weight for signal in primary_signals) + min(len(listing_signals) * 3, 9)
    confidence_score = sum(signal.confidence_weight for signal in primary_signals) + min(len(project.sources) * 6, 24)
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
    if project.confidence_score >= config["alerts"]["immediate_confidence_threshold"]:
        project.status = "urgent"
        project.recommendation = "Buy"
    elif project.confidence_score >= config["alerts"]["digest_confidence_threshold"]:
        project.status = "watch"
        project.recommendation = "Watch"
    else:
        project.status = "monitor"
        project.recommendation = "Monitor"
    project.summary = build_summary(project)
    return project


def build_summary(project: ProjectRecord) -> str:
    parts = [
        project.name,
        f"Promoteur: {project.promoter or 'à confirmer'}",
        f"Ville: {project.city or 'à confirmer'}",
        f"Zone: {project.zone or 'à confirmer'}",
        f"Sources: {', '.join(project.sources[:4])}",
    ]
    return " | ".join(parts)

