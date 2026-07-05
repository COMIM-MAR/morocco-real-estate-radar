from __future__ import annotations

from urllib.parse import quote_plus

from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for query in config.get("sources", {}).get("social_queries", []):
        signals.append(
            SignalEvent(
                collector="social.watch",
                channel="social",
                source="Social watch",
                signal_type="social_watch",
                title=f"Social watch: {query}",
                url=f"https://www.google.com/search?q={quote_plus(query)}",
                text=query,
                is_primary=False,
                launch_weight=8,
                confidence_weight=12,
                reasons=["surveillance sociale complémentaire"],
            )
        )
    return signals

