from __future__ import annotations

import os
import time
from pathlib import Path


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:  # pragma: no cover
        raise SystemExit("Playwright is required. Run: python -m pip install -r requirements.txt && python -m playwright install chromium") from error

    output_path = Path(os.getenv("META_STORAGE_STATE_PATH", "secrets/meta-storage-state.json")).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Opening Chromium for Meta login...")
    print("1. Log in to Facebook/Meta if needed")
    print("2. Open Meta Ad Library and confirm it loads")
    print("3. Leave the browser open while the session is being saved automatically")
    print("4. Close the browser window when you are done")

    with sync_playwright() as engine:
        browser = engine.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            locale="fr-FR",
            viewport={"width": 1440, "height": 1800},
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA", wait_until="domcontentloaded")
        print(f"\nAuto-saving storage state to:\n{output_path}\n")
        while True:
            if not context.pages:
                break
            context.storage_state(path=str(output_path))
            time.sleep(3)
        context.storage_state(path=str(output_path))
        context.close()
        browser.close()

    print(f"Saved storage state to {output_path}")
    print("Recommended next step:")
    print(f"base64 < {output_path}")


if __name__ == "__main__":
    main()
