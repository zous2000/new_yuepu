"""Quick check: POST /api/delete-score + DELETE /api/scores/{id}."""
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import SCORES_ROOT
from app.main import app

client = TestClient(app)
headers = {"Authorization": "Bearer dev-app-token-change-me"}

fid = "_del_test_"
p = SCORES_ROOT / fid
p.mkdir(parents=True, exist_ok=True)
(p / "data.json").write_text(
    '{"songId":"%s","title":"t","measures":[],"imageFile":"a.jpg","audioFile":"a.mp3"}' % fid,
    encoding="utf-8",
)
(p / "a.jpg").write_bytes(b"")
(p / "a.mp3").write_bytes(b"")

r = client.post(
    "/api/scores",
    headers={**headers, "Content-Type": "application/json"},
    json={"action": "delete", "folderId": fid, "song_id": fid},
)
print("POST /api/scores action=delete", r.status_code, r.text)

r2 = client.get(f"/api/scores/{fid}/data.json", headers=headers)
print("GET nested after POST delete", r2.status_code)

# DELETE 路径仍可用
p.mkdir(parents=True, exist_ok=True)
(p / "data.json").write_text(
    '{"songId":"%s","title":"t","measures":[],"imageFile":"a.jpg","audioFile":"a.mp3"}' % fid,
    encoding="utf-8",
)
(p / "a.jpg").write_bytes(b"")
(p / "a.mp3").write_bytes(b"")
r3 = client.delete(f"/api/scores/{fid}", headers=headers)
print("DELETE /api/scores/{id}", r3.status_code, r3.text)

shutil.rmtree(p, ignore_errors=True)
