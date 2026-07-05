from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 MoroccoRealEstateIntelligence/4.0"}
DETAIL_MARKERS = ("/a/", "/pa/", "/projet/", "/projets/", "/residence/", "/programmes/")


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def detail_like(url: str) -> bool:
    return any(marker in urlparse(url).path.lower() for marker in DETAIL_MARKERS)


def fetch(url: str) -> tuple[BeautifulSoup, str]:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()
    parts: list[str] = []
    for selector in ["title", "h1", "h2"]:
        for node in soup.select(selector)[:5]:
            parts.append(clean(node.get_text(" ")))
    for meta in soup.find_all("meta"):
        content = meta.get("content")
        if not content:
            continue
        if meta.get("name") in ("description",) or meta.get("property") in ("og:title", "og:description"):
            parts.append(clean(content))
    parts.append(clean(soup.get_text(" ")))
    return soup, clean(" ".join(parts))[:9000]


def collect_detail_pages(source_url: str, max_links: int = 80) -> list[tuple[str, str]]:
    soup, page_text = fetch(source_url)
    links: list[tuple[str, str]] = []
    if detail_like(source_url):
        links.append((source_url, page_text[:220]))
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source_url, anchor["href"])
        title = clean(anchor.get_text(" "))
        if detail_like(url) and len(title) > 8:
            links.append((url, title[:220]))
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, title in links[:max_links]:
        if url in seen:
            continue
        seen.add(url)
        unique.append((url, title))
    return unique

