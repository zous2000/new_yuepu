"""Open pages and print console / page errors. Usage: cd server && python scripts/playwright_page_errors.py"""
from __future__ import annotations

import sys

BASE = "http://127.0.0.1:8000"
PATHS = ["/marker/", "/viewer/", "/"]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    all_lines: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        buffer: list[str] = []

        def on_console(msg):
            if msg.type in ("error", "warning"):
                buffer.append(f"console.{msg.type}: {msg.text}")

        def on_page_error(exc):
            buffer.append(f"pageerror: {exc}")

        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        for path in PATHS:
            buffer.clear()
            url = BASE.rstrip("/") + path
            print("===", url, "===")
            try:
                page.goto(url, wait_until="networkidle", timeout=45_000)
            except Exception as e:
                buffer.append(f"goto: {e}")
            page.wait_for_timeout(1000)
            for line in buffer:
                print(line)
                all_lines.append(f"{url} -> {line}")

        browser.close()

    if all_lines:
        print("\n--- SUMMARY ---", file=sys.stderr)
        for line in all_lines:
            print(line, file=sys.stderr)
        return 2
    print("OK: no console errors/warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
