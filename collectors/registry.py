from __future__ import annotations

import inspect

from collectors.ads.meta_ads import collect as collect_meta_ads
from collectors.google.google_search import collect as collect_google_search
from collectors.listings.portals import collect as collect_listings
from collectors.news.google_news import collect as collect_news
from collectors.promoters.websites import collect as collect_promoters
from collectors.social.watch import collect as collect_social
from collectors.urbanism.watch import collect as collect_urbanism


def collect_all(config: dict):
    signals = []
    for collector in (
        collect_promoters,
        collect_google_search,
        collect_meta_ads,
        collect_news,
        collect_social,
        collect_urbanism,
        collect_listings,
    ):
        try:
            params = inspect.signature(collector).parameters
            if len(params) >= 2:
                signals.extend(collector(config, signals))
            else:
                signals.extend(collector(config))
        except Exception as error:
            print(f"WARN collector failed: {collector.__name__} => {error}")
    return signals
