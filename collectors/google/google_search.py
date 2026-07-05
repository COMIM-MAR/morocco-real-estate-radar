from __future__ import annotations

from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from collectors.common import clean, domain, fetch, keyword_hits
from core.models import SignalEvent

GOOGLE_PROJECT_KEYWORDS = [
    "projet",
    "résidence",
    "residence",
    "lotissement",
    "pré-commercialisation",
    "pre-commercialisation",
    "lancement",
    "villa",
    "appartement",
    "programme",
]


def result_target(href: str) -> str | None:
    parsed = urlparse(href)
    if parsed.path == "/url":
        target = parse_qs(parsed.query).get("q", [None])[0]
        return target
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def extract_results(soup: BeautifulSoup) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        target = result_target(href)
        if not target or "google." in domain(target):
            continue
        title_node = anchor.find("h3")
        title = clean(title_node.get_text(" ")) if title_node else clean(anchor.get_text(" "))
        if len(title) < 12:
            continue
        if target in seen:
            continue
        seen.add(target)
        results.append((target, title))
    return results


def query_definition(item) -> dict:
    if isinstance(item, str):
        return {"query": item}
    return item


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for item in config.get("sources", {}).get("google_search_queries", []):
        query_config = query_definition(item)
        query = query_config["query"]
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&hl=fr"
        try:
            soup, _ = fetch(search_url)
            results = extract_results(soup)
        except Exception as error:
            print(f"WARN google discovery failed: {query} => {error}")
            results = []
        if not results:
            signals.append(
                SignalEvent(
                    collector="google.search",
                    channel="google_discovery",
                    source="Google Search",
                    signal_type="search_watch",
                    title=f"Google discovery watch: {query}",
                    url=search_url,
                    text=query,
                    is_primary=True,
                    launch_weight=12,
                    confidence_weight=14,
                    reasons=["fallback Google watch query"],
                )
            )
            continue
        for target_url, title in results[: query_config.get("max_results", 8)]:
            combined_text = f"{query} {title} {target_url}"
            hits = keyword_hits(combined_text, GOOGLE_PROJECT_KEYWORDS)
            launch_weight = 14 + min(len(hits) * 4, 16)
            confidence_weight = 18 + min(len(hits) * 3, 15)
            if query_config.get("preferred_domain") and domain(target_url) == domain(query_config["preferred_domain"]):
                confidence_weight += 12
            signals.append(
                SignalEvent(
                    collector="google.search",
                    channel="google_discovery",
                    source="Google Search",
                    signal_type="search_result",
                    title=title,
                    url=target_url,
                    text=combined_text,
                    is_primary=True,
                    launch_weight=launch_weight,
                    confidence_weight=confidence_weight,
                    metadata={
                        "query": query,
                        "preferred_domain": query_config.get("preferred_domain"),
                    },
                    reasons=["résultat Google détecté"] + [f"mot-clé Google: {hit}" for hit in hits[:3]],
                )
            )
    return signals
