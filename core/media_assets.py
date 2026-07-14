from __future__ import annotations

import os
from pathlib import Path

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


def project_meta_candidates(project) -> list[dict]:
    seen: set[str] = set()
    candidates: list[dict] = []
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
        candidates.append({"ad_id": ad_id, "url": source_url})
    return candidates[:META_MEDIA_CAPTURE_LIMIT]


def choose_best_media_locator(page):
    return page.locator("img, video").evaluate_all(
        """
        els => {
          let best = null;
          for (const el of els) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const src = el.currentSrc || el.src || el.getAttribute('poster') || '';
            const visible =
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              rect.width >= 220 &&
              rect.height >= 220 &&
              rect.top < window.innerHeight &&
              rect.bottom > 0;
            const invalid =
              !src ||
              src.startsWith('data:') ||
              src.includes('emoji.php') ||
              src.includes('static.xx.fbcdn.net/rsrc.php');
            if (!visible || invalid) continue;
            const score = (rect.width * rect.height) + (el.tagName === 'VIDEO' ? 100000 : 0);
            if (!best || score > best.score) {
              best = { score, tag: el.tagName.toLowerCase() };
            }
          }
          if (!best) return null;
          for (const el of els) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const src = el.currentSrc || el.src || el.getAttribute('poster') || '';
            const score = (rect.width * rect.height) + (el.tagName === 'VIDEO' ? 100000 : 0);
            const visible =
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              rect.width >= 220 &&
              rect.height >= 220 &&
              rect.top < window.innerHeight &&
              rect.bottom > 0;
            const invalid =
              !src ||
              src.startsWith('data:') ||
              src.includes('emoji.php') ||
              src.includes('static.xx.fbcdn.net/rsrc.php');
            if (visible && !invalid && score === best.score) {
              el.setAttribute('data-radar-capture', '1');
              return best.tag;
            }
          }
          return null;
        }
        """
    )


def ad_card_clip(page, ad_id: str) -> dict | None:
    try:
        targets = page.locator(f"text={ad_id}")
        count = min(targets.count(), 6)
    except Exception:
        return None
    for index in range(count):
        try:
            clip = targets.nth(index).evaluate(
                """
                (el) => {
                  el.scrollIntoView({block: 'center', inline: 'nearest'});
                  const rect = el.getBoundingClientRect();
                  const viewportWidth = window.innerWidth;
                  const viewportHeight = window.innerHeight;
                  if (!rect || rect.width <= 0 || rect.height <= 0) return null;
                  const x = Math.max(0, rect.left - 12);
                  const y = Math.max(0, rect.top - 56);
                  const width = Math.min(viewportWidth - x - 16, 620);
                  const height = Math.min(viewportHeight - y - 16, 820);
                  if (width < 260 || height < 260) return null;
                  return {
                    x: x + window.scrollX,
                    y: y + window.scrollY,
                    width,
                    height,
                  };
                }
                """
            )
        except Exception:
            clip = None
        if clip:
            return clip
    return None


def capture_ad_card(page, ad_id: str, asset_path: Path) -> bool:
    clip = ad_card_clip(page, ad_id)
    if not clip:
        return False
    try:
        page.screenshot(path=str(asset_path), clip=clip)
    except Exception:
        return False
    return asset_path.exists() and asset_path.stat().st_size > 0


def capture_visible_page(page, asset_path: Path) -> bool:
    try:
        page.screenshot(path=str(asset_path), full_page=False)
    except Exception:
        return False
    return asset_path.exists() and asset_path.stat().st_size > 0


def capture_meta_asset(context, source_url: str, ad_id: str, asset_path: Path) -> bool:
    page = context.new_page()
    try:
        page.goto(source_url, wait_until="domcontentloaded", timeout=META_MEDIA_CAPTURE_TIMEOUT_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=min(META_MEDIA_CAPTURE_TIMEOUT_MS, 15000))
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(META_MEDIA_CAPTURE_WAIT_MS)
        if capture_ad_card(page, ad_id, asset_path):
            return True
        return capture_visible_page(page, asset_path)
    except Exception:
        return False
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

    tasks: list[tuple[object, str, str, Path]] = []
    META_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    for project in projects:
        asset_urls: list[str] = []
        for candidate in project_meta_candidates(project):
            ad_id = candidate["ad_id"]
            rel_url = f"assets/meta/meta-ad-{ad_id}.png"
            asset_path = META_MEDIA_DIR / f"meta-ad-{ad_id}.png"
            if asset_path.exists() and asset_path.stat().st_size > 0:
                asset_urls.append(rel_url)
            else:
                tasks.append((project, ad_id, rel_url, asset_path))
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
            for project, ad_id, rel_url, asset_path in tasks:
                candidate_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA&id={ad_id}"
                if capture_meta_asset(context, candidate_url, ad_id, asset_path):
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
