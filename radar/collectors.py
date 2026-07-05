from __future__ import annotations
import re
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .models import Signal

HEADERS = {"User-Agent": "Mozilla/5.0 MoroccoRealEstateIntelligence/3.0"}
DETAIL_PATTERNS = ("/a/", "/pa/", "/projet/", "/projets/", "/programme", "/residence", "/résidence", "/produits/projets/")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_text(url: str, timeout: int = 20) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN fetch failed: {url} => {exc}")
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    parts = []
    for sel in ["title", "h1", "h2"]:
        for el in soup.select(sel)[:5]:
            parts.append(clean(el.get_text(" ")))
    for meta in soup.find_all("meta"):
        if meta.get("content") and meta.get("name") in ["description"]:
            parts.append(clean(meta["content"]))
        if meta.get("content") and meta.get("property") in ["og:title", "og:description"]:
            parts.append(clean(meta["content"]))
    parts.append(clean(soup.get_text(" ")))
    return clean(" ".join(parts))[:10000]


def is_detail_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in DETAIL_PATTERNS)


def discover_links(url: str) -> list[tuple[str, str]]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as exc:
        print(f"WARN source failed: {url} => {exc}")
        return []
    soup = BeautifulSoup(r.text, "lxml")
    out, seen = [], set()
    if is_detail_url(url):
        out.append((url, clean(soup.get_text(" "))[:250]))
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"])
        if full in seen:
            continue
        seen.add(full)
        txt = clean(a.get_text(" "))
        parent_txt = clean(a.find_parent().get_text(" ")) if a.find_parent() else ""
        preview = txt if len(txt) > len(parent_txt) else parent_txt
        if len(preview) < 15:
            continue
        if is_detail_url(full) or any(w in preview.lower() for w in ["lancement", "projet", "résidence", "residence", "lotissement", "à vendre", "a vendre", "villa"]):
            out.append((full, preview[:300]))
    return out[:120]


def collect_web_source(channel: str, name: str, url: str) -> list[Signal]:
    signals: list[Signal] = []
    for link, preview in discover_links(url):
        text = fetch_text(link)
        combined = clean(f"{preview} {text}")
        if len(combined) < 40:
            continue
        title = preview or combined[:180]
        signals.append(Signal(channel=channel, source=name, title=title[:240], url=link, text=combined[:10000]))
    return signals


def collect_google_news(query: str) -> list[Signal]:
    encoded = urllib.parse.quote(query)
    feed_url = f"https://news.google.com/rss/search?q={encoded}&hl=fr&gl=MA&ceid=MA:fr"
    feed = feedparser.parse(feed_url)
    out = []
    for entry in feed.entries[:15]:
        title = clean(entry.get("title", ""))
        link = entry.get("link", "")
        summary = clean(entry.get("summary", ""))
        out.append(Signal(channel="google_news", source="Google News", title=title, url=link, text=f"{title} {summary}"))
    return out


def collect_meta_ad_search(query: str) -> list[Signal]:
    # Meta Ad Library scraping is intentionally not automated here.
    # We create actionable monitoring links so launches can be reviewed quickly.
    q = urllib.parse.quote(query)
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA&media_type=all&q={q}&search_type=keyword_unordered"
    return [Signal(channel="meta_ads_search", source="Meta Ad Library", title=f"Recherche pubs actives Meta: {query}", url=url, text=f"Meta Ads active search Morocco: {query} lancement immobilier projet pré-commercialisation")]


def collect_all(config: dict) -> list[Signal]:
    out: list[Signal] = []
    for group, channel in [("official_promoter", "official_promoter"), ("listings", "listing")]:
        for src in config.get("sources", {}).get(group, []):
            out.extend(collect_web_source(channel, src["name"], src["url"]))
    for q in config.get("sources", {}).get("google_news_queries", []):
        out.extend(collect_google_news(q))
    for q in config.get("sources", {}).get("meta_ad_library_queries", []):
        out.extend(collect_meta_ad_search(q))
    return out
