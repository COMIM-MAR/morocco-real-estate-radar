from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from .config import DOCS_DIR

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    PlaywrightTimeoutError = None
    sync_playwright = None


META_MEDIA_CAPTURE_ENABLED = os.getenv("META_MEDIA_CAPTURE_ENABLED", "1") != "0"
META_MEDIA_CAPTURE_HEADLESS = os.getenv("META_PLAYWRIGHT_HEADLESS", "1") != "0"
META_MEDIA_CAPTURE_TIMEOUT_MS = int(os.getenv("META_MEDIA_CAPTURE_TIMEOUT_MS", "15000"))
META_MEDIA_CAPTURE_WAIT_MS = int(os.getenv("META_MEDIA_CAPTURE_WAIT_MS", "2000"))
META_MEDIA_CAPTURE_LIMIT = int(os.getenv("META_MEDIA_CAPTURE_LIMIT", "1"))
META_STORAGE_STATE_PATH = os.getenv("META_STORAGE_STATE_PATH")
META_MEDIA_DIR = DOCS_DIR / "assets" / "meta"
META_USER_AGENT = "Mozilla/5.0 MoroccoRealEstateIntelligence/4.0"


def is_meta_library_url(url: str | None) -> bool:
    return bool(url and "facebook.com/ads/library" in url)


def is_renderable_remote_media(url: str | None) -> bool:
    if not url or not url.startswith("http"):
        return False
    if is_meta_library_url(url):
        return False
    return True


def local_asset_exists(url: str | None) -> bool:
    if not url or url.startswith(("http://", "https://", "data:")):
        return False
    normalized = str(url).lstrip("./")
    if normalized.startswith("../"):
        normalized = normalized[3:]
    asset_path = DOCS_DIR / normalized
    return asset_path.exists() and asset_path.stat().st_size > 0


def media_extension(url: str, default: str = ".jpg") -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"):
        if path.endswith(ext):
            return ext
    return default


def download_media_url(context, url: str, asset_path: Path) -> bool:
    if not url.startswith("http"):
        return False
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=META_MEDIA_CAPTURE_TIMEOUT_MS)
        if response is None:
            return False
        data = response.body()
    except Exception:
        return False
    finally:
        page.close()
    if not data:
        return False
    asset_path.write_bytes(data)
    return asset_path.exists() and asset_path.stat().st_size > 0


def project_meta_candidates(project) -> list[dict]:
    seen: set[str] = set()
    candidates: list[tuple[int, dict]] = []
    aliases = [alias.lower() for alias in (project.aliases or []) if alias]
    city = (project.city or "").lower()
    for signal in project.signals:
        if signal.collector != "ads.meta_ads":
            continue
        metadata = signal.metadata or {}
        ad_id = str(metadata.get("ad_id") or "").strip()
        if not ad_id or ad_id in seen:
            continue
        seen.add(ad_id)
        source_url = metadata.get("ad_snapshot_url") or signal.url
        if not is_meta_library_url(source_url):
            continue
        text = " ".join(
            part
            for part in [
                signal.title or "",
                signal.text or "",
                metadata.get("landing_page_url") or "",
                metadata.get("page_name") or "",
            ]
            if part
        ).lower()
        score = 0
        for alias in aliases:
            if alias and alias in text:
                score += 20
        if city and city in text:
            score += 6
        if "get offer" in text:
            score += 4
        if "video" in text and "problèmes pour lire cette vidéo" in text:
            score -= 8
        for term in GENERIC_PROMO_TERMS:
            if term in text:
                score -= 18
        candidates.append((score, {"ad_id": ad_id, "url": source_url}))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _score, candidate in candidates[:META_MEDIA_CAPTURE_LIMIT]]


def ad_media_candidates(page, ad_id: str) -> list[dict]:
    return page.locator("img,video").evaluate_all(
        """
        (els, adId) => {
          const allNodes = [...document.querySelectorAll('body *')];
          const anchors = allNodes
            .filter((node) => (node.innerText || '').includes(adId))
            .map((node) => {
              const rect = node.getBoundingClientRect();
              return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
            })
            .filter((rect) => rect.width > 0 && rect.height > 0);
          if (!anchors.length) return [];
          const anchor = anchors.sort((a, b) => a.top - b.top)[0];
          const candidates = [];
          for (const el of els) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const src = el.currentSrc || el.src || '';
            const poster = el.getAttribute('poster') || '';
            const mediaUrl = src || poster;
            const visible =
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              rect.width >= 120 &&
              rect.height >= 120;
            const invalid =
              !mediaUrl ||
              mediaUrl.startsWith('data:') ||
              mediaUrl.includes('emoji.php') ||
              mediaUrl.includes('static.xx.fbcdn.net/rsrc.php');
            if (!visible || invalid) continue;
            const sameColumn = Math.abs(rect.left - anchor.left) < 260;
            const overlapX = rect.left <= anchor.left + 520 && rect.left + rect.width >= anchor.left - 40;
            const underAnchor = rect.top >= anchor.top - 80 && rect.top <= anchor.top + 900;
            if (!(sameColumn || overlapX) || !underAnchor) continue;
            candidates.push({
              tag: el.tagName.toLowerCase(),
              url: mediaUrl,
              poster,
              width: Math.round(rect.width),
              height: Math.round(rect.height),
              left: Math.round(rect.left),
              top: Math.round(rect.top),
              score: Math.round(rect.width * rect.height - Math.abs(rect.left - anchor.left) * 10 - Math.abs(rect.top - anchor.top) * 2),
            });
          }
          return candidates.sort((a, b) => b.score - a.score).slice(0, 4);
        }
        """,
        ad_id,
    )


def anchored_ad_media_url(page, ad_id: str) -> str | None:
    try:
        targets = page.locator(f"text={ad_id}")
        count = min(targets.count(), 6)
    except Exception:
        return None
    for index in range(count):
        try:
            media_url = targets.nth(index).evaluate(
                """
                (el) => {
                  let node = el;
                  while (node && node !== document.body) {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    const text = node.innerText || '';
                    const idMentions = (text.match(/ID dans la bibliothèque/g) || []).length;
                    const visible =
                      style.display !== 'none' &&
                      style.visibility !== 'hidden' &&
                      rect.width >= 260 &&
                      rect.width <= 900 &&
                      rect.height >= 220 &&
                      rect.height <= 1800;
                    const media = [...node.querySelectorAll('img,video')]
                      .map((child) => {
                        const childRect = child.getBoundingClientRect();
                        const src = child.currentSrc || child.src || child.getAttribute('poster') || '';
                        const childVisible =
                          childRect.width >= 120 &&
                          childRect.height >= 120 &&
                          src &&
                          !src.startsWith('data:') &&
                          !src.includes('emoji.php') &&
                          !src.includes('static.xx.fbcdn.net/rsrc.php');
                        if (!childVisible) return null;
                        return {
                          url: src,
                          area: childRect.width * childRect.height,
                        };
                      })
                      .filter(Boolean)
                      .sort((a, b) => b.area - a.area);
                    if (visible && idMentions <= 1 && media.length) {
                      return media[0].url;
                    }
                    node = node.parentElement;
                  }
                  return null;
                }
                """
            )
        except Exception:
            media_url = None
        if isinstance(media_url, str) and media_url.startswith("http"):
            return media_url
    return None


def fetch_meta_asset_url(context, source_url: str, ad_id: str) -> str | None:
    page = context.new_page()
    try:
        page.goto(source_url, wait_until="domcontentloaded", timeout=META_MEDIA_CAPTURE_TIMEOUT_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=min(META_MEDIA_CAPTURE_TIMEOUT_MS, 15000))
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(META_MEDIA_CAPTURE_WAIT_MS)
        anchored_url = anchored_ad_media_url(page, ad_id)
        if anchored_url:
            return anchored_url
        for candidate in ad_media_candidates(page, ad_id):
            media_url = candidate.get("url") or candidate.get("poster") or ""
            if media_url.startswith("http"):
                return media_url
        return None
    except Exception:
        return None
    finally:
        page.close()


def attach_meta_media_assets(projects: list) -> list:
    for project in projects:
        current_images = [
            url
            for url in (project.evidence.get("images") or [])
            if is_renderable_remote_media(url) or local_asset_exists(url)
        ]
        current_videos = [url for url in (project.evidence.get("videos") or []) if is_renderable_remote_media(url)]
        project.evidence["images"] = current_images
        project.evidence["videos"] = current_videos

    if not META_MEDIA_CAPTURE_ENABLED or sync_playwright is None:
        return projects

    tasks: list[tuple[object, str, str]] = []
    META_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    for project in projects:
        asset_urls: list[str] = []
        for candidate in project_meta_candidates(project):
            ad_id = candidate["ad_id"]
            existing = sorted(META_MEDIA_DIR.glob(f"meta-ad-{ad_id}.*"))
            if existing and existing[0].stat().st_size > 0:
                asset_urls.append(f"assets/meta/{existing[0].name}")
            else:
                tasks.append((project, ad_id, candidate["url"]))
        if asset_urls:
            project.evidence["images"] = asset_urls + project.evidence.get("images", [])

    if not tasks:
        return projects

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=META_MEDIA_CAPTURE_HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context_kwargs = {
            "locale": "fr-FR",
            "user_agent": META_USER_AGENT,
            "viewport": {"width": 1440, "height": 2200},
        }
        if META_STORAGE_STATE_PATH and Path(META_STORAGE_STATE_PATH).exists():
            context_kwargs["storage_state"] = META_STORAGE_STATE_PATH
        context = browser.new_context(**context_kwargs)
        try:
            for project, ad_id, candidate_url in tasks:
                media_url = fetch_meta_asset_url(context, candidate_url, ad_id)
                if not media_url:
                    continue
                ext = media_extension(media_url)
                asset_path = META_MEDIA_DIR / f"meta-ad-{ad_id}{ext}"
                rel_url = f"assets/meta/{asset_path.name}"
                if download_media_url(context, media_url, asset_path):
                    project.evidence["images"] = [rel_url] + project.evidence.get("images", [])
        finally:
            context.close()
            browser.close()

    for project in projects:
        deduped: list[str] = []
        seen: set[str] = set()
        for url in project.evidence.get("images", []):
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        project.evidence["images"] = deduped

    return projects
GENERIC_PROMO_TERMS = [
    "tirage au sort",
    "séjour",
    "offre exclusive",
    "coupe du monde",
    "bon d'achat",
    "pack électroménager",
    "hotel escale smir",
]
