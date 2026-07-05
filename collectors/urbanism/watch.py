from __future__ import annotations

from urllib.parse import urljoin

from collectors.common import clean, fetch, keyword_hits
from core.models import SignalEvent

URBANISM_KEYWORDS = [
    "permis",
    "lotissement",
    "plan d'aménagement",
    "plan d amenagement",
    "aménagement",
    "amenagement",
    "enquête publique",
    "enquete publique",
    "autorisation",
    "appel à manifestation",
    "appel d'offres",
    "projet",
    "résidence",
    "residence",
]


def source_keywords(source: dict) -> list[str]:
    return source.get("keywords", URBANISM_KEYWORDS)


def extract_candidate_pages(source: dict) -> list[tuple[str, str, list[str]]]:
    soup, base_text = fetch(source["url"])
    keywords = source_keywords(source)
    candidates: list[tuple[str, str, list[str]]] = []
    base_hits = keyword_hits(f"{source.get('description', '')} {base_text}", keywords)
    if base_hits:
        candidates.append((source["url"], clean(source.get("description", source["name"])), base_hits))
    seen: set[str] = {source["url"]}
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source["url"], anchor["href"])
        if url in seen:
            continue
        title = clean(anchor.get_text(" ")) or clean(anchor.get("title"))
        if len(title) < 8:
            continue
        seen.add(url)
        link_text = f"{title} {url}"
        hits = keyword_hits(link_text, keywords)
        if not hits:
            continue
        candidates.append((url, title, hits))
    return candidates


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for source in config.get("sources", {}).get("urbanism", []):
        try:
            candidates = extract_candidate_pages(source)
        except Exception as error:
            print(f"WARN urbanism source failed: {source['name']} {source['url']} => {error}")
            candidates = []
        if not candidates:
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
                    launch_weight=18,
                    confidence_weight=14,
                    reasons=["fallback urbanism watch"],
                )
            )
            continue
        for url, title, hits in candidates[: source.get("max_results", 12)]:
            signals.append(
                SignalEvent(
                    collector="urbanism.watch",
                    channel="urbanism",
                    source=source["name"],
                    signal_type="urbanism_page",
                    title=title,
                    url=url,
                    text=f"{source.get('description', '')} {title} {' '.join(hits)}",
                    is_primary=True,
                    launch_weight=18 + min(len(hits) * 5, 25),
                    confidence_weight=14 + min(len(hits) * 4, 20),
                    metadata={"keywords": hits},
                    reasons=["signal urbanisme détecté"] + [f"mot-clé urbanisme: {hit}" for hit in hits[:4]],
                )
            )
    return signals
