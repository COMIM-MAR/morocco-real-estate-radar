from __future__ import annotations

from urllib.parse import quote

from core.models import SignalEvent


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for promoter in config.get("promoters", {}).get("tracked", []):
        query = f"{promoter} lancement immobilier Maroc"
        url = (
            "https://www.facebook.com/ads/library/?active_status=active"
            "&ad_type=all&country=MA&media_type=all&search_type=keyword_unordered&q="
            + quote(query)
        )
        signals.append(
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Meta Ad Library",
                signal_type="meta_watch",
                title=f"Meta Ads watch: {query}",
                url=url,
                text=query,
                is_primary=True,
                launch_weight=34,
                confidence_weight=38,
                metadata={"promoter_hint": promoter},
                reasons=["surveillance Meta Ad Library"],
            )
        )
    for query in config.get("sources", {}).get("meta_ad_library_searches", []):
        url = (
            "https://www.facebook.com/ads/library/?active_status=active"
            "&ad_type=all&country=MA&media_type=all&search_type=keyword_unordered&q="
            + quote(query)
        )
        signals.append(
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Meta Ad Library",
                signal_type="meta_watch",
                title=f"Meta Ads keyword watch: {query}",
                url=url,
                text=query,
                is_primary=True,
                launch_weight=26,
                confidence_weight=28,
                reasons=["mot-clé Meta Ads à vérifier"],
            )
        )
    return signals

