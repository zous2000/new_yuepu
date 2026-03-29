"""调试：用 Playwright 校验 POST /api/delete-score（避免 /api/scores/delete 与 GET .../{filename:path} 路由混淆导致 405）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE = os.environ.get("YUEPU_TEST_BASE", "http://127.0.0.1:8000")
TOKEN = "dev-app-token-change-me"


def _scores_root():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from app.config import SCORES_ROOT

    return SCORES_ROOT


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请安装: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    SCORES_ROOT = _scores_root()
    fid = "_pw_del_test_"
    pdir = SCORES_ROOT / fid
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "data.json").write_text(
        json.dumps(
            {
                "songId": fid,
                "title": "pw_del",
                "measures": [{"id": 1, "startTimeMs": 0, "endTimeMs": 1000}],
                "imageFile": "a.jpg",
                "audioFile": "a.mp3",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pdir / "a.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (pdir / "a.mp3").write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00")

    try:
        with sync_playwright() as p:
            req = p.request.new_context(
                base_url=BASE,
                extra_http_headers={"Authorization": f"Bearer {TOKEN}"},
            )
            post = req.post(
                "/api/delete-score",
                data=json.dumps({"song_id": fid}),
                headers={"Content-Type": "application/json"},
            )
            print("POST /api/delete-score", post.status, post.text())
            if post.status != 200:
                return 2

            post_empty = req.post(
                "/api/delete-score",
                data=json.dumps({"song_id": fid}),
                headers={"Content-Type": "application/json"},
            )
            print("POST again (expect 404)", post_empty.status, post_empty.text())

            # 可选：对比 DELETE（若此处为 405，多为上游只允许 GET/POST）
            pdir.mkdir(parents=True, exist_ok=True)
            (pdir / "data.json").write_text('{"songId":"%s","title":"x","measures":[1],"imageFile":"a.jpg","audioFile":"a.mp3"}' % fid, encoding="utf-8")
            (pdir / "a.jpg").write_bytes(b"x")
            (pdir / "a.mp3").write_bytes(b"x")
            dele = req.delete(f"/api/scores/{fid}")
            print("DELETE /api/scores/{id}", dele.status, dele.text()[:120])
    finally:
        import shutil

        shutil.rmtree(pdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
