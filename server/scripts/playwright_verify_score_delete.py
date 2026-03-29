"""
端到端验证删除曲包：拉起 uvicorn → 写入可上架(ready)测试目录 → POST /api/scores 删除 →
再对现有 data/scores 下一套乐谱执行删除（默认删目录名 111，可通过环境变量指定或不删）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ.get("APP_TOKEN", "dev-app-token-change-me")
PORT = int(os.environ.get("YUEPU_VERIFY_PORT", "8778"))
# 置空可跳过「删除已有乐谱」一步
OPTIONAL_DELETE_FOLDER = os.environ.get("YUEPU_DELETE_EXISTING_FOLDER", "111")


def _wait_health(base: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/health", timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.15)
    raise TimeoutError("health check failed: " + base)


def _make_ready_package(scores_root: Path, folder: str) -> None:
    d = scores_root / folder
    if d.is_dir():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    obj = {
        "songId": folder,
        "title": folder,
        "imageFile": "sheet.jpg",
        "audioFile": "audio.mp3",
        "measures": [{"id": 1, "startTimeMs": 0, "endTimeMs": 1000}],
    }
    (d / "data.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "sheet.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (d / "audio.mp3").write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("需要: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    sys.path.insert(0, str(ROOT))
    from app.config import SCORES_ROOT

    test_folder = "__pw_verify_del__"
    _make_ready_package(SCORES_ROOT, test_folder)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{PORT}"
    lines: list[str] = []

    try:
        _wait_health(base)
        lines.append(f"OK uvicorn {base}")

        with sync_playwright() as p:
            req = p.request.new_context(
                base_url=base,
                extra_http_headers={"Authorization": f"Bearer {TOKEN}"},
            )
            lst = req.get("/api/scores?ready=true")
            lines.append(f"GET /api/scores?ready=true -> {lst.status} ({lst.text()[:120]})...")
            if lst.status != 200:
                return 2

            body = json.dumps(
                {"action": "delete", "folderId": test_folder, "song_id": test_folder},
            )
            r = req.post(
                "/api/scores",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            lines.append(f"POST /api/scores delete fixture -> {r.status} {r.text()}")
            if r.status != 200:
                return 3
            if (SCORES_ROOT / test_folder).exists():
                lines.append("FAIL: fixture folder still exists")
                return 4
            lines.append("OK fixture folder removed on disk")

            # 首页同路径：浏览器里用 fetch；此处再用 APIRequest 模拟
            bogus = req.post(
                "/api/scores",
                data=json.dumps({"action": "delete", "folderId": "___no_such___"}),
                headers={"Content-Type": "application/json"},
            )
            lines.append(f"POST delete missing -> {bogus.status} (expect 404)")

            if OPTIONAL_DELETE_FOLDER.strip():
                exist = SCORES_ROOT / OPTIONAL_DELETE_FOLDER.strip()
                if exist.is_dir():
                    ex = req.post(
                        "/api/scores",
                        data=json.dumps(
                            {
                                "action": "delete",
                                "folderId": OPTIONAL_DELETE_FOLDER.strip(),
                            },
                        ),
                        headers={"Content-Type": "application/json"},
                    )
                    lines.append(
                        f"POST delete existing '{OPTIONAL_DELETE_FOLDER}' -> {ex.status} {ex.text()[:200]}",
                    )
                    if ex.status != 200:
                        lines.append("(若该套目录已不存在，404 可忽略)")
                else:
                    lines.append(f"skip optional delete: folder {OPTIONAL_DELETE_FOLDER!r} not on disk")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(SCORES_ROOT / test_folder, ignore_errors=True)

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
