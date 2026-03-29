"""
自动打开打点页、选图/音频、点上传，打印状态区与控制台日志，并截图。
前置：pip install playwright && playwright install chromium
用法：
  cd server
  python scripts/playwright_marker_debug.py --image C:\\aaa\\123.jpg --audio C:\\aaa\\123.mp3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端根地址")
    parser.add_argument("--image", type=Path, required=True, help="谱面图片路径")
    parser.add_argument("--audio", type=Path, required=True, help="音频路径")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口（默认无头）")
    parser.add_argument("--out", type=Path, default=Path("marker-playwright-debug.png"), help="截图路径")
    args = parser.parse_args()

    if not args.image.is_file():
        print("ERROR: 图片不存在:", args.image, file=sys.stderr)
        return 2
    if not args.audio.is_file():
        print("ERROR: 音频不存在:", args.audio, file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: 未安装 playwright。在 server 目录执行：\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1

    base = args.base_url.rstrip("/")
    url = f"{base}/marker/?pwdebug=1"

    logs: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        def on_console(msg) -> None:
            line = f"[{msg.type}] {msg.text}"
            logs.append(line)
            print("CONSOLE", line)

        def on_request_failed(req) -> None:
            print("REQ_FAIL", req.url, req.failure)

        page.on("console", on_console)
        page.on("requestfailed", on_request_failed)

        def on_page_error(exc) -> None:
            print("PAGEERROR", exc)

        page.on("pageerror", on_page_error)

        print("GOTO", url)
        page.goto(url, wait_until="load", timeout=60_000)

        ver = page.locator("h1").inner_text(timeout=10_000)
        print("H1:", ver[:120])
        print("overlay nodes:", page.locator("#overlay").count())
        print("pre-preview markerPreviewClick:", page.evaluate("() => typeof window.markerPreviewClick"))

        if not page.locator("#btnPreview").count():
            print("ERROR: 找不到 #btnPreview", file=sys.stderr)
            browser.close()
            return 3

        has_handler = page.evaluate("() => typeof window.markerPreviewClick === 'function'")
        print("window.markerPreviewClick is function:", has_handler)

        page.set_input_files("#imgFile", str(args.image.resolve()))
        page.set_input_files("#audioFile", str(args.audio.resolve()))

        upload_status: dict[str, object] = {}

        def on_response(resp) -> None:
            u = resp.url
            if "/api/marker/stage" in u and resp.request.method == "POST":
                upload_status["status"] = resp.status
                upload_status["url"] = u
                try:
                    upload_status["body"] = resp.text()
                except Exception as e:
                    upload_status["body"] = f"<read error {e}>"

        page.on("response", on_response)

        page.fill("#appTokenMarker", "dev-app-token-change-me")
        page.fill("#songId", "pwdebug_song")
        page.click("#btnPreview")

        for i in range(120):
            page.wait_for_timeout(500)
            if upload_status:
                print("STAGE HTTP", upload_status.get("status"), upload_status.get("url"))
                body = upload_status.get("body")
                if isinstance(body, str):
                    print("STAGE BODY", body[:800])
                break
            if i % 10 == 0 and i:
                st = page.locator("#status").inner_text()
                print(f"... waiting stage ({i * 0.5:.0f}s) status={st[:80]!r}")
        else:
            print(
                "WARN: 未捕获到 POST /api/marker/stage（可能被拦截或 Token/网络失败）。",
                file=sys.stderr,
            )

        page.wait_for_timeout(1500)

        status = page.locator("#status").inner_text()
        print("--- #status ---")
        print(status or "(empty)")

        dbg = page.locator("#debugLog")
        if dbg.count():
            print("--- #debugLog ---")
            print(dbg.inner_text() or "(empty)")

        page.screenshot(path=str(args.out), full_page=True)
        print("SCREENSHOT", args.out.resolve())

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
