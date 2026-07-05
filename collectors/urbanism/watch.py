from __future__ import annotations

from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for source in config.get("sources", {}).get("urbanism", []):
        signals.append(
            SignalEvent(
                collector="urbanism.watch",
                channel="urbanism",
                source=source["name"],
                signal_type="urbanism_watch",
                title=f"Urbanism watch: {source['name']}",
                url=source["url"],
                text=source.get("description", source["name"]),
                is_primary=True,
                launch_weight=24,
                confidence_weight=18,
                reasons=["source urbanisme prioritaire"],
            )
        )
    return signals

