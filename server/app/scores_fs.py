import json
import shutil
import subprocess
from pathlib import Path

from pypinyin import Style, lazy_pinyin

from .config import SCORES_ROOT


def ensure_scores_root() -> None:
    SCORES_ROOT.mkdir(parents=True, exist_ok=True)


def title_pinyin_initial(title: str) -> str:
    """曲目展示名首字的拼音首字母 A–Z；英文取首字母；数字/其它为 #。"""
    t = (title or "").strip()
    if not t:
        return "#"
    ch = t[0]
    if ch.isascii() and ch.isalpha():
        return ch.upper()
    if ch.isascii() and ch.isdigit():
        return "#"
    try:
        initials = lazy_pinyin(ch, style=Style.FIRST_LETTER)
        if initials and initials[0]:
            c = (initials[0][0] or "").upper()
            if "A" <= c <= "Z":
                return c
    except Exception:
        pass
    return "#"


def list_scores_manifest(*, only_ready: bool = False) -> list[dict]:
    """only_ready=True 时仅含：至少 1 个小节、谱图与音频文件均存在（供首页曲库）。"""
    ensure_scores_root()
    out: list[dict] = []
    for d in sorted(SCORES_ROOT.iterdir()):
        if not d.is_dir():
            continue
        data_path = d / "data.json"
        if not data_path.is_file():
            continue
        try:
            raw = json.loads(data_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        song_id = raw.get("songId") or d.name
        title = raw.get("title") or song_id
        measures = raw.get("measures")
        if not isinstance(measures, list):
            measures = []
        image_name = raw.get("imageFile", "sheet.jpg")
        audio_name = raw.get("audioFile", "audio.mp3")
        if only_ready:
            if len(measures) == 0:
                continue
            if not (d / image_name).is_file() or not (d / audio_name).is_file():
                continue
        updated_at = int(data_path.stat().st_mtime * 1000)
        sid = d.name
        title_initial = title_pinyin_initial(title)
        out.append(
            {
                "songId": song_id,
                "folderId": sid,
                "title": title,
                "titleInitial": title_initial,
                "measureCount": len(measures),
                "updatedAt": updated_at,
                "files": {
                    "data": f"/api/scores/{sid}/data.json",
                    "image": f"/api/scores/{sid}/{image_name}",
                    "audio": f"/api/scores/{sid}/{audio_name}",
                },
            }
        )
    return out


def score_dir(song_folder: str) -> Path:
    if not song_folder or ".." in song_folder or "/" in song_folder or "\\" in song_folder:
        raise ValueError("Invalid song id")
    root = SCORES_ROOT.resolve()
    p = (SCORES_ROOT / song_folder).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise ValueError("Invalid song id") from None
    if p == root:
        raise ValueError("Invalid song id")
    return p


def delete_score_folder(folder_id: str) -> bool:
    """删除曲包目录（与 list_scores_manifest 中的 folderId / 静态文件名 song_id 一致）。"""
    d = score_dir(folder_id)
    if not d.is_dir():
        return False
    shutil.rmtree(d)
    return True


def safe_file_path(song_folder: str, filename: str) -> Path:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid path")
    d = score_dir(song_folder)
    target = (d / filename).resolve()
    if target.parent != d.resolve():
        raise ValueError("Invalid path")
    return target


def run_ffmpeg_midi_to_mp3(src: Path, dst_mp3: Path) -> None:
    dst_mp3.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        str(dst_mp3),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout or "ffmpeg failed")
