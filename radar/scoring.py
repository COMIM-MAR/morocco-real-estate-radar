from __future__ import annotations

import re
from .models import Opportunity

PRICE_PATTERNS = [
    r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)",
    r"(?:à partir de|a partir de|prix à partir de|prix)\s*(?:de)?\s*(\d[\d\s.,]{4,})",
    r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)",
]


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

        if city_hit and not best_city:
            best_city = city_key
            reasons.append(f"ville détectée: {city['label']}")

        for group_name, group in city.get("zones", {}).items():
            for zone in group.get("names", []):
                if zone.lower() in t:
                    if int(group.get("weight", 0)) >= best_zone_weight:
                        best_city = city_key
                        best_zone = zone
                        best_zone_weight = int(group.get("weight", 0))
                    reasons.append(f"zone détectée: {city['label']} / {zone} ({group_name})")

    return best_city, best_zone, best_zone_weight, reasons


def detect_asset(text: str, config: dict) -> tuple[str | None, int, list[str]]:
    t = text.lower()
    reasons = []
    prefs = config["asset_preferences"]

    if re.search(r"\b(villa|villas)\b", t):
        return "villa", int(prefs.get("villa", 0)), ["type détecté: villa"]

    if re.search(r"\b(r\+4|r4|r\+5|r5|immeuble|terrain|lotissement|lot de terrain|lots de terrain)\b", t):
        return "land_r4_plus", int(prefs.get("land_r4_plus", 0)), ["type détecté: land_r4_plus"]

    if re.search(r"\b(penthouse|duplex|terrasse)\b", t):
        return "penthouse", int(prefs.get("penthouse", 0)), ["type détecté: penthouse"]

    if re.search(r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b", t):
        return "apartment_3_bed", int(prefs.get("apartment_3_bed", 0)), ["type détecté: apartment_3_bed"]

    if re.search(r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b", t):
        return "apartment_2_bed", int(prefs.get("apartment_2_bed", 0)), ["type détecté: apartment_2_bed"]

    if re.search(r"\bstudio\b", t):
        return "studio", int(prefs.get("studio", 0)), ["type détecté: studio"]

    if re.search(r"\b(appartement|appart|résidence|residence)\b", t):
        return "apartment_unknown", 40, ["type détecté: appartement, nombre de chambres à confirmer"]

    return None, 0, reasons


def extract_price(text: str) -> int | None:
    t = text.lower().replace("\u202f", " ").replace("\xa0", " ")

    for pattern in PRICE_PATTERNS:
        m = re.search(pattern, t, re.I)
        if not m:
            continue

        raw = m.group(1).strip()

        if "mdh" in m.group(0) or "million" in m.group(0):
            raw = raw.replace(",", ".")
            try:
                return int(float(raw) * 1_000_000)
            except ValueError:
                continue

        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue

        value = int(digits)

        if 100_000 <= value <= 30_000_000:
            return value

    return None


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
