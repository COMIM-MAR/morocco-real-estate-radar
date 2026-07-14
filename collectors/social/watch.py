from __future__ import annotations

import os
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from collectors.common import clean, domain, fetch, keyword_hits
from core.models import SignalEvent

SOCIAL_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
]
SOCIAL_KEYWORDS = [
    "immobilier",
    "résidence",
    "residence",
    "appartement",
    "villa",
    "lotissement",
    "lancement",
    "pré-commercialisation",
    "pre-commercialisation",
    "ouverture",
    "commercialisation",
]
SOCIAL_QUERY_LIMIT = int(os.getenv("SOCIAL_QUERY_LIMIT", "18"))
SOCIAL_RESULT_LIMIT = int(os.getenv("SOCIAL_RESULT_LIMIT", "5"))


def search_url(query: str) -> str:
    return f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"


def platform_queries(base: str) -> list[str]:
    return [f"site:{platform} {base}" for platform in SOCIAL_DOMAINS[:3]]


def query_contexts(config: dict) -> list[dict]:
    contexts: list[dict] = []
    seen: set[str] = set()
    cities = [cfg["label"] for cfg in config.get("cities", {}).values()]
    city_zones: list[tuple[str, str]] = []
    for cfg in config.get("cities", {}).values():
        city = cfg["label"]
        for zone in cfg.get("zones", [])[:3]:
            city_zones.append((city, zone))

    for query in config.get("sources", {}).get("social_queries", []):
        contexts.append({"query": query, "promoter": None, "city": None, "zone": None})

    for city in cities[:5]:
        for query in platform_queries(f'projet immobilier "{city}"'):
            contexts.append({"query": query, "promoter": None, "city": city, "zone": None})
        for query in platform_queries(f'résidence neuve "{city}"'):
            contexts.append({"query": query, "promoter": None, "city": city, "zone": None})

    for promoter in config.get("promoters", {}).get("tracked", []):
        for query in platform_queries(f'"{promoter}" immobilier Maroc'):
            contexts.append({"query": query, "promoter": promoter, "city": None, "zone": None})
        for city in cities[:4]:
            for query in platform_queries(f'"{promoter}" "{city}" immobilier'):
                contexts.append({"query": query, "promoter": promoter, "city": city, "zone": None})

    for city, zone in city_zones[:10]:
        for query in platform_queries(f'"{zone}" immobilier "{city}"'):
            contexts.append({"query": query, "promoter": None, "city": city, "zone": zone})

    unique_contexts: list[dict] = []
    for context in contexts:
        key = context["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique_contexts.append(context)
    return unique_contexts[:SOCIAL_QUERY_LIMIT]


def social_domain(target_url: str) -> bool:
    host = domain(target_url)
    return any(platform in host for platform in SOCIAL_DOMAINS)


def result_target(href: str) -> str | None:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        return target
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def extract_results(soup: BeautifulSoup) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a.result__a, a[data-testid='result-title-a']"):
        href = anchor.get("href", "")
        target = result_target(href)
        if not target:
            continue
        title = clean(anchor.get_text(" "))
        if len(title) < 6:
            continue
        if target in seen:
            continue
        seen.add(target)
        results.append((target, title))
    return results


def result_relevance(text: str, context: dict) -> int:
    lowered = text.lower()
    score = 0
    hits = keyword_hits(text, SOCIAL_KEYWORDS)
    score += min(len(hits) * 6, 24)
    promoter = context.get("promoter")
    city = context.get("city")
    zone = context.get("zone")
    if promoter and promoter.lower() in lowered:
        score += 28
    if city and city.lower() in lowered:
        score += 18
    if zone and zone.lower() in lowered:
        score += 14
    if any(token in lowered for token in ["post", "publication", "reel", "vidéo", "video"]):
        score += 4
    return score


def social_signal(target_url: str, title: str, context: dict) -> SignalEvent:
    text = clean(f"{context['query']} {title} {target_url}")
    score = result_relevance(text, context)
    reasons = ["résultat social détecté via Google"] + [f"mot-clé social: {hit}" for hit in keyword_hits(text, SOCIAL_KEYWORDS)[:3]]
    if context.get("promoter"):
        reasons.append(f"promoteur: {context['promoter']}")
    if context.get("city"):
        reasons.append(f"ville: {context['city']}")
    if context.get("zone"):
        reasons.append(f"zone: {context['zone']}")
    return SignalEvent(
        collector="social.watch",
        channel="social",
        source=domain(target_url) or "Social",
        signal_type="social_post",
        title=title,
        url=target_url,
        text=text,
        is_primary=True,
        launch_weight=16 + min(score // 3, 16),
        confidence_weight=18 + min(score // 2, 20),
        metadata={
            "query": context["query"],
            "promoter_hint": context.get("promoter"),
            "city_hint": context.get("city"),
            "zone_hint": context.get("zone"),
        },
        reasons=reasons,
    )


def watch_signal(context: dict) -> SignalEvent:
    return SignalEvent(
        collector="social.watch",
        channel="social",
        source="Social watch",
        signal_type="social_watch",
        title=f"Social watch: {context['query']}",
        url=search_url(context["query"]),
        text=context["query"],
        is_primary=False,
        launch_weight=8,
        confidence_weight=12,
        metadata={
            "promoter_hint": context.get("promoter"),
            "city_hint": context.get("city"),
            "zone_hint": context.get("zone"),
            "query": context["query"],
        },
        reasons=["surveillance sociale complémentaire"],
    )


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for context in query_contexts(config):
        url = search_url(context["query"])
        try:
            soup, _ = fetch(url)
            results = extract_results(soup)
        except Exception as error:
            print(f"WARN social discovery failed: {context['query']} => {error}")
            results = []
        matched = 0
        for target_url, title in results:
            if not social_domain(target_url):
                continue
            text = clean(f"{context['query']} {title} {target_url}")
            if result_relevance(text, context) < 18:
                continue
            signals.append(social_signal(target_url, title, context))
            matched += 1
            if matched >= SOCIAL_RESULT_LIMIT:
                break
        if matched == 0:
            signals.append(watch_signal(context))
    return signals
