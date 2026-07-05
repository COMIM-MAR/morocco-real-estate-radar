from __future__ import annotations

from collectors.common import clean, collect_detail_pages, fetch
from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for source in config.get("sources", {}).get("promoters", []):
        try:
            links = collect_detail_pages(source["url"])
        except Exception as error:
            print(f"WARN promoter source failed: {source['name']} {source['url']} => {error}")
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
                    collector="promoters.websites",
                    channel="project_discovery",
                    source=source["name"],
                    signal_type="promoter_page",
                    title=link_title or text[:180],
                    url=url,
                    text=text,
                    is_primary=True,
                    launch_weight=30,
                    confidence_weight=30,
                    metadata={"promoter_hint": source["name"]},
                    reasons=["nouvelle page promoteur"],
                )
            )
    return signals

