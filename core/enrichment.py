from __future__ import annotations

import re


CITY_GEO = {
    "Tanger": {"lat": 35.7595, "lng": -5.8340, "sea_distance_km": 3, "station_distance_km": 4, "highway_distance_km": 5},
    "Casablanca": {"lat": 33.5731, "lng": -7.5898, "sea_distance_km": 6, "station_distance_km": 5, "highway_distance_km": 4},
    "Rabat": {"lat": 34.0209, "lng": -6.8416, "sea_distance_km": 7, "station_distance_km": 4, "highway_distance_km": 4},
    "Agadir": {"lat": 30.4278, "lng": -9.5981, "sea_distance_km": 4, "station_distance_km": 9, "highway_distance_km": 6},
    "Marrakech": {"lat": 31.6295, "lng": -7.9811, "sea_distance_km": 180, "station_distance_km": 5, "highway_distance_km": 6},
}

ZONE_OVERRIDES = {
    "Tanja Balia": {"lat": 35.7448, "lng": -5.7855, "sea_distance_km": 2, "station_distance_km": 3, "highway_distance_km": 4},
    "Malabata": {"lat": 35.7830, "lng": -5.7603, "sea_distance_km": 1, "station_distance_km": 4, "highway_distance_km": 5},
    "Ain Diab": {"lat": 33.5928, "lng": -7.6872, "sea_distance_km": 1, "station_distance_km": 8, "highway_distance_km": 5},
    "Hay Riad": {"lat": 33.9701, "lng": -6.8616, "sea_distance_km": 12, "station_distance_km": 6, "highway_distance_km": 4},
}


def geo_profile(city: str | None, zone: str | None) -> dict:
    if zone and zone in ZONE_OVERRIDES:
        return ZONE_OVERRIDES[zone]
    if city and city in CITY_GEO:
        return CITY_GEO[city]
    return {"lat": None, "lng": None, "sea_distance_km": None, "station_distance_km": None, "highway_distance_km": None}


def price_band(min_price: int | None, config: dict) -> str:
    if not min_price:
        return "unknown"
    if min_price <= config["profile"]["cash_ready"]:
        return "cash_ready"
    if min_price <= config["profile"]["max_budget"]:
        return "within_budget"
    return "above_budget"


def recommendation_narrative(project, band: str) -> str:
    if project.confidence_score >= 90 and project.investment_score >= 75:
        return "Acheter rapidement si vérifications terrain confirment le lancement."
    if project.confidence_score >= 75 and band != "above_budget":
        return "Surveiller activement et valider disponibilités, prix et calendrier."
    if band == "above_budget":
        return "Éviter à court terme ou suivre uniquement pour benchmark marché."
    return "Garder en observation jusqu'à nouvelles confirmations."


def price_evolution_summary(timeline: list[dict], current_prices: dict) -> dict:
    current_min = current_prices.get("min")
    seen_prices = []
    for item in timeline:
        detected = item.get("price_mad") if isinstance(item, dict) else None
        if detected:
            seen_prices.append(detected)
    if current_min:
        seen_prices.append(current_min)
    if not seen_prices:
        return {"trend": "unknown", "summary": "Aucune série de prix fiable pour le moment."}
    minimum = min(seen_prices)
    maximum = max(seen_prices)
    if current_min == minimum == maximum:
        trend = "stable"
    elif current_min == minimum and maximum > minimum:
        trend = "down"
    elif current_min == maximum and maximum > minimum:
        trend = "up"
    else:
        trend = "mixed"
    summary = f"Prix observés entre {minimum} et {maximum} MAD."
    return {"trend": trend, "summary": summary}


def roi_hint(project) -> dict:
    base = project.investment_score
    if project.confidence_score >= 85:
        base += 5
    label = "Élevé" if base >= 80 else "Moyen" if base >= 60 else "Prudent"
    five_year_value = max(0, min(100, round(base * 0.92)))
    return {"label": label, "five_year_upside_score": five_year_value}


def slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "project"


def enrich_project_intelligence(project, config):
    geo = geo_profile(project.city, project.zone)
    band = price_band(project.prices.get("min"), config)
    project_slug = f"{slugify(project.name)}-{project.project_id[:8]}"
    price_evolution = price_evolution_summary(project.timeline, project.prices)
    roi = roi_hint(project)
    project.evidence["geo"] = geo
    project.evidence["price_band"] = band
    project.evidence["price_evolution"] = price_evolution
    project.evidence["roi"] = roi
    project.evidence["project_slug"] = project_slug
    project.evidence["infrastructure"] = {
        "sea_distance_km": geo.get("sea_distance_km"),
        "station_distance_km": geo.get("station_distance_km"),
        "highway_distance_km": geo.get("highway_distance_km"),
    }
    project.evidence["recommendation_narrative"] = recommendation_narrative(project, band)
    return project

