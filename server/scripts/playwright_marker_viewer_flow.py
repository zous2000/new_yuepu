"""POST /api/marker/stage then open viewer with markerSession; print JS errors."""
from __future__ import annotations

import sys
from io import BytesIO

import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
TOKEN = "dev-app-token-change-me"
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00"


def multipart_body(boundary: str, parts: list[tuple[str, str, str, bytes]]) -> bytes:
    b = b""
    for name, filename, ctype, data in parts:
        b += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n'
        ).encode()
        b += data + b"\r\n"
    b += f"--{boundary}--\r\n".encode()
    return b


def stage_session() -> str:
    import uuid

    boundary = "----Boundary" + uuid.uuid4().hex
    data = multipart_body(
        boundary,
        [
            ("image", "t.jpg", "image/jpeg", JPG),
            ("audio", "a.mp3", "audio/mpeg", MP3),
            (
                "data_json",
                "data.json",
                "application/json",
                b'{"songId":"t","title":"t","imageFile":"sheet.jpg","audioFile":"audio.mp3","measures":[]}',
            ),
        ],
    )
    req = urllib.request.Request(
        f"{BASE}/api/marker/stage",
        data=data,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {TOKEN}",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        import json

        j = json.loads(r.read().decode())
    return j["session"]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright", file=sys.stderr)
        return 1

    try:
        sid = stage_session()
    except Exception as e:
        print("stage failed:", e, file=sys.stderr)
        return 3

    url = f"{BASE}/viewer/?markerSession={sid}&minimal=1"
    print("OPEN", url)

    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_console(m):
            if m.type in ("error", "warning"):
                errors.append(f"{m.type}: {m.text}")

        page.on("console", on_console)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        page.goto(url, wait_until="networkidle", timeout=60_000)
        st = page.locator("#status").inner_text(timeout=10_000)
        tt = page.locator("#scoreTitle").inner_text(timeout=10_000)
        print("status:", (st or "")[:200])
        print("scoreTitle:", (tt or "")[:200])
        page.wait_for_timeout(2000)
        browser.close()

    for e in errors:
        print("ERR", e, file=sys.stderr)
    return 3 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
