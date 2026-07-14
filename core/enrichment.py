from __future__ import annotations

import re
from urllib.parse import urlparse


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

ASSET_LABELS = {
    "villa": "Villa",
    "land_r4_plus": "Terrain / Immeuble R+4+",
    "penthouse": "Penthouse",
    "apartment_3_bed": "Appartement 3 chambres",
    "apartment_2_bed": "Appartement 2 chambres",
    "studio": "Studio",
    "apartment_unknown": "Appartement",
}

SOURCE_KIND_LABELS = {
    "official_site": "Site promoteur",
    "meta_ads": "Publicité Meta",
    "google_search": "Résultat Google",
    "google_news": "Article / Google News",
    "social": "Réseau social",
    "listing": "Portail immobilier",
    "urbanism": "Document urbanisme",
    "other": "Source diverse",
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


def asset_label(asset_type: str | None) -> str:
    return ASSET_LABELS.get(asset_type or "", "Type à confirmer")


def classify_source_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "news.google.com" in host:
        return "google_news"
    if "facebook.com" in host and "/ads/library/" in url:
        return "meta_ads"
    if "google.com" in host and "/search" in url:
        return "google_search"
    if any(token in host for token in ["instagram.com", "facebook.com", "linkedin.com", "youtube.com", "tiktok.com"]):
        return "social"
    if any(token in host for token in ["mubawab", "avito", "agenz", "sarouty", "properstar"]):
        return "listing"
    if any(token in host for token in ["autanger", "auc.ma", "agenceurbaine", "urban"]) or url.endswith(".pdf"):
        return "urbanism"
    if host:
        return "official_site"
    return "other"


def classify_signal(signal) -> str:
    channel = getattr(signal, "channel", None)
    if channel == "advertising":
        return "meta_ads"
    if channel == "google_discovery":
        return "google_search"
    if channel == "news":
        return "google_news"
    if channel == "social":
        return "social"
    if channel == "listing":
        return "listing"
    if channel == "urbanism":
        return "urbanism"
    if channel == "project_discovery":
        return "official_site"
    return classify_source_url(getattr(signal, "url", ""))


def text_contains(haystack: str | None, needle: str | None) -> bool:
    if not haystack or not needle:
        return False
    return needle.lower() in haystack.lower()


def signal_relevant_to_project(signal, project) -> bool:
    promoter_sensitive_channels = {"advertising", "project_discovery", "google_discovery", "social", "news"}
    promoter_ok = True
    if getattr(project, "promoter", None):
        if getattr(signal, "channel", None) in promoter_sensitive_channels:
            promoter_ok = (
                getattr(signal, "promoter_hint", None) == project.promoter
                or text_contains(getattr(signal, "title", ""), project.promoter)
                or text_contains(getattr(signal, "text", ""), project.promoter)
                or text_contains(getattr(signal, "url", ""), project.promoter)
                or text_contains(getattr(signal, "source", ""), project.promoter)
            )
    city_ok = True
    if getattr(project, "city", None):
        city_ok = (
            getattr(signal, "city_hint", None) == project.city
            or text_contains(getattr(signal, "title", ""), project.city)
            or text_contains(getattr(signal, "text", ""), project.city)
            or text_contains(getattr(signal, "url", ""), project.city)
        )
    zone_ok = True
    if getattr(project, "zone", None):
        zone_ok = getattr(signal, "zone_hint", None) in {None, project.zone}
    return promoter_ok and city_ok and zone_ok


def source_description(kind: str) -> str:
    descriptions = {
        "official_site": "Page officielle du promoteur ou du projet.",
        "meta_ads": "Publicité Facebook / Instagram repérée via Meta Ad Library.",
        "google_search": "Résultat remonté par une requête de veille Google.",
        "google_news": "Résultat presse ou Google News surveillé.",
        "social": "Lien réseau social surveillé comme indice complémentaire.",
        "listing": "Portail immobilier servant surtout à confirmer prix et disponibilité.",
        "urbanism": "Source urbanisme, permis, planification ou document public.",
        "other": "Source non classée automatiquement.",
    }
    return descriptions.get(kind, "Source non classée automatiquement.")


def source_label(url: str, kind: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if kind == "meta_ads":
        return "Meta Ad Library"
    if kind == "google_search":
        return "Google Search"
    if kind == "google_news":
        return "Google News"
    if kind == "social":
        return host or "Réseau social"
    if kind == "listing":
        return host or "Portail immobilier"
    if kind == "urbanism":
        return host or "Urbanisme"
    return host or SOURCE_KIND_LABELS.get(kind, "Source")


def build_source_catalog(project) -> list[dict]:
    entries = []
    seen = set()
    for signal in getattr(project, "signals", []) or []:
        if not signal_relevant_to_project(signal, project):
            continue
        kind = classify_signal(signal)
        url = signal.url
        key = (kind, url)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "kind": kind,
                "kind_label": SOURCE_KIND_LABELS.get(kind, "Source"),
                "label": signal.title or source_label(url, kind),
                "description": source_description(kind),
                "url": url,
                "source": signal.source,
                "signal_type": signal.signal_type,
                "proof_level": "direct" if signal.signal_type in {"search_result", "urbanism_page", "promoter_page", "project_page", "listing_detail", "listing_page", "meta_ad"} else "watch",
            }
        )
    if entries:
        return entries
    for url in project.source_urls:
        kind = classify_source_url(url)
        key = (kind, url)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "kind": kind,
                "kind_label": SOURCE_KIND_LABELS.get(kind, "Source"),
                "label": source_label(url, kind),
                "description": source_description(kind),
                "url": url,
            }
        )
    return entries


def ai_analysis(project, band: str) -> dict:
    strengths = []
    if project.evidence.get("confirmation_count", 0) >= 2:
        strengths.append("Le projet est confirmé par plusieurs canaux indépendants.")
    if project.confidence_score >= 85:
        strengths.append("Le score de confiance est élevé, donc le signal paraît crédible.")
    if project.investment_score >= 70:
        strengths.append("Le potentiel investissement ressort comme intéressant selon le profil configuré.")
    risks = []
    if not project.prices.get("min"):
        risks.append("Le prix public n'est pas encore confirmé.")
    if band == "above_budget":
        risks.append("Le projet semble au-dessus du budget cible configuré.")
    if project.evidence.get("listing_signal_count", 0) == 0:
        risks.append("Aucune disponibilité publique confirmée sur portail pour l'instant.")
    next_steps = [
        "Vérifier le site officiel et les pages sociales du promoteur.",
        "Confirmer les disponibilités et le ticket d'entrée réel.",
        "Surveiller si de nouveaux documents urbanisme ou listings apparaissent.",
    ]
    summary = recommendation_narrative(project, band)
    return {
        "summary": summary,
        "strengths": strengths[:3],
        "risks": risks[:3],
        "next_steps": next_steps,
    }


def availability_summary(project) -> dict:
    listing_count = project.evidence.get("listing_signal_count", 0)
    if listing_count > 0:
        public_status = f"{listing_count} signal(s) listing détecté(s), disponibilités à confirmer."
    else:
        public_status = "Aucune disponibilité publique détectée pour le moment."
    return {
        "asset_label": asset_label(project.asset_type),
        "public_status": public_status,
        "price_min": project.prices.get("min"),
        "price_max": project.prices.get("max"),
    }


def enrich_project_intelligence(project, config):
    geo = geo_profile(project.city, project.zone)
    band = price_band(project.prices.get("min"), config)
    project_slug = f"{slugify(project.name)}-{project.project_id[:8]}"
    price_evolution = price_evolution_summary(project.timeline, project.prices)
    roi = roi_hint(project)
    source_catalog = build_source_catalog(project)
    practical = availability_summary(project)
    analysis = ai_analysis(project, band)
    image_urls: list[str] = []
    video_urls: list[str] = []
    seen_images: set[str] = set()
    seen_videos: set[str] = set()
    for signal in project.signals:
        metadata = signal.metadata or {}
        for url in metadata.get("image_urls") or []:
            if url and url not in seen_images:
                seen_images.add(url)
                image_urls.append(url)
        for url in metadata.get("video_urls") or []:
            if url and url not in seen_videos:
                seen_videos.add(url)
                video_urls.append(url)
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
    project.evidence["source_catalog"] = source_catalog
    project.evidence["practical"] = practical
    project.evidence["ai_analysis"] = analysis
    project.evidence["confirmation_details"] = project.evidence.get("confirmation_details", [])
    project.evidence["official_links"] = [item for item in source_catalog if item["kind"] == "official_site"]
    project.evidence["social_links"] = [item for item in source_catalog if item["kind"] in {"social", "meta_ads"}]
    project.evidence["listing_links"] = [item for item in source_catalog if item["kind"] == "listing"]
    project.evidence["news_links"] = [item for item in source_catalog if item["kind"] == "google_news"]
    project.evidence["urbanism_links"] = [item for item in source_catalog if item["kind"] == "urbanism"]
    project.evidence["images"] = image_urls
    project.evidence["videos"] = video_urls
    return project
