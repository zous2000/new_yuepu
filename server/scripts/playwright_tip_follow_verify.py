from __future__ import annotations

import json
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OPEN_ID = "我的祖国"


def main() -> int:
    url = f"{BASE}/viewer/?open={urllib.parse.quote(OPEN_ID)}&minimal=1"
    print("OPEN", url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="networkidle", timeout=60_000)
        page.wait_for_function("() => !!document.getElementById('sheet') && document.getElementById('sheet').naturalWidth > 0")

        page.click("#btnTipMode")
        page.wait_for_timeout(500)
        page.click("#btnTipFollow")
        page.wait_for_timeout(500)

        debug = page.evaluate(
            """
            () => {
              const wrap = document.getElementById("wrap");
              const sheet = document.getElementById("sheet");
              const player = document.getElementById("player");
              const tMs = 15000;
              player.currentTime = tMs / 1000;
              player.dispatchEvent(new Event("seeked"));
              player.dispatchEvent(new Event("timeupdate"));
              if (typeof drawOverlay === "function") drawOverlay();
              if (typeof scrollActiveMeasureToCenter === "function") scrollActiveMeasureToCenter();

              const hit = (typeof findMeasureForHighlightAt === "function") ? findMeasureForHighlightAt(tMs) : null;
              const sr = sheet.getBoundingClientRect();
              const wr = wrap.getBoundingClientRect();
              if (!hit || !hit.m) {
                return { hasHit: false, wrap: { left: wr.left, top: wr.top, right: wr.right, bottom: wr.bottom } };
              }

              const naturalW = sheet.naturalWidth || 1;
              const naturalH = sheet.naturalHeight || 1;
              const m = hit.m;
              const scaleX = sr.width / naturalW;
              const scaleY = sr.height / naturalH;
              const cx = sr.left + (m.rect.x + m.rect.w / 2) * scaleX;
              const cy = sr.top + (m.rect.y + m.rect.h / 2) * scaleY;
              const inWrap = cx >= wr.left && cx <= wr.right && cy >= wr.top && cy <= wr.bottom;

              return {
                hasHit: true,
                index: hit.i,
                measureStartMs: m.startTimeMs,
                measureEndMs: m.endTimeMs,
                center: { x: cx, y: cy },
                wrap: { left: wr.left, top: wr.top, right: wr.right, bottom: wr.bottom, centerX: (wr.left + wr.right) / 2, centerY: (wr.top + wr.bottom) / 2 },
                inWrap,
                scroll: { left: wrap.scrollLeft, top: wrap.scrollTop },
              };
            }
            """
        )

        shot = "server/scripts/playwright_tip_follow_verify.png"
        page.screenshot(path=shot, full_page=False)
        browser.close()

    print("DEBUG", json.dumps(debug, ensure_ascii=False))
    print("SCREENSHOT", shot)
    return 0 if debug.get("hasHit") else 2


if __name__ == "__main__":
    raise SystemExit(main())

