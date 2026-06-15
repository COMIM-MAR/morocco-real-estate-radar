from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .models import Opportunity

HEADERS = {
    "User-Agent": "Mozilla/5.0 MoroccoRealEstateRadar/0.1 (+https://github.com/)"
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def scrape_web_page(name: str, url: str, timeout: int = 20) -> list[Opportunity]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN source failed: {name} {url} => {exc}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    results: list[Opportunity] = []

    # Capture cards, articles and links. This is intentionally generic for MVP.
    candidates = soup.select("article, .card, .project, .property, .item, li, a")
    if not candidates:
        candidates = soup.find_all("a")

    for node in candidates[:300]:
        text = clean(node.get_text(" "))
        if len(text) < 25:
            continue
        link = node.get("href") if node.name == "a" else None
        if not link:
            a = node.find("a", href=True)
            link = a.get("href") if a else url
        full_url = urljoin(url, link)
        title = text[:140]
        results.append(Opportunity(source=name, title=title, url=full_url, text=text[:2000]))

    return results


def collect_all(config: dict) -> list[Opportunity]:
    out: list[Opportunity] = []
    for src in config.get("sources", {}).get("web_pages", []):
        out.extend(scrape_web_page(src["name"], src["url"]))
    return out
