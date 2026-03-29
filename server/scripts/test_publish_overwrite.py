"""一次性自检：marker publish 重名 409 / overwrite。"""
from __future__ import annotations

import json
import shutil
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCORES_ROOT
from app.main import app

def main() -> None:
    c = TestClient(app)
    headers = {"Authorization": "Bearer dev-app-token-change-me"}
    sid = "_test_conflict_marker"
    d = SCORES_ROOT / sid
    if d.is_dir():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "data.json").write_text(
        json.dumps(
            {
                "songId": sid,
                "title": "t",
                "measures": [],
                "imageFile": "sheet.jpg",
                "audioFile": "audio.mp3",
            }
        ),
        encoding="utf-8",
    )

    data = {"song_id": sid, "title": "t", "overwrite": "false"}
    measure = {
        "id": 1,
        "startTimeMs": 0,
        "endTimeMs": 1000,
        "rect": {"x": 0, "y": 0, "w": 1, "h": 1},
    }
    dj = json.dumps({"songId": sid, "measures": [measure]}, ensure_ascii=False)
    files = [
        ("image", ("sheet.png", BytesIO(b"\x89PNG\r\n\x1a\n\x00"), "image/png")),
        ("audio", ("a.mp3", BytesIO(b"x" * 20), "audio/mpeg")),
        ("data_json", ("data.json", BytesIO(dj.encode("utf-8")), "application/json")),
    ]
    r = c.post("/api/marker/publish", headers=headers, data=data, files=files)
    assert r.status_code == 409, r.text

    data["overwrite"] = "true"
    files = [
        ("image", ("sheet.png", BytesIO(b"\x89PNG\r\n\x1a\n\x00"), "image/png")),
        ("audio", ("a.mp3", BytesIO(b"x" * 20), "audio/mpeg")),
        ("data_json", ("data.json", BytesIO(dj.encode("utf-8")), "application/json")),
    ]
    r2 = c.post("/api/marker/publish", headers=headers, data=data, files=files)
    assert r2.status_code == 200, r2.text

    shutil.rmtree(d)
    print("ok: 409 then 200")


if __name__ == "__main__":
    main()
