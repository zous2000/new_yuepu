"""Marker page: set files, token, click 预览, collect errors."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BASE = "http://127.0.0.1:8000"

# minimal valid-ish files
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return 1

    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "p.jpg"
        aud = Path(td) / "a.mp3"
        img.write_bytes(JPG)
        aud.write_bytes(MP3)

        errors: list[str] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            def on_console(m):
                if m.type in ("error", "warning"):
                    errors.append(f"{m.type}: {m.text}")

            page.on("console", on_console)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            page.goto(f"{BASE}/marker/", wait_until="networkidle", timeout=60_000)
            page.fill("#appTokenMarker", "dev-app-token-change-me")
            page.fill("#songId", "playwright_test")
            page.set_input_files("#imgFile", str(img))
            page.set_input_files("#audioFile", str(aud))
            page.click("#btnPreview")

            for _ in range(40):
                page.wait_for_timeout(250)
                if "/viewer/" in page.url:
                    break
            print("URL after preview:", page.url[:120])
            st = page.locator("#status").inner_text()
            print("status (last marker if not navigated):", (st or "")[:300])
            browser.close()

    for e in errors:
        print("ERR", e, file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
