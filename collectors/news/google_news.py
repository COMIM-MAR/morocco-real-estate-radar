from __future__ import annotations

from urllib.parse import quote_plus

import feedparser

from collectors.common import clean, keyword_hits
from core.models import SignalEvent

NEWS_PROJECT_KEYWORDS = [
    "projet immobilier",
    "programme immobilier",
    "résidence",
    "residence",
    "lotissement",
    "pré-commercialisation",
    "pre-commercialisation",
    "lancement",
    "livraison",
    "permis de construire",
    "villa",
    "appartement",
]


def query_definition(item) -> dict:
    if isinstance(item, str):
        return {"query": item}
    return item


def feed_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=fr-MA&gl=MA&ceid=MA:fr"


def parse_entries(query: str) -> list[dict]:
    parsed = feedparser.parse(feed_url(query))
    entries: list[dict] = []
    for entry in parsed.entries:
        title = clean(getattr(entry, "title", ""))
        link = getattr(entry, "link", "")
        if not title or not link:
            continue
        summary = clean(getattr(entry, "summary", ""))
        source_field = entry.get("source")
        source = clean(source_field.get("title", "")) if isinstance(source_field, dict) else ""
        entries.append(
            {
                "title": title,
                "url": link,
                "summary": summary,
                "source": source,
                "published": getattr(entry, "published", ""),
            }
        )
    return entries


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for item in config.get("sources", {}).get("news_queries", []):
        query_config = query_definition(item)
        query = query_config["query"]
        try:
            entries = parse_entries(query)
        except Exception as error:
            print(f"WARN google news collector failed: {query} => {error}")
            entries = []
        if not entries:
            signals.append(
                SignalEvent(
                    collector="news.google_news",
                    channel="news",
                    source="Google News",
                    signal_type="news_watch",
                    title=f"Google News watch: {query}",
                    url=feed_url(query),
                    text=query,
                    is_primary=True,
                    launch_weight=10,
                    confidence_weight=15,
                    reasons=["surveillance presse / Google News"],
                )
            )
            continue
        for entry in entries[: query_config.get("max_results", 8)]:
            combined_text = f"{query} {entry['title']} {entry['summary']}"
            hits = keyword_hits(combined_text, NEWS_PROJECT_KEYWORDS)
            launch_weight = 12 + min(len(hits) * 4, 16)
            confidence_weight = 16 + min(len(hits) * 3, 18)
            signals.append(
                SignalEvent(
                    collector="news.google_news",
                    channel="news",
                    source=entry["source"] or "Google News",
                    signal_type="news_result",
                    title=entry["title"],
                    url=entry["url"],
                    text=combined_text,
                    is_primary=True,
                    launch_weight=launch_weight,
                    confidence_weight=confidence_weight,
                    metadata={"query": query, "published": entry["published"]},
                    reasons=["article presse détecté"] + [f"mot-clé presse: {hit}" for hit in hits[:3]],
                )
            )
    return signals
