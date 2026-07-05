from __future__ import annotations
import re
from .models import Signal


def has_any(text: str, words: list[str]) -> bool:
    t = text.lower()
    return any(str(w).lower() in t for w in words)


def extract_price(text: str) -> int | None:
    t = text.lower().replace("\u202f", " ").replace("\xa0", " ")
    patterns = [
        r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)",
        r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)",
        r"(?:prix|à partir de|a partir de)\s*(?:de)?\s*(\d[\d\s.,]{4,})",
    ]
    for p in patterns:
        for m in re.finditer(p, t, re.I):
            raw = m.group(1).strip()
            if "mdh" in m.group(0).lower() or "million" in m.group(0).lower():
                try:
                    return int(float(raw.replace(",", ".")) * 1_000_000)
                except Exception:
                    continue
            digits = re.sub(r"\D", "", raw)
            if digits:
                val = int(digits)
                if 100_000 <= val <= 30_000_000:
                    return val
    return None


def detect_city_zone(sig: Signal, config: dict) -> tuple[str | None, str | None, int, list[str]]:
    locator = f"{sig.source} {sig.title} {sig.url}".lower()
    best_city, best_zone, best_weight = None, None, 0
    for city_key, city in config["cities"].items():
        aliases = [city_key, city["label"], *city.get("aliases", [])]
        if any(a.lower() in locator for a in aliases):
            best_city = city_key
        for group in city.get("zones", {}).values():
            for zone in group.get("names", []):
                if zone.lower() in locator:
                    weight = int(group.get("weight", 0))
                    if weight >= best_weight:
                        best_city, best_zone, best_weight = city_key, zone, weight
    reasons = []
    if best_city:
        reasons.append(f"ville retenue: {config['cities'][best_city]['label']}")
    if best_zone:
        reasons.append(f"zone retenue: {best_zone}")
    return best_city, best_zone, best_weight, reasons


def detect_asset(sig: Signal, config: dict) -> tuple[str | None, int, list[str]]:
    title = sig.title.lower()
    text = f"{sig.title} {sig.text}".lower()
    prefs = config["asset_preferences"]
    rules = [
        ("villa", r"\b(villa|villas)\b", "villa"),
        ("land_r4_plus", r"\b(r\+4|r4|r\+5|r5|immeuble|terrain|lotissement|lot de terrain|lots de terrain)\b", "terrain R+4+"),
        ("penthouse", r"\b(penthouse)\b", "penthouse"),
        ("apartment_3_bed", r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b", "appartement 3 chambres"),
        ("apartment_2_bed", r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b", "appartement 2 chambres"),
        ("studio", r"\bstudio\b", "studio"),
    ]
    for key, pat, label in rules:
        if re.search(pat, title):
            return key, int(prefs.get(key, 0)), [f"type retenu: {label}"]
    for key, pat, label in rules:
        if re.search(pat, text):
            return key, int(prefs.get(key, 0)), [f"type retenu: {label}"]
    if re.search(r"\b(appartement|appart|résidence|residence)\b", title):
        return "apartment_unknown", int(prefs.get("apartment_unknown", 35)), ["type retenu: appartement, chambres à confirmer"]
    return None, 0, ["type non confirmé"]


def score_signal(sig: Signal, config: dict) -> Signal:
    text = f"{sig.title} {sig.text}".lower()
    reasons = []

    if has_any(text, config["keywords"]["rental_negative"]):
        sig.status = "rejected"
        sig.reasons = ["exclu: annonce de location"]
        return sig

    if sig.channel == "listing" and not has_any(text, config["keywords"]["sale"]):
        sig.status = "rejected"
        sig.reasons = ["exclu: listing sans signal de vente"]
        return sig

    city, zone, zone_weight, rz = detect_city_zone(sig, config)
    sig.city, sig.zone = city, zone
    reasons += rz

    asset, asset_weight, ra = detect_asset(sig, config)
    sig.asset_type = asset
    reasons += ra

    source_score = int(config["source_weights"].get(sig.channel, 50))
    confidence = min(100, source_score)
    opportunity = 0

    if city:
        opportunity += round(18 * int(config["cities"][city]["priority"]) / 100)
    else:
        opportunity -= 8
        reasons.append("ville non confirmée")

    if zone_weight:
        opportunity += round(18 * zone_weight / 100)

    if asset:
        opportunity += round(22 * asset_weight / 100)
    elif sig.channel == "listing":
        sig.status = "rejected"
        sig.reasons = reasons + ["exclu: type non confirmé"]
        return sig

    launch_hits = [k for k in config["keywords"]["launch"] if k.lower() in text]
    if launch_hits:
        confidence += 12
        opportunity += min(18, 6 + 3 * len(launch_hits))
        reasons.append("signal lancement: " + ", ".join(launch_hits[:4]))

    if has_any(text, config["keywords"]["sea"]):
        opportunity += 8
        reasons.append("bonus mer/plage")
    if has_any(text, config["keywords"]["infrastructure"]):
        opportunity += 8
        reasons.append("bonus infrastructure")
    if has_any(text, config["keywords"]["negative"]):
        opportunity -= 30
        reasons.append("signal négatif")

    price = extract_price(text)
    sig.price_mad = price
    if price:
        if price <= int(config["profile"]["cash_ready"]):
            opportunity += 10
            reasons.append("prix compatible cash")
        elif price <= int(config["profile"]["max_budget"]):
            opportunity += 7
            reasons.append("prix compatible budget max/VEFA")
        else:
            opportunity -= 18
            reasons.append("prix au-dessus budget")
    elif sig.channel == "listing":
        opportunity -= 6
        reasons.append("prix non détecté")

    sig.confidence_score = max(0, min(100, int(confidence)))
    sig.opportunity_score = max(0, min(100, int(opportunity)))
    sig.total_score = round(sig.confidence_score * 0.45 + sig.opportunity_score * 0.55)
    sig.status = "urgent" if sig.total_score >= int(config["alerts"]["immediate_threshold"]) else "digest" if sig.total_score >= int(config["alerts"]["digest_threshold"]) else "watch"
    sig.reasons = reasons
    return sig
