from __future__ import annotations

import os
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

from core.models import SignalEvent

HEADERS = {"User-Agent": "Mozilla/5.0 MoroccoRealEstateIntelligence/4.0"}
META_COLLECTOR_MODE = os.getenv("META_COLLECTOR_MODE", "playwright")
META_PLAYWRIGHT_HEADLESS = os.getenv("META_PLAYWRIGHT_HEADLESS", "1") != "0"
META_PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("META_PLAYWRIGHT_TIMEOUT_MS", "45000"))
META_PLAYWRIGHT_WAIT_MS = int(os.getenv("META_PLAYWRIGHT_WAIT_MS", "4500"))
META_STORAGE_STATE_PATH = os.getenv("META_STORAGE_STATE_PATH")
META_SSL_INSECURE = os.getenv("META_SSL_INSECURE", "0") == "1"
META_QUERY_LIMIT = int(os.getenv("META_QUERY_LIMIT", "36"))
META_AD_SEARCH_BASE = (
    "https://www.facebook.com/ads/library/?active_status=active"
    "&ad_type=all&country=MA&media_type=all&search_type=keyword_unordered&q="
)
META_AD_DETAIL_BASE = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA&id="
REAL_ESTATE_KEYWORDS = [
    "immobilier",
    "résidence",
    "residence",
    "appartement",
    "villa",
    "villas",
    "lotissement",
    "bureau",
    "bureaux",
    "plateaux",
    "business",
    "centre d'affaires",
    "centre d’affaires",
    "investissement",
    "commercialisation",
    "pré-commercialisation",
    "pre-commercialisation",
    "lancement",
]


def search_url(query: str) -> str:
    return META_AD_SEARCH_BASE + quote(query)


def detail_url(ad_id: str) -> str:
    return f"{META_AD_DETAIL_BASE}{ad_id}"


def decode_fragment(value: str | None) -> str:
    if not value:
        return ""
    text = value.encode("utf-8").decode("unicode_escape")
    text = text.replace("\\/", "/")
    return clean(text)


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slug_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ]+", (text or "").lower()) if len(token) >= 3]


def fetch_html(url: str) -> str:
    try:
        import requests

        response = requests.get(url, headers=HEADERS, timeout=20, verify=not META_SSL_INSECURE)
        response.raise_for_status()
        return response.text
    except Exception:
        request = Request(url, headers=HEADERS)
        context = None
        if META_SSL_INSECURE:
            context = ssl._create_unverified_context()
        with urlopen(request, timeout=20, context=context) as response:
            return response.read().decode("utf-8", errors="replace")


def challenge_detected(html: str) -> bool:
    lowered = html.lower()
    return "client challenge" in lowered or "http error 403" in lowered or "something went wrong" in lowered


def playwright_ready() -> bool:
    if META_COLLECTOR_MODE == "http":
        return False
    try:
        import playwright  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def fetch_html_with_playwright(url: str) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as engine:
        browser = engine.chromium.launch(
            headless=META_PLAYWRIGHT_HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context_kwargs = {
            "locale": "fr-FR",
            "user_agent": HEADERS["User-Agent"],
            "viewport": {"width": 1440, "height": 1800},
        }
        if META_STORAGE_STATE_PATH and Path(META_STORAGE_STATE_PATH).exists():
            context_kwargs["storage_state"] = META_STORAGE_STATE_PATH
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=META_PLAYWRIGHT_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=min(META_PLAYWRIGHT_TIMEOUT_MS, 15000))
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(META_PLAYWRIGHT_WAIT_MS)
            html = page.content()
        finally:
            context.close()
            browser.close()
    return html


def parse_text_blocks(page_text: str) -> list[dict]:
    normalized = page_text.replace("\xa0", " ")
    pattern = re.compile(
        r"ID dans la bibliothèque\s*:?\s*(?P<ad_id>\d+)(?P<block>.*?)(?=(?:Actif\s+ID dans la bibliothèque\s*:?\s*\d+)|\Z)",
        re.S,
    )
    entries: list[dict] = []
    for match in pattern.finditer(normalized):
        ad_id = match.group("ad_id")
        block = clean(match.group("block"))
        if not block:
            continue
        lines = [clean(line) for line in block.splitlines() if clean(line)]
        page_name = ""
        body_lines: list[str] = []
        inline_match = re.search(
            r"Voir les détails [^\n]*?\s+(?P<page>.*?)\s+Sponsorisé\s+(?P<body>.*)",
            block,
            re.S,
        )
        if inline_match:
            page_name = clean(inline_match.group("page"))
            page_name = re.sub(r"^(la publicité|du récapitulatif)\s+", "", page_name, flags=re.I)
            body_lines = [clean(inline_match.group("body"))]
        if "Sponsorisé" in lines:
            sponsored_index = lines.index("Sponsorisé")
            if not page_name and sponsored_index > 0:
                for candidate in reversed(lines[:sponsored_index]):
                    if candidate.startswith("Voir les détails"):
                        continue
                    if candidate.startswith("Début de diffusion"):
                        continue
                    if candidate.startswith("ID dans la bibliothèque"):
                        continue
                    page_name = candidate
                    break
            if not body_lines:
                body_lines = lines[sponsored_index + 1 : sponsored_index + 8]
        entries.append(
            {
                "ad_id": ad_id,
                "page_name": page_name or "Meta page",
                "body": clean(" ".join(body_lines)),
                "caption": "",
                "landing_page_url": "",
                "snapshot_url": detail_url(ad_id),
            }
        )
    return entries


def enrich_entries_with_links(entries: list[dict], links: list[dict]) -> list[dict]:
    for entry in entries:
        page_name = entry.get("page_name", "").strip().lower()
        page_link = next(
            (
                item["href"]
                for item in links
                if item.get("text", "").strip().lower() == page_name and "facebook.com" in item.get("href", "")
            ),
            "",
        )
        landing_link = next(
            (
                item["href"]
                for item in links
                if item.get("text")
                and ("Learn More" in item["text"] or "En savoir plus" in item["text"])
                and "l.facebook.com/l.php" in item.get("href", "")
            ),
            "",
        )
        if page_link:
            entry["page_link"] = page_link
        if landing_link:
            entry["landing_page_url"] = landing_link
    return entries


def query_contexts(config: dict) -> list[dict]:
    contexts: list[dict] = []
    seen: set[str] = set()
    cities = [cfg["label"] for cfg in config.get("cities", {}).values()]
    city_zones: list[tuple[str, str]] = []
    for cfg in config.get("cities", {}).values():
        label = cfg["label"]
        for zone in cfg.get("zones", [])[:4]:
            city_zones.append((label, zone))
    for promoter in config.get("promoters", {}).get("tracked", []):
        contexts.append({"query": f"{promoter} lancement immobilier Maroc", "promoter": promoter, "city": None, "zone": None})
        for city in cities[:4]:
            contexts.append({"query": f"{promoter} {city} immobilier", "promoter": promoter, "city": city, "zone": None})
            contexts.append({"query": f"{promoter} {city} résidence", "promoter": promoter, "city": city, "zone": None})
        for city, zone in city_zones[:10]:
            contexts.append({"query": f"{promoter} {zone}", "promoter": promoter, "city": city, "zone": zone})
    generic_queries = list(config.get("sources", {}).get("meta_ad_library_searches", []))
    for query in generic_queries:
        contexts.append({"query": query, "promoter": None, "city": None, "zone": None})
    for city in cities[:5]:
        contexts.append({"query": f"projet immobilier {city}", "promoter": None, "city": city, "zone": None})
        contexts.append({"query": f"résidence {city}", "promoter": None, "city": city, "zone": None})
    for city, zone in city_zones[:10]:
        contexts.append({"query": zone, "promoter": None, "city": city, "zone": zone})
    unique_contexts: list[dict] = []
    for context in contexts:
        key = context["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique_contexts.append(context)
    return unique_contexts[:META_QUERY_LIMIT]


def real_estate_relevance(entry: dict, context: dict) -> int:
    haystack = " ".join(
        [
            entry.get("page_name", ""),
            entry.get("body", ""),
            entry.get("caption", ""),
            entry.get("landing_page_url", ""),
        ]
    ).lower()
    score = 0
    keyword_hits = [keyword for keyword in REAL_ESTATE_KEYWORDS if keyword in haystack]
    score += min(len(keyword_hits) * 5, 30)
    promoter = context.get("promoter")
    city = context.get("city")
    zone = context.get("zone")
    if promoter and promoter.lower() in haystack:
        score += 35
    if city and city.lower() in haystack:
        score += 22
    if zone and zone.lower() in haystack:
        score += 18
    query_tokens = slug_tokens(context.get("query", ""))
    score += sum(4 for token in query_tokens if token in haystack)
    landing = entry.get("landing_page_url", "").lower()
    if any(token in landing for token in ["ma/", ".ma", "immo", "residence", "greenlotus", "cgi", "addoha", "alliances", "prestigia"]):
        score += 8
    if "sponsorisé" in haystack:
        score += 4
    return score


def filter_relevant_entries(entries: list[dict], context: dict, limit: int = 5) -> list[dict]:
    ranked = []
    for entry in entries:
        score = real_estate_relevance(entry, context)
        if score < 20:
            continue
        normalized = normalize_candidate(entry, context["query"], context.get("promoter"))
        normalized["city_hint"] = context.get("city")
        normalized["zone_hint"] = context.get("zone")
        ranked.append((score, normalized))
    ranked.sort(key=lambda item: item[0], reverse=True)
    deduped: list[dict] = []
    seen: set[str] = set()
    for _, entry in ranked:
        if entry["ad_id"] in seen:
            continue
        seen.add(entry["ad_id"])
        deduped.append(entry)
        if len(deduped) >= limit:
            break
    return deduped


def fetch_entries_with_playwright(url: str) -> list[dict]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as engine:
        browser = engine.chromium.launch(
            headless=META_PLAYWRIGHT_HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context_kwargs = {
            "locale": "fr-FR",
            "user_agent": HEADERS["User-Agent"],
            "viewport": {"width": 1440, "height": 2200},
        }
        if META_STORAGE_STATE_PATH and Path(META_STORAGE_STATE_PATH).exists():
            context_kwargs["storage_state"] = META_STORAGE_STATE_PATH
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=META_PLAYWRIGHT_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=min(META_PLAYWRIGHT_TIMEOUT_MS, 15000))
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(META_PLAYWRIGHT_WAIT_MS)
            page_text = page.locator("body").inner_text()
            links = page.locator("a").evaluate_all(
                "els => els.map(a => ({text:(a.innerText||'').trim(), href:a.href})).filter(x => x.href)"
            )
        finally:
            context.close()
            browser.close()
    return enrich_entries_with_links(parse_text_blocks(page_text), links)


def regex_entries(html: str) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    compact = html.replace("\\/", "/")
    patterns = [
        re.compile(
            r'"adArchiveID":"(?P<ad_id>\d+)".{0,1200}?"pageName":"(?P<page_name>[^"]+)".{0,2500}?(?:"adSnapshotUrl":"(?P<snapshot>[^"]+)")?',
            re.S,
        ),
        re.compile(
            r'"archive_id":"(?P<ad_id>\d+)".{0,1200}?"page_name":"(?P<page_name>[^"]+)".{0,2500}?(?:"ad_snapshot_url":"(?P<snapshot>[^"]+)")?',
            re.S,
        ),
    ]
    for pattern in patterns:
        for match in pattern.finditer(compact):
            ad_id = match.group("ad_id")
            if not ad_id or ad_id in seen:
                continue
            seen.add(ad_id)
            page_name = decode_fragment(match.groupdict().get("page_name"))
            snapshot = decode_fragment(match.groupdict().get("snapshot")) or detail_url(ad_id)
            window_start = max(0, match.start() - 400)
            window_end = min(len(compact), match.end() + 2200)
            window = compact[window_start:window_end]
            body_match = re.search(r'"(?:ad_creative_body|body|adBody)":"([^"]{10,800})"', window)
            caption_match = re.search(r'"(?:link_caption|caption|linkCaption)":"([^"]{4,400})"', window)
            landing_match = re.search(r'"(?:link_url|linkUrl|landing_page_url|landingPageUrl)":"([^"]{8,800})"', window)
            entries.append(
                {
                    "ad_id": ad_id,
                    "page_name": page_name or "Meta page",
                    "snapshot_url": snapshot,
                    "body": decode_fragment(body_match.group(1) if body_match else ""),
                    "caption": decode_fragment(caption_match.group(1) if caption_match else ""),
                    "landing_page_url": decode_fragment(landing_match.group(1) if landing_match else ""),
                }
            )
    return entries


def normalize_candidate(entry: dict, query: str, promoter: str | None) -> dict:
    body = clean(" ".join(part for part in [entry.get("page_name"), entry.get("body"), entry.get("caption")] if part))
    title_bits = [entry.get("page_name") or "Meta page", f"ad #{entry['ad_id']}"]
    if promoter:
        title_bits.insert(0, promoter)
    return {
        "ad_id": entry["ad_id"],
        "page_name": entry.get("page_name") or "Meta page",
        "snapshot_url": detail_url(entry["ad_id"]),
        "ad_snapshot_url": entry.get("snapshot_url") or detail_url(entry["ad_id"]),
        "landing_page_url": entry.get("landing_page_url") or "",
        "body": body,
        "query": query,
        "title": " · ".join(bit for bit in title_bits if bit),
    }


def score_candidate(entry: dict, promoter: str | None, query: str) -> int:
    haystack = " ".join(
        [
            entry.get("page_name", ""),
            entry.get("body", ""),
            entry.get("caption", ""),
            entry.get("landing_page_url", ""),
        ]
    ).lower()
    score = 0
    if promoter and promoter.lower() in haystack:
        score += 40
    query_tokens = [token for token in re.split(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ]+", query.lower()) if len(token) >= 4]
    score += sum(8 for token in query_tokens if token in haystack)
    if "immobilier" in haystack:
        score += 4
    if "lancement" in haystack or "pré-commercialisation" in haystack or "pre-commercialisation" in haystack:
        score += 8
    return score


def best_entries(html: str, query: str, promoter: str | None, limit: int = 3) -> list[dict]:
    ranked = []
    for entry in regex_entries(html):
        normalized = normalize_candidate(entry, query, promoter)
        ranked.append((score_candidate(normalized, promoter, query), normalized))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [entry for score, entry in ranked if score > 0][:limit]


def meta_signal(entry: dict, promoter: str | None) -> SignalEvent:
    text = clean(" ".join(part for part in [entry.get("page_name"), entry.get("body"), entry.get("landing_page_url")] if part))
    return SignalEvent(
        collector="ads.meta_ads",
        channel="advertising",
        source=entry.get("page_name") or "Meta Ad Library",
        signal_type="meta_ad",
        title=entry["title"],
        url=entry["snapshot_url"],
        text=text,
        is_primary=True,
        launch_weight=38,
        confidence_weight=40,
        city_hint=entry.get("city_hint"),
        zone_hint=entry.get("zone_hint"),
        metadata={
            "promoter_hint": promoter,
            "ad_id": entry["ad_id"],
            "page_name": entry.get("page_name"),
            "ad_snapshot_url": entry.get("ad_snapshot_url"),
            "landing_page_url": entry.get("landing_page_url"),
            "query": entry.get("query"),
            "city_hint": entry.get("city_hint"),
            "zone_hint": entry.get("zone_hint"),
        },
        reasons=[f"publicité Meta exacte détectée: ad_id {entry['ad_id']}"],
    )


def watch_signal(query: str, promoter: str | None, reason: str) -> SignalEvent:
    return SignalEvent(
        collector="ads.meta_ads",
        channel="advertising",
        source="Meta Ad Library",
        signal_type="meta_watch",
        title=f"Meta Ads watch: {query}",
        url=search_url(query),
        text=query,
        is_primary=True,
        launch_weight=26 if promoter is None else 34,
        confidence_weight=28 if promoter is None else 38,
        metadata={"promoter_hint": promoter, "query": query},
        reasons=[reason],
    )


def collect(config: dict) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for context in query_contexts(config):
        query = context["query"]
        promoter = context.get("promoter")
        url = search_url(query)
        try:
            entries = []
            html = ""
            if playwright_ready():
                try:
                    dom_entries = fetch_entries_with_playwright(url)
                    entries = filter_relevant_entries(dom_entries, context)
                except Exception as error:
                    print(f"WARN meta ads playwright failed: {query} => {error}")
            if not entries:
                html = fetch_html(url)
                if challenge_detected(html):
                    raise RuntimeError("HTTP Error 403: Client challenge")
                entries = best_entries(html, query, promoter, limit=5)
        except Exception as error:
            print(f"WARN meta ads failed: {query} => {error}")
            entries = []
        if entries:
            signals.extend(meta_signal(entry, promoter) for entry in entries)
            continue
        fallback_reason = "surveillance Meta Ad Library"
        if promoter is None:
            fallback_reason = "mot-clé Meta Ads à vérifier"
        signals.append(watch_signal(query, promoter, fallback_reason))
    return signals


__all__ = [
    "best_entries",
    "collect",
    "detail_url",
    "regex_entries",
    "search_url",
]
