from __future__ import annotations

import hashlib
import re
from collections import Counter
from urllib.parse import urlparse

from core.models import ProjectRecord, SignalEvent
from core.scoring import enrich_project, enrich_signal

PROJECT_STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "des",
    "du",
    "d",
    "by",
    "avec",
    "maroc",
    "morocco",
    "immobilier",
    "immobiliere",
    "residence",
    "résidence",
    "projet",
    "programme",
    "appartement",
    "appartements",
    "villas",
    "villa",
    "lotissement",
}
GENERIC_AD_PORTAL_SOURCES = {
    "avito immobilier neuf",
    "avito neuf",
    "mubawab maroc",
    "mubawab",
    "agenz",
}
GENERIC_META_SOURCE_PAGES = {
    "lotti.ma",
}
GENERIC_PROJECT_TITLES = {
    "je consulte",
    "plus d infos",
    "plus d'infos",
    "plus d’infos",
    "lire plus",
    "en savoir plus",
    "search",
}
GENERIC_PROMOTER_CATEGORY_URL_MARKERS = {
    "/projet/type/",
}
GENERIC_NON_PROJECT_TITLES = {
    "urbanisme planification autorisations",
    "etudes projets",
    "transformation digitale",
    "gestion patrimoine",
    "procédure autorisation construction",
    "agence urbaine de casablanca",
    "projet immobilier",
}


def normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9àâçéèêëîïôùûüÿñæœ\s-]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def project_tokens(text: str) -> list[str]:
    words = normalize(text).split()
    return [word for word in words if len(word) > 2 and word not in PROJECT_STOPWORDS]


def looks_like_specific_project_name(text: str | None) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return False
    if len(project_tokens(cleaned)) >= 1:
        return True
    return bool(re.search(r"[A-Za-zÀ-ÿ].*\d|\d.*[A-Za-zÀ-ÿ]", cleaned))


def extract_project_name_from_generic_ad(signal: SignalEvent) -> str | None:
    source = normalize(signal.source or "")
    title = normalize(signal.title or "")
    if source not in GENERIC_AD_PORTAL_SOURCES and title not in GENERIC_AD_PORTAL_SOURCES:
        return None
    text = clean_text(signal.text)
    for generic in GENERIC_AD_PORTAL_SOURCES:
        text = re.sub(rf"^(?:{re.escape(generic)})\s+", "", text, flags=re.I)
        text = re.sub(rf"^(?:{re.escape(generic)})\s+", "", text, flags=re.I)
    patterns = [
        r"(?:Découvrez|Decouvrez)\s+(?P<name>[A-ZÀ-ÿ0-9][^,:!.]{3,80}?)(?:\s+par|\s*,|\s*:)",
        r"(?P<name>[A-ZÀ-ÿ0-9][^,:!.]{3,80}?)\s*,\s+votre nouvelle adresse",
        r"(?P<name>Résidences?\s+[A-ZÀ-ÿ0-9][^,:!.]{2,80})(?:\s*:|\s*,)",
        r"(?P<name>[A-ZÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’ -]{3,80})\s*,\s+un projet résidentiel",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        candidate = match.group("name").strip(" -–—")
        if looks_like_specific_project_name(candidate):
            return candidate
    return None


def extract_project_name_from_meta_signal(signal: SignalEvent) -> str | None:
    if signal.collector != "ads.meta_ads":
        return None
    text = clean_text(signal.text)
    page_name = clean_text(signal.project_name_hint or signal.source or "")
    cleaned_page_name = re.sub(r"\s+by\s+.+$", "", page_name, flags=re.I).strip(" -–—")
    if cleaned_page_name and looks_like_specific_project_name(cleaned_page_name) and " by " in page_name.lower():
        return cleaned_page_name
    patterns = [
        r"(?:lancement du nouveau projet|nouveau projet)\s+(?P<name>[A-ZÀ-ÿ0-9][^,:!.]{2,80}?)(?:,|\s+signé|\s+signe|\s+situ[ée]|\s+à|\s+-)",
        r"(?:découvrez|decouvrez)\s+(?P<name>[A-ZÀ-ÿ0-9][^,:!.]{2,80}?)(?:\s+par|\s+by|\s*:|,)",
        r"\bà\s+(?P<name>Les\s+[A-ZÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’ -]{2,80}?)(?:\.|,|\s+projet|\s+par)",
        r"(?:projet|résidence|residence)\s+(?P<name>[A-ZÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’ -]{2,80}?)(?:\s+par|\s+by|\s*:|,)",
        r"(?P<name>Les\s+[A-ZÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’ -]{2,80}?)(?:\s+par|\s+by|\s*:|,)",
        r"(?P<name>[A-ZÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’ -]{2,80}?)\s*,\s+sign[ée]\s+.+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        candidate = match.group("name").strip(" -–—")
        if looks_like_specific_project_name(candidate) and normalize(candidate) not in GENERIC_AD_PORTAL_SOURCES:
            return candidate
    if page_name and looks_like_specific_project_name(page_name) and page_name.lower() not in GENERIC_META_SOURCE_PAGES:
        return page_name
    return None


def clean_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_generic_project_title(value: str | None) -> bool:
    return normalize(value or "") in GENERIC_PROJECT_TITLES


def should_skip_signal(signal: SignalEvent) -> bool:
    lowered_url = (signal.url or "").lower()
    lowered_title = normalize(signal.title or "")
    if signal.collector == "promoters.websites" and any(marker in lowered_url for marker in GENERIC_PROMOTER_CATEGORY_URL_MARKERS):
        return True
    lowered_text = normalize(signal.text or "")
    lowered_source = normalize(signal.source or "")
    if signal.collector == "ads.meta_ads":
        if lowered_source in GENERIC_META_SOURCE_PAGES:
            return True
        if "google maps des terrains" in lowered_text or "carte interactive unique" in lowered_text:
            return True
    if signal.signal_type in {"search_watch", "meta_watch", "news_watch", "social_watch"} and "projet immobilier" in lowered_title:
        return True
    if signal.channel == "urbanism" and (
        lowered_title in GENERIC_NON_PROJECT_TITLES
        or lowered_url.rstrip("/") in {"https://www.auc.ma", "https://auc.ma", "https://www.autanger.ma", "https://autanger.ma"}
        or "/etudes-projets/" in lowered_url
        or "/gestion-urbaine/procedure" in lowered_url
    ):
        return True
    return False


def project_name_from_url_slug(url: str) -> str | None:
    slug = urlparse(url).path.split("/")[-1]
    slug_tokens = [token for token in slug.replace("-", " ").split() if len(token) > 2]
    if not slug_tokens:
        return None
    return " ".join(word.capitalize() for word in slug_tokens[:6])


def infer_project_name(signal: SignalEvent) -> str:
    meta_project_name = extract_project_name_from_meta_signal(signal)
    if meta_project_name:
        return meta_project_name
    generic_title = is_generic_project_title(signal.title) or is_generic_project_title(signal.project_name_hint)
    if generic_title:
        slug_name = project_name_from_url_slug(signal.url)
        if slug_name:
            return slug_name
    text = f"{signal.title} {signal.url}"
    patterns = [
        r"(sun[\s-]?hills?)",
        r"(prestigia[\s-][a-z0-9-]+)",
        r"(résidence[\s-][a-z0-9-]+)",
        r"(residence[\s-][a-z0-9-]+)",
        r"(lotissement[\s-][a-z0-9-]+)",
        r"(projet[\s-][a-z0-9-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalize(text), re.I)
        if match:
            return match.group(1).replace("-", " ").title()
    slug_name = project_name_from_url_slug(signal.url)
    if slug_name:
        return slug_name
    tokens = project_tokens(signal.title)
    return " ".join(word.capitalize() for word in tokens[:4]) or signal.source


def canonical_name(name: str) -> str:
    return " ".join(project_tokens(name)) or normalize(name)


def alias_candidates(signal: SignalEvent) -> list[str]:
    derived_project_name = extract_project_name_from_generic_ad(signal)
    if derived_project_name:
        candidates = [derived_project_name]
    else:
        meta_project_name = extract_project_name_from_meta_signal(signal)
        if meta_project_name:
            candidates = [meta_project_name]
        else:
            candidates = [signal.project_name_hint or "", infer_project_name(signal), signal.title]
    slug_name = project_name_from_url_slug(signal.url)
    if slug_name and not derived_project_name:
        candidates.append(slug_name)
    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        if is_generic_project_title(candidate):
            continue
        key = normalize(candidate)
        if key in seen:
            continue
        seen.add(key)
        aliases.append(candidate)
    return aliases


def signal_identity(signal: SignalEvent) -> dict:
    aliases = alias_candidates(signal)
    token_sets = [set(project_tokens(alias)) for alias in aliases]
    primary_tokens = max(token_sets, key=len, default=set())
    promoter = normalize(signal.promoter_hint or signal.source)
    city = normalize(signal.city_hint or "")
    zone = normalize(signal.zone_hint or "")
    return {
        "aliases": aliases,
        "tokens": primary_tokens,
        "promoter": promoter,
        "city": city,
        "zone": zone,
        "source": normalize(signal.source),
    }


def project_key(name: str, city: str | None, promoter: str | None) -> str:
    raw = f"{canonical_name(name)}|{normalize(city or '')}|{normalize(promoter or '')}"
    return hashlib.sha1(raw.encode()).hexdigest()


def score_group_match(group: dict, signal: SignalEvent) -> int:
    identity = signal_identity(signal)
    score = 0
    group_tokens = group["tokens"]
    overlap = len(group_tokens & identity["tokens"])
    name_match = any(canonical_name(alias) in group["alias_keys"] for alias in identity["aliases"])
    exactish_signals = {"meta_ad", "promoter_page", "project_page", "listing_detail", "search_result", "urbanism_page"}
    if signal.signal_type in exactish_signals and overlap == 0 and not name_match:
        return 0
    if signal.signal_type in {"meta_ad", "promoter_page", "project_page"} and overlap < 2 and not name_match:
        return 0
    if overlap >= 2:
        score += 50
    elif overlap == 1:
        score += 18
    if group["promoter"] and identity["promoter"] and group["promoter"] == identity["promoter"]:
        score += 25
    if group["city"] and identity["city"] and group["city"] == identity["city"]:
        score += 20
    if group["zone"] and identity["zone"] and group["zone"] == identity["zone"]:
        score += 8
    if group["source"] == identity["source"]:
        score += 5
    if name_match:
        score += 30
    return score


def add_signal_to_group(group: dict, signal: SignalEvent) -> None:
    identity = signal_identity(signal)
    group["signals"].append(signal)
    group["tokens"].update(identity["tokens"])
    group["alias_keys"].update(canonical_name(alias) for alias in identity["aliases"])
    group["aliases"].update(identity["aliases"])
    if not group["promoter"] and identity["promoter"]:
        group["promoter"] = identity["promoter"]
    if not group["city"] and identity["city"]:
        group["city"] = identity["city"]
    if not group["zone"] and identity["zone"]:
        group["zone"] = identity["zone"]


def best_group(groups: list[dict], signal: SignalEvent) -> dict | None:
    ranked = sorted(((score_group_match(group, signal), group) for group in groups), key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < 45:
        return None
    return ranked[0][1]


def resolve_projects(signals: list[SignalEvent], config: dict) -> list[ProjectRecord]:
    enriched = [enrich_signal(signal, config) for signal in signals if not should_skip_signal(signal)]
    enriched.sort(key=lambda signal: (signal.promoter_hint or "", signal.city_hint or "", signal.discovered_at))
    groups: list[dict] = []
    for signal in enriched:
        group = best_group(groups, signal)
        if group is None:
            identity = signal_identity(signal)
            group = {
                "signals": [],
                "tokens": set(identity["tokens"]),
                "aliases": set(identity["aliases"]),
                "alias_keys": {canonical_name(alias) for alias in identity["aliases"]},
                "promoter": identity["promoter"],
                "city": identity["city"],
                "zone": identity["zone"],
                "source": identity["source"],
            }
            groups.append(group)
        add_signal_to_group(group, signal)
    projects = [build_project(group["signals"], config) for group in groups]
    projects.sort(key=lambda project: (project.confidence_score, project.investment_score), reverse=True)
    return projects


def choose_name(signals: list[SignalEvent]) -> tuple[str, list[str]]:
    aliases: list[str] = []
    for signal in signals:
        aliases.extend(alias_candidates(signal))
    counts = Counter(canonical_name(alias) for alias in aliases if alias.strip())
    if not counts:
        return signals[0].source, [signals[0].source]
    best_key = counts.most_common(1)[0][0]
    normalized_to_display: dict[str, str] = {}
    for alias in aliases:
        normalized_to_display.setdefault(canonical_name(alias), alias)
    best_name = normalized_to_display.get(best_key, aliases[0])
    unique_aliases = list(dict.fromkeys(alias for alias in aliases if canonical_name(alias) == best_key or len(project_tokens(alias)) >= 2))
    return best_name, unique_aliases[:6]


def build_project(signals: list[SignalEvent], config: dict) -> ProjectRecord:
    signals.sort(key=lambda signal: signal.discovered_at)
    primary = [signal for signal in signals if signal.is_primary]
    exemplar = primary[0] if primary else signals[0]
    project_name, aliases = choose_name(signals)
    sources = sorted({signal.source for signal in signals})
    channels = sorted({signal.channel for signal in signals})
    source_urls = list(dict.fromkeys(signal.url for signal in signals))[:12]
    reasons: list[str] = []
    for signal in signals:
        reasons.extend(signal.reasons)
    unique_reasons = list(dict.fromkeys(reasons))[:10]
    prices = [signal.price_mad for signal in signals if signal.price_mad]
    promoter = exemplar.promoter_hint or next((signal.promoter_hint for signal in signals if signal.promoter_hint), None)
    city = exemplar.city_hint or next((signal.city_hint for signal in signals if signal.city_hint), None)
    zone = exemplar.zone_hint or next((signal.zone_hint for signal in signals if signal.zone_hint), None)
    asset_type = exemplar.asset_type_hint or next((signal.asset_type_hint for signal in signals if signal.asset_type_hint), None)
    timeline = [
        {
            "detected_at": signal.discovered_at,
            "channel": signal.channel,
            "source": signal.source,
            "title": signal.title[:160],
            "url": signal.url,
        }
        for signal in signals[:20]
    ]
    project = ProjectRecord(
        project_id=project_key(project_name, city, promoter),
        name=project_name,
        city=city,
        zone=zone,
        promoter=promoter,
        asset_type=asset_type,
        first_detected_at=signals[0].discovered_at,
        last_updated_at=signals[-1].discovered_at,
        launch_score=0,
        confidence_score=0,
        investment_score=0,
        urgency_score=0,
        recommendation="Watch",
        status="watch",
        summary="",
        prices={"min": min(prices) if prices else None, "max": max(prices) if prices else None},
        aliases=aliases,
        channels=channels,
        sources=sources,
        source_urls=source_urls,
        evidence={},
        reasons=unique_reasons,
        timeline=timeline,
        signals=signals,
    )
    return enrich_project(project, config)
