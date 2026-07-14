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
META_PROJECT_QUERY_LIMIT = int(os.getenv("META_PROJECT_QUERY_LIMIT", "12"))
META_AD_SEARCH_BASE = (
    "https://www.facebook.com/ads/library/?active_status=active"
    "&ad_type=all&country=MA&media_type=all&search_type=keyword_unordered&q="
)
META_AD_DETAIL_BASE = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA&id="
REAL_ESTATE_KEYWORDS = [
    "immobilier",
    "résidentiel",
    "residentiel",
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
NON_REAL_ESTATE_BLOCKLIST = [
    "travel",
    "voyage",
    "tourisme",
    "tourist",
    "billetterie",
    "visa",
    "omra",
    "umrah",
    "hajj",
    "hotel",
    "hôtel",
    "vol",
    "flight",
]
PROJECT_QUERY_STOPWORDS = {
    "maroc",
    "morocco",
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "tiktok",
    "immobilier",
    "immobiliere",
    "immobilière",
    "résidence",
    "residence",
    "projet",
    "programme",
    "appartement",
    "appartements",
    "villa",
    "villas",
    "lotissement",
    "casablanca",
    "tanger",
    "rabat",
    "agadir",
    "marrakech",
    "search",
    "plus",
    "infos",
    "je",
    "consulte",
    "voir",
    "procédure",
    "procedure",
    "autorisation",
    "construction",
    "economiques",
    "économiques",
    "moyen",
    "standing",
    "haut",
    "ad",
    "ads",
    "watch",
}
GENERIC_PROJECT_PHRASES = {
    "plus d infos",
    "je consulte",
    "projet immobilier",
    "residence ad",
    "résidence ad",
    "meta ads watch projets",
    "projets economiques",
    "projets économiques",
    "projets moyen standing",
    "projets haut standing",
}


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


def unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def extract_media_urls(window: str) -> tuple[list[str], list[str]]:
    image_patterns = [
        r'"(?:image_url|imageUrl|original_image_url|originalImageUrl|resized_image_url|resizedImageUrl|video_preview_image_url|videoPreviewImageUrl|watermarked_resized_image_uri|watermarkedResizedImageUri|image_uri|imageUri)":"([^"]+)"',
    ]
    video_patterns = [
        r'"(?:video_hd_url|videoHdUrl|video_sd_url|videoSdUrl|video_url|videoUrl)":"([^"]+)"',
    ]
    image_urls: list[str] = []
    video_urls: list[str] = []
    for pattern in image_patterns:
        image_urls.extend(decode_fragment(match) for match in re.findall(pattern, window))
    for pattern in video_patterns:
        video_urls.extend(decode_fragment(match) for match in re.findall(pattern, window))
    image_urls = [url for url in image_urls if url.startswith("http")]
    video_urls = [url for url in video_urls if url.startswith("http")]
    return unique_preserve(image_urls), unique_preserve(video_urls)


def slug_tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ]+", (text or "").lower()) if len(token) >= 3]


def display_name(text: str) -> str:
    parts = []
    for token in clean(text).split():
        parts.append(token if token.isupper() and len(token) <= 5 else token.capitalize())
    return " ".join(parts)


def project_query_candidate(raw: str | None, config: dict) -> str | None:
    if not raw:
        return None
    cleaned = clean(raw)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"[|_/\\-]+", " ", cleaned)
    cleaned = re.sub(r"\b(page|post|publication|reel|video|vidéo)\b", " ", cleaned, flags=re.I)
    promoter_tokens = {
        token
        for promoter in config.get("promoters", {}).get("tracked", [])
        for token in slug_tokens(promoter)
    }
    city_tokens = {
        token
        for city_cfg in config.get("cities", {}).values()
        for token in slug_tokens(city_cfg.get("label", ""))
    }
    zone_tokens = {
        token
        for city_cfg in config.get("cities", {}).values()
        for zone in city_cfg.get("zones", [])
        for token in slug_tokens(zone)
    }
    ignored = PROJECT_QUERY_STOPWORDS | promoter_tokens | city_tokens | zone_tokens
    tokens = [token for token in re.findall(r"[A-Za-zÀ-ÿ0-9']+", cleaned) if len(token) >= 3]
    filtered = [token for token in tokens if token.lower() not in ignored]
    if len(filtered) < 2:
        return None
    candidate = display_name(" ".join(filtered[:4]))
    normalized_candidate = clean(candidate).lower()
    normalized_candidate = re.sub(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ]+", " ", normalized_candidate).strip()
    if normalized_candidate in GENERIC_PROJECT_PHRASES:
        return None
    if len(slug_tokens(candidate)) < 2:
        return None
    return candidate


def candidate_project_contexts(config: dict, seed_signals: list[SignalEvent] | None = None) -> list[dict]:
    if not seed_signals:
        return []
    contexts: list[dict] = []
    seen: set[str] = set()
    interesting_channels = {"project_discovery", "google_discovery", "news", "urbanism"}
    for signal in seed_signals:
        if signal.channel not in interesting_channels:
            continue
        raw_candidates = [
            signal.project_name_hint,
            signal.title,
            signal.metadata.get("page_name") if isinstance(signal.metadata, dict) else None,
        ]
        for raw in raw_candidates:
            candidate = project_query_candidate(raw, config)
            if not candidate:
                continue
            query_variants = [candidate, f'"{candidate}" immobilier Maroc']
            if signal.city_hint:
                query_variants.append(f'"{candidate}" {signal.city_hint}')
            for query in query_variants:
                key = query.lower()
                if key in seen:
                    continue
                seen.add(key)
                contexts.append(
                    {
                        "query": query,
                        "promoter": signal.promoter_hint,
                        "city": signal.city_hint,
                        "zone": signal.zone_hint,
                    }
                )
            break
        if len(contexts) >= META_PROJECT_QUERY_LIMIT:
            break
    return contexts[:META_PROJECT_QUERY_LIMIT]


def configured_project_contexts(config: dict) -> list[dict]:
    contexts: list[dict] = []
    for item in config.get("sources", {}).get("meta_project_seeds", []):
        if isinstance(item, str):
            contexts.append({"query": item, "promoter": None, "city": None, "zone": None})
            continue
        contexts.append(
            {
                "query": item.get("query", ""),
                "promoter": item.get("promoter"),
                "city": item.get("city"),
                "zone": item.get("zone"),
            }
        )
    return [context for context in contexts if context.get("query")]


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
                "image_urls": [],
                "video_urls": [],
            }
        )
    return entries


def enrich_entries_with_links(entries: list[dict], links: list[dict], html: str = "") -> list[dict]:
    regex_map = {entry["ad_id"]: entry for entry in regex_entries(html)} if html else {}
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
        regex_entry = regex_map.get(entry.get("ad_id"))
        if regex_entry:
            entry["snapshot_url"] = regex_entry.get("snapshot_url") or entry.get("snapshot_url")
            entry["ad_snapshot_url"] = regex_entry.get("snapshot_url") or entry.get("ad_snapshot_url")
            entry["body"] = entry.get("body") or regex_entry.get("body") or ""
            entry["caption"] = entry.get("caption") or regex_entry.get("caption") or ""
            entry["landing_page_url"] = entry.get("landing_page_url") or regex_entry.get("landing_page_url") or ""
            entry["image_urls"] = unique_preserve((entry.get("image_urls") or []) + (regex_entry.get("image_urls") or []))
            entry["video_urls"] = unique_preserve((entry.get("video_urls") or []) + (regex_entry.get("video_urls") or []))
    return entries


def query_contexts(config: dict, seed_signals: list[SignalEvent] | None = None) -> list[dict]:
    contexts: list[dict] = []
    seen: set[str] = set()
    cities = [cfg["label"] for cfg in config.get("cities", {}).values()]
    city_zones: list[tuple[str, str]] = []
    for cfg in config.get("cities", {}).values():
        label = cfg["label"]
        for zone in cfg.get("zones", [])[:4]:
            city_zones.append((label, zone))
    for context in configured_project_contexts(config):
        contexts.append(context)
    for context in candidate_project_contexts(config, seed_signals):
        contexts.append(context)
    generic_queries = list(config.get("sources", {}).get("meta_ad_library_searches", []))
    for query in generic_queries:
        contexts.append({"query": query, "promoter": None, "city": None, "zone": None})
    for city in cities[:5]:
        contexts.append({"query": f"projet immobilier {city}", "promoter": None, "city": city, "zone": None})
        contexts.append({"query": f"résidence {city}", "promoter": None, "city": city, "zone": None})
    for city, zone in city_zones[:10]:
        contexts.append({"query": zone, "promoter": None, "city": city, "zone": zone})
    for promoter in config.get("promoters", {}).get("tracked", []):
        contexts.append({"query": f"{promoter} lancement immobilier Maroc", "promoter": promoter, "city": None, "zone": None})
        for city in cities[:4]:
            contexts.append({"query": f"{promoter} {city} immobilier", "promoter": promoter, "city": city, "zone": None})
            contexts.append({"query": f"{promoter} {city} résidence", "promoter": promoter, "city": city, "zone": None})
        for city, zone in city_zones[:10]:
            contexts.append({"query": f"{promoter} {zone}", "promoter": promoter, "city": city, "zone": zone})
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
    visible_haystack = " ".join(
        [
            entry.get("page_name", ""),
            entry.get("body", ""),
            entry.get("caption", ""),
        ]
    ).lower()
    page_name_haystack = (entry.get("page_name", "") or "").lower()
    score = 0
    keyword_hits = [keyword for keyword in REAL_ESTATE_KEYWORDS if keyword in haystack]
    visible_keyword_hits = [keyword for keyword in REAL_ESTATE_KEYWORDS if keyword in visible_haystack]
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
    landing_real_estate_hits = [
        token
        for token in ["immo", "immobilier", "residence", "résidence", "lotissement", "villa", "appartement", "bureau"]
        if token in landing
    ]
    if any(token in landing for token in ["ma/", ".ma", "immo", "residence", "greenlotus", "cgi", "addoha", "alliances", "prestigia"]):
        score += 8
    if "sponsorisé" in haystack:
        score += 4
    query_tokens = slug_tokens(context.get("query", ""))
    visible_query_hits = [token for token in query_tokens if token in visible_haystack]
    page_name_query_hits = [token for token in query_tokens if token in page_name_haystack]
    if not visible_keyword_hits and not visible_query_hits:
        return 0
    if any(token in haystack for token in NON_REAL_ESTATE_BLOCKLIST) and not keyword_hits and not landing_real_estate_hits:
        return 0
    if not visible_keyword_hits and not landing_real_estate_hits:
        return 0
    if query_tokens and len(query_tokens) <= 3 and not page_name_query_hits:
        return 0
    if (entry.get("page_name") or "").lower().startswith("récapitulatif "):
        return 0
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
            html = page.content()
            links = page.locator("a").evaluate_all(
                "els => els.map(a => ({text:(a.innerText||'').trim(), href:a.href})).filter(x => x.href)"
            )
        finally:
            context.close()
            browser.close()
    return enrich_entries_with_links(parse_text_blocks(page_text), links, html)


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
            image_urls, video_urls = extract_media_urls(window)
            entries.append(
                {
                    "ad_id": ad_id,
                    "page_name": page_name or "Meta page",
                    "snapshot_url": snapshot,
                    "body": decode_fragment(body_match.group(1) if body_match else ""),
                    "caption": decode_fragment(caption_match.group(1) if caption_match else ""),
                    "landing_page_url": decode_fragment(landing_match.group(1) if landing_match else ""),
                    "image_urls": image_urls,
                    "video_urls": video_urls,
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
        "image_urls": unique_preserve(entry.get("image_urls") or []),
        "video_urls": unique_preserve(entry.get("video_urls") or []),
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
        project_name_hint=entry.get("page_name"),
        metadata={
            "promoter_hint": promoter,
            "ad_id": entry["ad_id"],
            "page_name": entry.get("page_name"),
            "ad_snapshot_url": entry.get("ad_snapshot_url"),
            "landing_page_url": entry.get("landing_page_url"),
            "image_urls": entry.get("image_urls") or [],
            "video_urls": entry.get("video_urls") or [],
            "query": entry.get("query"),
            "city_hint": entry.get("city_hint"),
            "zone_hint": entry.get("zone_hint"),
        },
        reasons=[f"publicité Meta exacte détectée: ad_id {entry['ad_id']}"],
    )


def social_signal_from_meta(entry: dict, promoter: str | None) -> SignalEvent | None:
    page_link = entry.get("page_link") or ""
    if not page_link:
        return None
    text = clean(" ".join(part for part in [entry.get("page_name"), entry.get("body"), entry.get("landing_page_url")] if part))
    return SignalEvent(
        collector="ads.meta_ads",
        channel="social",
        source=entry.get("page_name") or "Meta page",
        signal_type="social_post",
        title=f"{entry.get('page_name') or 'Meta page'} · social page",
        url=page_link,
        text=text,
        is_primary=True,
        launch_weight=22,
        confidence_weight=26,
        city_hint=entry.get("city_hint"),
        zone_hint=entry.get("zone_hint"),
        project_name_hint=entry.get("page_name"),
        metadata={
            "promoter_hint": promoter,
            "ad_id": entry["ad_id"],
            "page_name": entry.get("page_name"),
            "page_link": page_link,
            "landing_page_url": entry.get("landing_page_url"),
            "image_urls": entry.get("image_urls") or [],
            "video_urls": entry.get("video_urls") or [],
            "query": entry.get("query"),
            "city_hint": entry.get("city_hint"),
            "zone_hint": entry.get("zone_hint"),
        },
        reasons=[f"page sociale reliée à la publicité Meta: ad_id {entry['ad_id']}"],
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


def collect(config: dict, seed_signals: list[SignalEvent] | None = None) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    seen_signal_ids: set[str] = set()
    for context in query_contexts(config, seed_signals):
        query = context["query"]
        promoter = context.get("promoter")
        url = search_url(query)
        try:
            entries = []
            html = ""
            used_playwright = False
            if playwright_ready():
                try:
                    dom_entries = fetch_entries_with_playwright(url)
                    used_playwright = True
                    entries = filter_relevant_entries(dom_entries, context)
                except Exception as error:
                    print(f"WARN meta ads playwright failed: {query} => {error}")
            if not entries and not used_playwright:
                html = fetch_html(url)
                if challenge_detected(html):
                    raise RuntimeError("HTTP Error 403: Client challenge")
                entries = best_entries(html, query, promoter, limit=5)
        except Exception as error:
            print(f"WARN meta ads failed: {query} => {error}")
            entries = []
        if entries:
            for entry in entries:
                ad_signal = meta_signal(entry, promoter)
                if ad_signal.signal_id not in seen_signal_ids:
                    signals.append(ad_signal)
                    seen_signal_ids.add(ad_signal.signal_id)
                social_signal = social_signal_from_meta(entry, promoter)
                if social_signal and social_signal.signal_id not in seen_signal_ids:
                    signals.append(social_signal)
                    seen_signal_ids.add(social_signal.signal_id)
            continue
        fallback_reason = "surveillance Meta Ad Library"
        if promoter is None:
            fallback_reason = "mot-clé Meta Ads à vérifier"
        watch = watch_signal(query, promoter, fallback_reason)
        if watch.signal_id not in seen_signal_ids:
            signals.append(watch)
            seen_signal_ids.add(watch.signal_id)
    return signals


__all__ = [
    "best_entries",
    "collect",
    "detail_url",
    "regex_entries",
    "search_url",
]
