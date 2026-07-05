from __future__ import annotations

from urllib.parse import quote_plus

from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for query in config.get("sources", {}).get("google_search_queries", []):
        url = f"https://www.google.com/search?q={quote_plus(query)}&hl=fr"
        signals.append(
            SignalEvent(
                collector="google.search",
                channel="google_discovery",
                source="Google Search",
                signal_type="search_watch",
                title=f"Google discovery watch: {query}",
                url=url,
                text=query,
                is_primary=True,
                launch_weight=18,
                confidence_weight=22,
                reasons=["requête Google prioritaire"],
            )
        )
    return signals

