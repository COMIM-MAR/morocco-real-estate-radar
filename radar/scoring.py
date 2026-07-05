from __future__ import annotations

import re
from .models import Opportunity


RENTAL_NEGATIVE = [
    "à louer", "a louer", "location", "louer", "mensuel", "par mois", "/mois",
    "meublé à louer", "meuble a louer"
]

SALE_REQUIRED = [
    "à vendre", "a vendre", "vente", "vendre", "appartement à vendre",
    "villa à vendre", "terrain à vendre", "lotissement", "projet", "commercialisation",
    "réservation", "reservation", "lancement"
]


def has_any(text: str, words: list[str]) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in words)


def normalize_price(raw: str, full_match: str) -> int | None:
    full = full_match.lower()
    raw = raw.strip().replace("\u202f", " ").replace("\xa0", " ")

    if "mdh" in full or "million" in full:
        raw = raw.replace(",", ".")
        try:
            return int(float(raw) * 1_000_000)
        except Exception:
            return None

    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    value = int(digits)
    if 100_000 <= value <= 30_000_000:
        return value

    return None


def extract_price(text: str) -> int | None:
    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)",
        r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)",
        r"(?:prix|à partir de|a partir de)\s*(?:de)?\s*(\d[\d\s.,]{4,})",
    ]

    for p in patterns:
        for m in re.finditer(p, text, re.I):
            price = normalize_price(m.group(1), m.group(0))
            if price:
                return price

    return None


def detect_city_zone(op: Opportunity, config: dict) -> tuple[str | None, str | None, int, list[str]]:
    # Important: do NOT use full page text for city detection because menus/footers contain all cities.
    source_text = f"{op.source} {op.title} {op.url}".lower()

    best_city = None
    best_zone = None
    best_weight = 0
    reasons = []

    for city_key, city in config["cities"].items():
        city_label = city["label"].lower()

        if city_key in source_text or city_label in source_text:
            best_city = city_key

        for group_name, group in city.get("zones", {}).items():
            for zone in group.get("names", []):
                z = zone.lower()
                if z in source_text:
                    weight = int(group.get("weight", 0))
                    if weight > best_weight:
                        best_city = city_key
                        best_zone = zone
                        best_weight = weight

    if best_city:
        reasons.append(f"ville retenue: {config['cities'][best_city]['label']}")
    if best_zone:
        reasons.append(f"zone retenue: {best_zone}")

    return best_city, best_zone, best_weight, reasons


def detect_asset(op: Opportunity, config: dict) -> tuple[str | None, int, list[str]]:
    # Use title first to avoid bad detection from page menus.
    title = op.title.lower()
    text = f"{op.title} {op.text}".lower()
    prefs = config["asset_preferences"]

    if re.search(r"\b(villa|villas)\b", title):
        return "villa", int(prefs["villa"]), ["type retenu: villa"]

    if re.search(r"\b(r\+4|r4|r\+5|r5|immeuble|terrain|lotissement|lot de terrain|lots de terrain)\b", title):
        return "land_r4_plus", int(prefs["land_r4_plus"]), ["type retenu: terrain R+4+"]

    if re.search(r"\b(penthouse)\b", title):
        return "penthouse", int(prefs["penthouse"]), ["type retenu: penthouse"]

    if re.search(r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b", title):
        return "apartment_3_bed", int(prefs["apartment_3_bed"]), ["type retenu: appartement 3 chambres"]

    if re.search(r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b", title):
        return "apartment_2_bed", int(prefs["apartment_2_bed"]), ["type retenu: appartement 2 chambres"]

    if re.search(r"\bstudio\b", title):
        return "studio", int(prefs["studio"]), ["type retenu: studio"]

    # fallback only after title
    if re.search(r"\b(villa|villas)\b", text):
        return "villa", int(prefs["villa"]), ["type retenu: villa"]

    if re.search(r"\b(r\+4|r4|r\+5|r5|immeuble|terrain|lotissement|lot de terrain|lots de terrain)\b", text):
        return "land_r4_plus", int(prefs["land_r4_plus"]), ["type retenu: terrain R+4+"]

    if re.search(r"\b(penthouse)\b", text):
        return "penthouse", int(prefs["penthouse"]), ["type retenu: penthouse"]

    if re.search(r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b", text):
        return "apartment_3_bed", int(prefs["apartment_3_bed"]), ["type retenu: appartement 3 chambres"]

    if re.search(r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b", text):
        return "apartment_2_bed", int(prefs["apartment_2_bed"]), ["type retenu: appartement 2 chambres"]

    if re.search(r"\bstudio\b", text):
        return "studio", int(prefs["studio"]), ["type retenu: studio"]

    if re.search(r"\b(appartement|appart)\b", title):
        return "apartment_unknown", 35, ["type retenu: appartement, chambres à confirmer"]

    return None, 0, ["type non confirmé"]


def score_opportunity(op: Opportunity, config: dict) -> Opportunity:
    full_text = f"{op.title} {op.text}".lower()
    title_text = op.title.lower()
    weights = config["scoring"]["weights"]

    reasons = []
    score = 0

    # Hard exclusion: rental ads
    if has_any(full_text, RENTAL_NEGATIVE):
        op.score = 0
        op.urgency = "rejected"
        op.reasons = ["exclu: annonce de location"]
        return op

    # Hard exclusion: not sale/project related
    if not has_any(full_text, SALE_REQUIRED):
        op.score = 0
        op.urgency = "rejected"
        op.reasons = ["exclu: pas assez de signal vente/projet"]
        return op

    city, zone, zone_weight, rz = detect_city_zone(op, config)
    op.city = city
    op.zone = zone
    reasons += rz

    if city:
        city_priority = int(config["cities"][city]["priority"])
        score += round(weights["city_priority"] * city_priority / 100)
    else:
        score -= 10
        reasons.append("ville non confirmée")

    if zone_weight:
        score += round(weights["zone"] * zone_weight / 100)

    asset, asset_weight, ra = detect_asset(op, config)
    op.asset_type = asset
    reasons += ra

    # Hard exclusion: no clear asset type
    if not asset:
        op.score = 0
        op.urgency = "rejected"
        op.reasons = reasons + ["exclu: type de bien non confirmé"]
        return op

    score += round(weights["asset_type"] * asset_weight / 100)

    early_hits = [k for k in config["keywords"]["early_signals"] if k.lower() in full_text]
    if early_hits:
        score += min(weights["early_signal"], 5 + 3 * len(early_hits))
        reasons.append("signal amont: " + ", ".join(early_hits[:4]))

    if has_any(full_text, config["keywords"]["sea"]):
        score += weights["sea_proximity"]
        reasons.append("bonus mer/plage")

    if has_any(full_text, config["keywords"]["infrastructure"]):
        score += weights["infrastructure"]
        reasons.append("bonus infrastructure")

    if any(w in full_text for w in ["rentabilité", "rendement", "airbnb", "booking"]):
        score += weights["yield_keywords"]
        reasons.append("signal locatif/investissement")

    price = extract_price(full_text)
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
            score -= 20
            reasons.append("prix au-dessus du budget max")
    else:
        # Not fatal for projects/VEFA, but lower confidence
        score -= 5
        reasons.append("prix non détecté")

    if has_any(full_text, config["keywords"]["negative"]):
        score -= 30
        reasons.append("signal négatif: vendu/épuisé/indisponible")

    op.score = max(0, min(100, int(score)))

    urgent = int(config["scoring"]["urgent_threshold"])
    trigger = int(config["scoring"]["trigger_threshold"])
    op.urgency = "urgent" if op.score >= urgent else "alert" if op.score >= trigger else "watch"
    op.reasons = reasons
    return op
