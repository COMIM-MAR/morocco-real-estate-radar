from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .models import Opportunity

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

GENERIC_BAD_PATTERNS = [
    "ville al houceima",
    "kénitra nouacer agadir",
    "casablanca marrakech essaouira",
    "accueil",
    "contactez-nous",
    "qui sommes-nous",
]

PRICE_RE = re.compile(
    r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)|"
    r"(?:prix|à partir de|a partir de)\s*(?:de)?\s*(\d[\d\s.,]{4,})|"
    r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)",
    re.I,
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_mubawab_url(url: str) -> bool:
    return "mubawab.ma" in urlparse(url).netloc


def is_detail_like_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return (
        "/a/" in path
        or "/pa/" in path
        or "/projet/" in path
        or "/produits/projets/" in path.lower()
    )


def has_price(text: str) -> bool:
    return bool(PRICE_RE.search(text or ""))


def is_generic_page(text: str, url: str) -> bool:
    t = text.lower()
    path = urlparse(url).path.strip("/")

    if path == "":
        return True

    if len(text) > 500 and any(p in t for p in GENERIC_BAD_PATTERNS):
        return True

    useful_words = [
        "à vendre", "a vendre", "vente", "villa", "appartement", "terrain",
        "lotissement", "projet", "résidence", "residence", "penthouse",
        "duplex", "chambres", "m²", "m2", "dh", "dhs", "mad", "mdh",
    ]

    if not any(w in t for w in useful_words):
        return True

    return False


def fetch_page_text(url: str, timeout: int = 20) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN detail fetch failed: {url} => {exc}")
        return ""

    soup = BeautifulSoup(r.text, "lxml")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    parts = []

    title = soup.find("title")
    if title:
        parts.append(clean(title.get_text(" ")))

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        parts.append(clean(meta_desc["content"]))

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        parts.append(clean(og_title["content"]))

    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        parts.append(clean(og_desc["content"]))

    body_text = clean(soup.get_text(" "))
    parts.append(body_text)

    return clean(" ".join(parts))[:8000]


def extract_candidate_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        full_url = urljoin(base_url, href)
        text = clean(a.get_text(" "))

        if not text:
            parent = a.find_parent()
            text = clean(parent.get_text(" ")) if parent else ""

        if len(text) < 15:
            continue

        if not is_detail_like_url(full_url):
            continue

        links.append((full_url, text[:250]))

    return links


def scrape_web_page(name: str, url: str, timeout: int = 20) -> list[Opportunity]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN source failed: {name} {url} => {exc}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    results: list[Opportunity] = []
    seen_urls = set()

    candidates = extract_candidate_links(soup, url)

    # If the configured source is already a project/detail page
    if is_detail_like_url(url):
        candidates.insert(0, (url, clean(soup.get_text(" "))[:250]))

    for full_url, preview_text in candidates[:80]:
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        detail_text = fetch_page_text(full_url, timeout=timeout)
        combined_text = clean(f"{preview_text} {detail_text}")

        if len(combined_text) < 40:
            continue

        if is_generic_page(combined_text, full_url):
            continue

        title = preview_text
        if not title or len(title) < 20:
            title = combined_text[:180]

        results.append(
            Opportunity(
                source=name,
                title=title[:220],
                url=full_url,
                text=combined_text[:8000],
            )
        )

    return results


def collect_all(config: dict) -> list[Opportunity]:
    out: list[Opportunity] = []
    for src in config.get("sources", {}).get("web_pages", []):
        out.extend(scrape_web_page(src["name"], src["url"]))
    return out
