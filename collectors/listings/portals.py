from __future__ import annotations

import os
import re

from collectors.common import clean, collect_detail_pages, fetch
from core.availability import analyze_availability
from core.models import SignalEvent

LISTING_SOURCE_LIMIT = int(os.getenv("LISTING_SOURCE_LIMIT", "4"))

LISTING_DATE_PATTERN = re.compile(
    r"(?:publi\w*|actualis\w*|mis\s+(?:à|a)\s+jour)\s+(?:le\s+)?"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|il y a \d+\s*(?:jours|jour|semaines|semaine|mois|heures|heure))",
    re.I,
)


def detect_listing_date(text: str) -> str | None:
    match = LISTING_DATE_PATTERN.search(text or "")
    if not match:
        return None
    return clean(match.group(0))


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for source in config.get("sources", {}).get("listings", [])[:LISTING_SOURCE_LIMIT]:
        try:
            links = collect_detail_pages(source["url"])
        except Exception as error:
            print(f"WARN listing source failed: {source['name']} {source['url']} => {error}")
            continue
        for url, link_title in links:
            try:
                _, full_text = fetch(url)
            except Exception:
                full_text = link_title
            text = clean(f"{link_title} {full_text}")
            if len(text) < 30:
                continue
            availability = analyze_availability(text)
            listing_date = detect_listing_date(text)
            launch_weight = 4
            confidence_weight = 8
            reasons = ["signal listing secondaire"]
            if availability["status"]:
                confidence_weight += 6
                reasons.append(f"disponibilité détectée: {availability['status']}")
            if availability["status"] == "limited":
                launch_weight += 10
                reasons.append("stock limité repéré sur portail")
            if availability["surface_m2"]["min"]:
                confidence_weight += 3
                reasons.append("surface détectée")
            if listing_date:
                reasons.append(f"date listing: {listing_date}")
            signals.append(
                SignalEvent(
                    collector="listings.portals",
                    channel="listing",
                    source=source["name"],
                    signal_type="listing_detail",
                    title=link_title or text[:180],
                    url=url,
                    text=text,
                    is_primary=False,
                    launch_weight=launch_weight,
                    confidence_weight=confidence_weight,
                    metadata={
                        "portal": source["name"],
                        "availability": availability,
                        "listing_date_hint": listing_date,
                    },
                    reasons=reasons,
                )
            )
    return signals
