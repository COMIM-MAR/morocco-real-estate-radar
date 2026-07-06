from __future__ import annotations

import os
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 MoroccoRealEstateIntelligence/4.0"}
DETAIL_MARKERS = ("/a/", "/pa/", "/projet/", "/projets/", "/residence/", "/programmes/")
CONNECT_TIMEOUT_SECONDS = float(os.getenv("COLLECTOR_CONNECT_TIMEOUT_SECONDS", "5"))
READ_TIMEOUT_SECONDS = float(os.getenv("COLLECTOR_READ_TIMEOUT_SECONDS", "8"))
DETAIL_PAGE_LIMIT = int(os.getenv("COLLECTOR_DETAIL_PAGE_LIMIT", "12"))
MAX_RESPONSE_BYTES = int(os.getenv("COLLECTOR_MAX_RESPONSE_BYTES", "400000"))


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def detail_like(url: str) -> bool:
    return any(marker in urlparse(url).path.lower() for marker in DETAIL_MARKERS)


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def fetch(url: str) -> tuple[BeautifulSoup, str]:
    response = requests.get(
        url,
        headers=HEADERS,
        stream=True,
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    chunks: list[bytes] = []
    total_bytes = 0
    for chunk in response.iter_content(chunk_size=16384):
        if not chunk:
            continue
        chunks.append(chunk)
        total_bytes += len(chunk)
        if total_bytes >= MAX_RESPONSE_BYTES:
            break
    response.close()
    html = b"".join(chunks).decode(response.encoding or "utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
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


def same_domain(left: str, right: str) -> bool:
    return domain(left) == domain(right)


def keyword_hits(text: str, keywords: list[str]) -> list[str]:
    lowered = clean(text).lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def collect_detail_pages(source_url: str, max_links: int = DETAIL_PAGE_LIMIT) -> list[tuple[str, str]]:
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
