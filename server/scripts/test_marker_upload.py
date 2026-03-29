"""Quick check: POST /api/marker/upload then GET image/audio bytes."""
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
TOKEN = "dev-app-token-change-me"

jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x00"

boundary = "----Boundary" + uuid.uuid4().hex


def part(name: str, filename: str, ctype: str, data: bytes) -> bytes:
    h = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode()
    return h + data + b"\r\n"


body = part("image", "t.jpg", "image/jpeg", jpg) + part("audio", "a.mp3", "audio/mpeg", mp3)
body += f"--{boundary}--\r\n".encode()

req = Request(
    f"{BASE}/api/marker/upload",
    data=body,
    method="POST",
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {TOKEN}",
    },
)

try:
    with urlopen(req, timeout=8) as r:
        assert r.status == 200
        j = json.loads(r.read().decode())
        print("upload ok:", j)
        for key in ("imageUrl", "audioUrl"):
            path = j[key]
            assert path.startswith("/api/marker/asset/") or path.startswith("/marker-assets/"), path
            u = BASE + path if path.startswith("/") else path
            with urlopen(u, timeout=8) as r2:
                data = r2.read()
                print(key, r2.status, r2.headers.get("Content-Type"), "bytes", len(data))
except HTTPError as e:
    print("HTTPError", e.code, e.read()[:800].decode(errors="replace"))
except URLError as e:
    print("URLError — is uvicorn running?", e.reason)
