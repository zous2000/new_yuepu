"""
曲谱猫：验证下载接口与打点小工具列表缓存（需网络）。

用法（在 server 目录下）:
  pip install -r requirements-dev.txt
  playwright install chromium
  python e2e/run_qupumao_playwright.py

会拉起本机 uvicorn（临时端口），随后用 Playwright 测 API 与 /marker/ 页面。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
PORT = "18765"
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = os.environ.get("APP_TOKEN", "dev-app-token-change-me")


def main() -> int:
    if not SERVER_DIR.joinpath("app", "main.py").is_file():
        print("请在 yuepuapp/server 目录下运行本脚本。", file=sys.stderr)
        return 2

    env = {**os.environ, "APP_TOKEN": TOKEN}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            PORT,
        ],
        cwd=str(SERVER_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                import urllib.request

                urllib.request.urlopen(f"{BASE}/health", timeout=2)
                break
            except OSError:
                time.sleep(0.4)
        else:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            print("uvicorn 未就绪", err[:500], file=sys.stderr)
            return 3

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context()
            # --- API：POST download 应返回图片字节 ---
            resp = ctx.request.post(
                f"{BASE}/api/marker/qupumao/download",
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({"path": "/qupu/stcelsmg.html"}),
                timeout=180_000,
            )
            if resp.status != 200:
                print("download API:", resp.status, resp.text()[:300], file=sys.stderr)
                return 4
            body = resp.body()
            if len(body) < 2000:
                print("download API: 正文过短", len(body), file=sys.stderr)
                return 5
            ct = (resp.headers.get("content-type") or "").lower()
            if "image" not in ct:
                print("download API: 非 image Content-Type:", ct, file=sys.stderr)
                return 6

            # --- 页面：搜索后应出现至少一行成功标记 ✓ ---
            page = ctx.new_page()
            page.set_default_timeout(120_000)
            page.goto(f"{BASE}/marker/", wait_until="domcontentloaded")
            # Token 输入框在「精简界面」下被隐藏，但初始化脚本会写入默认 APP_TOKEN
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('appTokenMarker');
                  return el && (el.value || '').trim().length > 0;
                }""",
                timeout=30_000,
            )
            page.locator("#btnQupumaoSearch").click()
            page.locator("#qupumaoQuery").fill("三套车")
            page.locator("#qupumaoDoSearch").click()
            ok = page.locator("#qupumaoResults li .qupumao-row-status", has_text="✓")
            ok.first.wait_for(state="visible", timeout=120_000)
            if ok.count() < 1:
                print("列表未出现成功缓存行（✓）", file=sys.stderr)
                return 7

            browser.close()

        print("qupumao Playwright 验证通过（API + /marker/ 列表缓存）。")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
