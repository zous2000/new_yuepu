import mimetypes
import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

MARKER_TEMP = Path(__file__).resolve().parent.parent / "data" / "marker_temp"

SESSION_RE = re.compile(r"^[a-f0-9]{32}$")


def ensure_marker_temp() -> None:
    MARKER_TEMP.mkdir(parents=True, exist_ok=True)


def marker_asset_response(session: str, filename: str) -> FileResponse:
    if not SESSION_RE.fullmatch(session):
        raise HTTPException(status_code=404, detail="Not found")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Not found")
    root = MARKER_TEMP.resolve()
    base = (MARKER_TEMP / session).resolve()
    if base.parent != root:
        raise HTTPException(status_code=404, detail="Not found")
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Not found")
    target = (base / filename).resolve()
    if target.parent != base:
        raise HTTPException(status_code=404, detail="Not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(target, media_type=media_type or "application/octet-stream")
