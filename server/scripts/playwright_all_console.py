"""Print all browser console messages for key pages."""
from __future__ import annotations

import sys

BASE = "http://127.0.0.1:8000"
URLS = [
    f"{BASE}/marker/",
    f"{BASE}/viewer/",
    f"{BASE}/",
]


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_console(m):
            print(f"  [{m.type}] {m.text}")

        page.on("console", on_console)
        page.on("pageerror", lambda e: print(f"  PAGEERROR {e}"))

        for url in URLS:
            print("===", url)
            page.goto(url, wait_until="load", timeout=60_000)
            page.wait_for_timeout(1500)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
