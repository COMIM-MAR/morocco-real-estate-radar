from __future__ import annotations

import re
from .models import Opportunity

PRICE_RE = re.compile(r"(?:(\d+[\s.,]?\d*)\s*(?:dh|dhs|mad|dirhams))", re.I)


def contains_any(text: str, words: list[str]) -> str | None:
    t = text.lower()
    for w in words:
        if w.lower() in t:
            return w
    return None


def detect_city_zone(text: str, config: dict) -> tuple[str | None, str | None, int, list[str]]:
    t = text.lower()
    best_city = None
    best_zone = None
    best_zone_weight = 0
    reasons = []
    for city_key, city in config["cities"].items():
        city_hit = city_key in t or city["label"].lower() in t
        for group_name, group in city.get("zones", {}).items():
            for zone in group.get("names", []):
                if zone.lower() in t:
                    best_city = city_key
                    best_zone = zone
                    best_zone_weight = max(best_zone_weight, int(group.get("weight", 0)))
                    reasons.append(f"zone détectée: {city['label']} / {zone} ({group_name})")
        if city_hit and not best_city:
            best_city = city_key
            reasons.append(f"ville détectée: {city['label']}")
    return best_city, best_zone, best_zone_weight, reasons


def detect_asset(text: str, config: dict) -> tuple[str | None, int, list[str]]:
    reasons = []
    prefs = config["asset_preferences"]
    for asset, words in config["keywords"]["asset_types"].items():
        if contains_any(text, words):
            reasons.append(f"type détecté: {asset}")
            return asset, int(prefs.get(asset, 0)), reasons
    return None, 0, reasons


def extract_price(text: str) -> int | None:
    # Lightweight extraction. Avoid making decisions if price text is ambiguous.
    m = PRICE_RE.search(text)
    if not m:
        return None
    raw = re.sub(r"\D", "", m.group(1))
    if not raw:
        return None
    value = int(raw)
    if value < 10000:
        return None
    return value


def score_opportunity(op: Opportunity, config: dict) -> Opportunity:
    text = f"{op.title} {op.text}".lower()
    weights = config["scoring"]["weights"]
    score = 0
    reasons: list[str] = []

    city, zone, zone_weight, rz = detect_city_zone(text, config)
    op.city, op.zone = city, zone
    reasons += rz
    if city:
        city_priority = int(config["cities"][city]["priority"])
        score += round(weights["city_priority"] * city_priority / 100)
    if zone_weight:
        score += round(weights["zone"] * zone_weight / 100)

    asset, asset_weight, ra = detect_asset(text, config)
    op.asset_type = asset
    reasons += ra
    if asset_weight:
        score += round(weights["asset_type"] * asset_weight / 100)

    early_hits = [k for k in config["keywords"]["early_signals"] if k.lower() in text]
    if early_hits:
        score += min(weights["early_signal"], 5 + 3 * len(early_hits))
        reasons.append("signal amont: " + ", ".join(early_hits[:5]))

    if contains_any(text, config["keywords"]["sea"]):
        score += weights["sea_proximity"]
        reasons.append("bonus mer/plage")

    if contains_any(text, config["keywords"]["infrastructure"]):
        score += weights["infrastructure"]
        reasons.append("bonus infrastructure")

    if any(w in text for w in ["rentabilité", "rendement", "location", "airbnb", "booking"]):
        score += weights["yield_keywords"]
        reasons.append("signal locatif")

    if any(w in text for w in ["promoteur", "groupe", "résidence fermée", "standing", "haut standing"]):
        score += weights["promoter_signal"]
        reasons.append("signal promoteur/standing")

    price = extract_price(text)
    op.price_mad = price
    max_budget = int(config["profile"]["max_budget"])
    cash_ready = int(config["profile"]["cash_ready"])
    if price:
        if price <= cash_ready:
            score += weights["budget_fit"]
            reasons.append("prix compatible cash disponible")
        elif price <= max_budget:
            score += round(weights["budget_fit"] * 0.7)
            reasons.append("prix compatible budget max/VEFA")
        else:
            score -= 15
            reasons.append("prix au-dessus du budget max")

    if contains_any(text, config["keywords"]["negative"]):
        score -= 25
        reasons.append("signal négatif: vendu/épuisé/indisponible")

    op.score = max(0, min(100, int(score)))
    urgent = int(config["scoring"]["urgent_threshold"])
    trigger = int(config["scoring"]["trigger_threshold"])
    op.urgency = "urgent" if op.score >= urgent else "alert" if op.score >= trigger else "watch"
    op.reasons = reasons
    return op
