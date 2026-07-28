from __future__ import annotations

import re

SOLD_OUT_MARKERS = [
    "stock épuisé",
    "stock epuise",
    "plus de disponibilité",
    "plus de disponibilite",
    "plus aucun lot disponible",
    "plus aucune disponibilité",
    "plus aucune disponibilite",
    "projet complet",
    "toutes les unités vendues",
    "toutes les unites vendues",
    "vendu à 100%",
    "vendu a 100%",
    "sold out",
    "programme complet",
    "résidence complète",
    "residence complete",
]
LIMITED_MARKERS = [
    "dernières unités",
    "dernieres unites",
    "dernière tranche",
    "derniere tranche",
    "derniers lots",
    "dernier lots",
    "dernières villas",
    "dernieres villas",
    "derniers appartements",
    "stock limité",
    "stock limite",
    "quelques lots restants",
    "quelques unités restantes",
    "quelques unites restantes",
    "offre limitée",
    "offre limitee",
    "dernière chance",
    "derniere chance",
    "peu de disponibilité",
    "peu de disponibilite",
    "dernières opportunités",
    "dernieres opportunites",
]
AVAILABLE_MARKERS = [
    "disponible",
    "disponibles",
    "en vente",
    "nouvelle tranche",
    "lots disponibles",
    "livraison immédiate",
    "livraison immediate",
    "stock disponible",
    "large choix",
]

STATUS_PRIORITY = ["sold_out", "limited", "available"]

UNIT_COUNT_PATTERN = re.compile(
    r"(\d{1,3})\s*(?:lots?|villas?|appartements?|unit[ée]s?)\s*(?:restant(?:e|s)?|disponible(?:s)?)",
    re.I,
)
SURFACE_RANGE_PATTERN = re.compile(r"(\d{2,4})\s*(?:à|a|-)\s*(\d{2,4})\s*m(?:2|²)", re.I)
SURFACE_SINGLE_PATTERN = re.compile(r"(\d{2,4})\s*m(?:2|²)", re.I)


def detect_availability_status(text: str) -> str | None:
    lowered = (text or "").lower()
    if any(marker in lowered for marker in SOLD_OUT_MARKERS):
        return "sold_out"
    if any(marker in lowered for marker in LIMITED_MARKERS):
        return "limited"
    if any(marker in lowered for marker in AVAILABLE_MARKERS):
        return "available"
    return None


def detect_unit_count(text: str) -> int | None:
    match = UNIT_COUNT_PATTERN.search(text or "")
    if not match:
        return None
    value = int(match.group(1))
    if 1 <= value <= 999:
        return value
    return None


def detect_surface_m2(text: str) -> dict:
    text = text or ""
    range_match = SURFACE_RANGE_PATTERN.search(text)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        return {"min": min(low, high), "max": max(low, high)}
    single_match = SURFACE_SINGLE_PATTERN.search(text)
    if single_match:
        value = int(single_match.group(1))
        return {"min": value, "max": value}
    return {"min": None, "max": None}


def analyze_availability(text: str) -> dict:
    return {
        "status": detect_availability_status(text),
        "unit_count": detect_unit_count(text),
        "surface_m2": detect_surface_m2(text),
    }


def status_rank(status: str | None) -> int:
    if status not in STATUS_PRIORITY:
        return len(STATUS_PRIORITY)
    return STATUS_PRIORITY.index(status)


def most_urgent_status(statuses: list[str | None]) -> str | None:
    candidates = [status for status in statuses if status]
    if not candidates:
        return None
    return min(candidates, key=status_rank)


def project_availability_summary(signals) -> dict:
    statuses: list[str] = []
    unit_counts: list[int] = []
    surface_min_values: list[int] = []
    surface_max_values: list[int] = []
    matched_signals = 0
    for signal in signals:
        metadata = getattr(signal, "metadata", None) or {}
        availability = metadata.get("availability")
        if not availability:
            continue
        matched_signals += 1
        if availability.get("status"):
            statuses.append(availability["status"])
        if availability.get("unit_count"):
            unit_counts.append(availability["unit_count"])
        surface = availability.get("surface_m2") or {}
        if surface.get("min"):
            surface_min_values.append(surface["min"])
        if surface.get("max"):
            surface_max_values.append(surface["max"])
    return {
        "status": most_urgent_status(statuses),
        "unit_count_min": min(unit_counts) if unit_counts else None,
        "surface_m2": {
            "min": min(surface_min_values) if surface_min_values else None,
            "max": max(surface_max_values) if surface_max_values else None,
        },
        "signal_count": matched_signals,
    }
