from __future__ import annotations

from urllib.parse import urlparse

from collectors.common import clean, collect_detail_pages, fetch
from core.models import SignalEvent

GENERIC_PROMOTER_CATEGORY_TITLES = {
    "projets économiques",
    "projets economiques",
    "projets moyen standing",
    "projets haut standing",
    "lots de terrains",
    "locaux commerciaux",
    "plateaux de bureaux",
    "équipements sociaux",
    "equipements sociaux",
    "guide d'achat",
    "guide d’achat",
    "financement",
    "actualités",
    "actualites",
    "contact",
    "plus d'infos",
    "plus d’infos",
    "je consulte",
    "lire plus",
    "en savoir plus",
}


def is_generic_promoter_category(title: str, text: str) -> bool:
    normalized_title = clean(title).lower()
    if normalized_title in GENERIC_PROMOTER_CATEGORY_TITLES:
        return True
    category_markers = [
        "projets économiques",
        "projets moyen standing",
        "projets haut standing",
        "lots de terrains",
        "locaux commerciaux",
        "plateaux de bureaux",
    ]
    normalized_text = clean(text).lower()
    category_hits = sum(1 for marker in category_markers if marker in normalized_text)
    return category_hits >= 4


def is_generic_promoter_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/projet/type/" in path


def derive_project_title(url: str, title: str, text: str) -> str:
    normalized_title = clean(title)
    if normalized_title and normalized_title.lower() not in GENERIC_PROMOTER_CATEGORY_TITLES:
        return normalized_title
    slug = urlparse(url).path.split("/")[-1].replace("-", " ").strip()
    slug = clean(slug)
    if slug:
        return " ".join(token.upper() if token.isupper() and len(token) <= 5 else token.capitalize() for token in slug.split())
    return clean(text[:180])


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for source in config.get("sources", {}).get("promoters", []):
        try:
            links = collect_detail_pages(source["url"])
        except Exception as error:
            print(f"WARN promoter source failed: {source['name']} {source['url']} => {error}")
            continue
        for url, link_title in links:
            try:
                _, full_text = fetch(url)
            except Exception:
                full_text = link_title
            text = clean(f"{link_title} {full_text}")
            if len(text) < 30:
                continue
            if is_generic_promoter_url(url):
                continue
            effective_title = derive_project_title(url, link_title or "", text)
            if is_generic_promoter_category(effective_title or "", text):
                continue
            signals.append(
                SignalEvent(
                    collector="promoters.websites",
                    channel="project_discovery",
                    source=source["name"],
                    signal_type="promoter_page",
                    title=effective_title or text[:180],
                    url=url,
                    text=text,
                    is_primary=True,
                    launch_weight=30,
                    confidence_weight=30,
                    metadata={"promoter_hint": source["name"]},
                    reasons=["nouvelle page promoteur"],
                )
            )
    return signals
