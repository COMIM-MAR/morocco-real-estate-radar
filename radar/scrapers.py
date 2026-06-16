from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .models import Opportunity

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MoroccoRealEstateRadar/0.2)"
}

GENERIC_BAD_PATTERNS = [
    "ville al houceima",
    "kénitra nouacer agadir",
    "casablanca marrakech essaouira",
    "accueil",
    "contactez-nous",
    "qui sommes-nous",
]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_generic_page(text: str, url: str) -> bool:
    t = text.lower()
    path = urlparse(url).path.strip("/")

    if path == "":
        return True

    if len(text) > 500 and sum(1 for p in GENERIC_BAD_PATTERNS if p in t) >= 1:
        return True

    if "en savoir plus" not in t and "à vendre" not in t and "a vendre" not in t and "lotissement" not in t and "projet" not in t:
        return True

    return False


def scrape_web_page(name: str, url: str, timeout: int = 20) -> list[Opportunity]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN source failed: {name} {url} => {exc}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    results: list[Opportunity] = []

    candidates = soup.select(
        "article, .card, .project, .property, .item, .produit, .projet, li, a[href]"
    )

    seen_urls = set()

    for node in candidates[:500]:
        text = clean(node.get_text(" "))
        if len(text) < 25:
            continue

        link = node.get("href") if node.name == "a" else None
        if not link:
            a = node.find("a", href=True)
            link = a.get("href") if a else url

        full_url = urljoin(url, link)

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        if is_generic_page(text, full_url):
            continue

        title = text[:180]
        results.append(
            Opportunity(
                source=name,
                title=title,
                url=full_url,
                text=text[:3000],
            )
        )

    return results


def collect_all(config: dict) -> list[Opportunity]:
    out: list[Opportunity] = []
    for src in config.get("sources", {}).get("web_pages", []):
        out.extend(scrape_web_page(src["name"], src["url"]))
    return out
