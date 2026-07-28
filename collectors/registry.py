from __future__ import annotations

import inspect

from collectors.ads.meta_ads import collect as collect_meta_ads
from collectors.google.google_search import collect as collect_google_search
from collectors.listings.portals import collect as collect_listings
from collectors.news.google_news import collect as collect_news
from collectors.promoters.websites import collect as collect_promoters
from collectors.social.watch import collect as collect_social
from collectors.urbanism.watch import collect as collect_urbanism
from core.health import WATCH_SIGNAL_TYPES


def collect_all(config: dict):
    signals = []
    stats = {}
    for collector in (
        collect_promoters,
        collect_google_search,
        collect_meta_ads,
        collect_news,
        collect_social,
        collect_urbanism,
        collect_listings,
    ):
        name = collector.__module__
        try:
            params = inspect.signature(collector).parameters
            batch = collector(config, signals) if len(params) >= 2 else collector(config)
            signals.extend(batch)
            real_primary = sum(
                1 for signal in batch if signal.is_primary and signal.signal_type not in WATCH_SIGNAL_TYPES
            )
            stats[name] = {"total": len(batch), "real_primary": real_primary, "error": None}
        except Exception as error:
            print(f"WARN collector failed: {collector.__name__} => {error}")
            stats[name] = {"total": 0, "real_primary": 0, "error": str(error)}
    return signals, stats
