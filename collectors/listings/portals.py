from __future__ import annotations

import os

from collectors.common import clean, collect_detail_pages, fetch
from core.models import SignalEvent

LISTING_SOURCE_LIMIT = int(os.getenv("LISTING_SOURCE_LIMIT", "4"))


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
                    launch_weight=4,
                    confidence_weight=8,
                    metadata={"portal": source["name"]},
                    reasons=["signal listing secondaire"],
                )
            )
    return signals
