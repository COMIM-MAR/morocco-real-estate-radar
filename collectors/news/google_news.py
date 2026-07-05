from __future__ import annotations

from urllib.parse import quote_plus

from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for query in config.get("sources", {}).get("news_queries", []):
        url = f"https://news.google.com/search?q={quote_plus(query)}&hl=fr&gl=MA&ceid=MA:fr"
        signals.append(
            SignalEvent(
                collector="news.google_news",
                channel="news",
                source="Google News",
                signal_type="news_watch",
                title=f"Google News watch: {query}",
                url=url,
                text=query,
                is_primary=True,
                launch_weight=10,
                confidence_weight=15,
                reasons=["surveillance presse / Google News"],
            )
        )
    return signals

