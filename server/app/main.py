import json
import urllib.error
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth_admin import (
    create_admin_token,
    require_admin_token,
    verify_admin_credentials,
)
from .auth_app import require_app_token
from .config import SCORES_ROOT
from .marker_temp import MARKER_TEMP, ensure_marker_temp, marker_asset_response
from .qupumao import QU_ORIGIN, fetch_url_bytes, resolve_sheet_image_urls, search_qupumao, validate_qupu_path
from .scores_fs import (
    delete_score_folder,
    ensure_scores_root,
    list_scores_manifest,
    run_ffmpeg_midi_to_mp3,
    safe_file_path,
)

app = FastAPI(title="Yuepu Score Server")

# 开发期：打点小工具可能从其它端口/预览打开并指向本机 API，需带 Authorization 的跨源请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
ensure_scores_root()
ensure_marker_temp()

# 注意：Mount 须注册在 /marker-assets、/api 等具体路由之后，避免旧版路由与路径前缀歧义。


def _safe_home_index_path() -> Path | None:
    """首页 HTML 路径（须落在 STATIC_DIR 下，防路径穿越）。"""
    try:
        root = STATIC_DIR.resolve()
        p = (STATIC_DIR / "home" / "index.html").resolve()
        p.relative_to(root)
    except (ValueError, OSError):
        return None
    return p if p.is_file() else None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home_page():
    """乐谱库首页；放在 API 与 Mount 之前注册，避免极端环境下根路径匹配异常。"""
    path = _safe_home_index_path()
    if path:
        return FileResponse(
            path,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    return HTMLResponse(
        content=(
            "<p>home/index.html 缺失。请确认 <code>server/static/home/index.html</code> 存在后重启服务；"
            "或先访问 <a href='/marker/'>/marker/</a>。</p>"
        ),
        status_code=404,
    )


@app.post("/api/marker/upload")
async def api_marker_upload(
    request: Request,
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    _: None = Depends(require_app_token),
):
    """将打点小工具选中的谱图与音频暂存到服务器，返回可用 URL（供 img/audio 标签加载，避免本机占位文件无法读取）。"""
    ensure_marker_temp()
    session = uuid.uuid4().hex
    d = MARKER_TEMP / session
    d.mkdir(parents=True, exist_ok=False)

    img_suffix = Path(image.filename or "sheet.jpg").suffix.lower() or ".jpg"
    if img_suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        img_suffix = ".jpg"
    img_name = f"sheet{img_suffix}"

    aud_suffix = Path(audio.filename or "audio.mp3").suffix.lower() or ".mp3"
    if aud_suffix not in {".mp3", ".mpeg", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".mid", ".midi"}:
        aud_suffix = ".mp3"
    aud_name = f"audio{aud_suffix}"

    img_bytes = await image.read()
    aud_bytes = await audio.read()
    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="图片文件为空（0 字节），请换本地已下载的文件")
    if len(aud_bytes) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空（0 字节），请换本地已下载的文件")

    (d / img_name).write_bytes(img_bytes)
    (d / aud_name).write_bytes(aud_bytes)

    # 资源统一走 /api/marker/asset/…，与上传同前缀，便于端口转发/隧道只放行 /api 时仍能加载预览
    rel_img = f"/api/marker/asset/{session}/{img_name}"
    rel_aud = f"/api/marker/asset/{session}/{aud_name}"
    xf_host = request.headers.get("x-forwarded-host")
    xf_proto = request.headers.get("x-forwarded-proto")
    if xf_host:
        host = xf_host.split(",")[0].strip()
        proto = (xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme) or "https"
        base = f"{proto}://{host}".rstrip("/")
    else:
        base = str(request.base_url).rstrip("/")
    return {
        "session": session,
        "imageUrl": rel_img,
        "audioUrl": rel_aud,
        "imageUrlAbs": f"{base}{rel_img}",
        "audioUrlAbs": f"{base}{rel_aud}",
    }


@app.post("/api/marker/stage")
async def api_marker_stage(
    request: Request,
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    data_json: UploadFile = File(...),
    _: None = Depends(require_app_token),
):
    """将当前谱图、音频与标注 JSON 暂存到 marker_temp（与 upload 同目录规则），供阅览页 ?markerSession= 按正式曲包逻辑预览。"""
    ensure_marker_temp()
    session = uuid.uuid4().hex
    d = MARKER_TEMP / session
    d.mkdir(parents=True, exist_ok=False)

    img_suffix = Path(image.filename or "sheet.jpg").suffix.lower() or ".jpg"
    if img_suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        img_suffix = ".jpg"
    img_name = f"sheet{img_suffix}"

    aud_suffix = Path(audio.filename or "audio.mp3").suffix.lower() or ".mp3"
    if aud_suffix not in {".mp3", ".mpeg", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".mid", ".midi"}:
        aud_suffix = ".mp3"
    aud_name = f"audio{aud_suffix}"

    img_bytes = await image.read()
    aud_bytes = await audio.read()
    raw_json = await data_json.read()
    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="图片文件为空")
    if len(aud_bytes) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")
    try:
        obj = json.loads(raw_json.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid data.json")

    (d / img_name).write_bytes(img_bytes)
    (d / aud_name).write_bytes(aud_bytes)
    obj["imageFile"] = img_name
    obj["audioFile"] = aud_name
    (d / "data.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    rel_img = f"/api/marker/asset/{session}/{img_name}"
    rel_aud = f"/api/marker/asset/{session}/{aud_name}"
    rel_data = f"/api/marker/asset/{session}/data.json"
    xf_host = request.headers.get("x-forwarded-host")
    xf_proto = request.headers.get("x-forwarded-proto")
    if xf_host:
        host = xf_host.split(",")[0].strip()
        proto = (xf_proto.split(",")[0].strip() if xf_proto else request.url.scheme) or "https"
        base = f"{proto}://{host}".rstrip("/")
    else:
        base = str(request.base_url).rstrip("/")
    return {
        "session": session,
        "imageUrl": rel_img,
        "audioUrl": rel_aud,
        "dataUrl": rel_data,
        "viewerUrl": f"{base}/viewer/?markerSession={session}&minimal=1",
    }


@app.get("/api/marker/asset/{session}/{filename:path}")
def api_marker_temp_asset(session: str, filename: str):
    """与上传接口同路径前缀，避免仅转发 /api 的代理无法访问 /marker-assets。"""
    return marker_asset_response(session, filename)


@app.get("/marker-assets/{session}/{filename:path}")
def get_marker_asset(session: str, filename: str):
    """通过不可猜测的 session 访问暂存文件，无需 Authorization（请勿把 session URL 公开传播）。"""
    return marker_asset_response(session, filename)


@app.get("/api/scores")
def api_scores_list(ready: bool = False, _: None = Depends(require_app_token)):
    """ready=true 时仅返回已打点且谱图/音频文件齐全的条目（首页曲库）；默认 false 兼容 App 全量列表。"""
    return {"scores": list_scores_manifest(only_ready=ready)}


class ScoresPostBody(BaseModel):
    """POST /api/scores：删除曲包（与 GET 列表同一路径，便于网关只放行 /api/scores）。"""

    action: str
    song_id: str | None = None
    songId: str | None = None
    folderId: str | None = None


@app.post("/api/scores")
def api_scores_post(body: ScoresPostBody, _: None = Depends(require_app_token)):
    act = (body.action or "").strip().lower()
    if act != "delete":
        raise HTTPException(status_code=400, detail='Use action "delete" to remove a score package')
    sid = (body.folderId or body.song_id or body.songId or "").strip()
    return _delete_score_package(sid)


def _delete_score_package(song_id: str) -> dict:
    """删除曲包目录；song_id 为磁盘 folderId（与 /api/scores/{id}/… 一致）。"""
    sid = (song_id or "").strip()
    if not sid or "/" in sid or "\\" in sid or ".." in sid:
        raise HTTPException(status_code=400, detail="Invalid song_id")
    try:
        removed = delete_score_folder(sid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if not removed:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


class ScoreDeleteBody(BaseModel):
    """删除曲包 JSON：优先 folderId（与列表 manifest 一致），其次 song_id / songId。"""

    folderId: str | None = None
    song_id: str | None = None
    songId: str | None = None


def _delete_score_from_body(body: ScoreDeleteBody) -> dict:
    sid = (body.folderId or body.song_id or body.songId or "").strip()
    return _delete_score_package(sid)


@app.post("/api/delete-score")
def api_delete_score(body: ScoreDeleteBody, _: None = Depends(require_app_token)):
    """删除曲包（POST）。路径独立于 /api/scores/…，避免与 GET .../{filename:path} 将「delete」误解析为 song_id 导致 405。"""
    return _delete_score_from_body(body)


@app.post("/api/scores/delete")
def api_scores_delete_post_alias(body: ScoreDeleteBody, _: None = Depends(require_app_token)):
    """兼容旧客户端；请优先使用 POST /api/delete-score。"""
    return _delete_score_from_body(body)


@app.delete("/api/scores/{song_id}")
def api_scores_delete(song_id: str, _: None = Depends(require_app_token)):
    """删除服务器上的整套曲包目录（需 App Token，与阅览 URL 中的 open= 标识一致）。"""
    return _delete_score_package(song_id)


@app.get("/api/scores/{song_id}/{filename:path}")
def api_score_file(song_id: str, filename: str, _: None = Depends(require_app_token)):
    try:
        path = safe_file_path(song_id, filename)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


async def _save_score_package(
    song_id: str,
    title: str,
    image: UploadFile,
    audio: UploadFile,
    data_json: UploadFile | None,
    *,
    require_data_json: bool,
    require_measures: bool,
    allow_overwrite: bool = False,
) -> dict:
    if not song_id or "/" in song_id or "\\" in song_id or ".." in song_id:
        raise HTTPException(status_code=400, detail="Invalid song_id")

    dest = SCORES_ROOT / song_id
    if dest.is_dir() and (dest / "data.json").is_file():
        if not allow_overwrite:
            raise HTTPException(
                status_code=409,
                detail="服务器上已存在同名曲包（相同目录名且含 data.json）；若要替换请先确认覆盖后再发布。",
            )
        delete_score_folder(song_id)

    dest.mkdir(parents=True, exist_ok=True)

    image_suffix = Path(image.filename or "sheet.jpg").suffix.lower() or ".jpg"
    if image_suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        image_suffix = ".jpg"
    image_name = f"sheet{image_suffix}"
    image_path = dest / image_name
    content = await image.read()
    image_path.write_bytes(content)

    audio_suffix = Path(audio.filename or "audio.mp3").suffix.lower()
    audio_bytes = await audio.read()
    final_audio_name = "audio.mp3"

    if audio_suffix in {".mid", ".midi"}:
        tmp_mid = dest / f"_upload{audio_suffix}"
        tmp_mid.write_bytes(audio_bytes)
        out_mp3 = dest / final_audio_name
        try:
            run_ffmpeg_midi_to_mp3(tmp_mid, out_mp3)
        except Exception as e:
            tmp_mid.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"MIDI transcode failed: {e}") from e
        tmp_mid.unlink(missing_ok=True)
    elif audio_suffix == ".mp3":
        (dest / final_audio_name).write_bytes(audio_bytes)
    elif audio_suffix == ".m4a":
        final_audio_name = "audio.m4a"
        (dest / final_audio_name).write_bytes(audio_bytes)
    else:
        raise HTTPException(
            status_code=400,
            detail="Audio must be .mp3, .m4a, .mid, or .midi",
        )

    if data_json is not None and data_json.filename:
        raw = await data_json.read()
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Invalid data.json")
        if require_measures:
            measures = obj.get("measures")
            if not isinstance(measures, list) or len(measures) < 1:
                raise HTTPException(
                    status_code=400,
                    detail="发布失败：data.json 中需包含至少 1 个小节（请先在谱面上完成打点）",
                )
        obj["songId"] = song_id
        if title:
            obj["title"] = title
        obj["imageFile"] = image_name
        obj["audioFile"] = final_audio_name
        (dest / "data.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        if require_data_json:
            raise HTTPException(status_code=400, detail="发布需上传 data.json（打点小工具导出的标注）")
        obj = {
            "songId": song_id,
            "title": title or song_id,
            "imageFile": image_name,
            "audioFile": final_audio_name,
            "measures": [],
        }
        (dest / "data.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "songId": song_id}


@app.post("/admin/login")
def admin_login(payload: dict):
    username = payload.get("username") or ""
    password = payload.get("password") or ""
    if not verify_admin_credentials(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_admin_token(), "token_type": "bearer"}


@app.post("/admin/scores")
async def admin_upload_score(
    song_id: str = Form(...),
    title: str = Form(""),
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    data_json: UploadFile | None = File(None),
    _: str = Depends(require_admin_token),
):
    return await _save_score_package(
        song_id,
        title,
        image,
        audio,
        data_json,
        require_data_json=False,
        require_measures=False,
        allow_overwrite=True,
    )


@app.post("/api/marker/publish")
async def api_marker_publish(
    song_id: str = Form(...),
    title: str = Form(""),
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    data_json: UploadFile = File(...),
    overwrite: bool = Form(False),
    _: None = Depends(require_app_token),
):
    """打点小工具：谱图 + 音频 + data.json 一并写入曲库（App Token），首页可阅览。"""
    return await _save_score_package(
        song_id,
        title,
        image,
        audio,
        data_json,
        require_data_json=True,
        require_measures=True,
        allow_overwrite=overwrite,
    )


@app.post("/api/marker/remove-score")
def api_marker_remove_score(body: ScoreDeleteBody, _: None = Depends(require_app_token)):
    """删除已发布曲包；与 /api/marker/* 同前缀，供首页在仅注册了 GET /api/scores 的旧后端上回退调用（避免 POST /api/scores 405）。"""
    return _delete_score_from_body(body)


class QupumaoDownloadBody(BaseModel):
    path: str


@app.get("/api/marker/qupumao/search")
def api_qupumao_search(q: str = "", _: None = Depends(require_app_token)):
    """代理搜索 www.qupumao.com（曲谱猫）；结果带服务端短时间缓存。"""
    try:
        results = search_qupumao(q, limit=15)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise HTTPException(status_code=502, detail=f"搜索失败（网络或对方站点）: {e}") from e
    return {"results": results}


@app.post("/api/marker/qupumao/download")
def api_qupumao_download(body: QupumaoDownloadBody, _: None = Depends(require_app_token)):
    """根据曲谱猫文章 path 解析谱图并下载；对齐参考实现可能对同一文有多张图，依次尝试直至成功。"""
    try:
        p = validate_qupu_path(body.path)
        img_urls = resolve_sheet_image_urls(p)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not img_urls:
        raise HTTPException(
            status_code=404,
            detail="未在文章中找到可用谱图地址",
        )
    ref = QU_ORIGIN + p
    last_err: str | None = None
    max_tries = min(12, len(img_urls))
    for img_url in img_urls[:max_tries]:
        try:
            data, mime = fetch_url_bytes(img_url, referer=ref)
            if len(data) >= 256:
                return Response(
                    content=data,
                    media_type=mime,
                    headers={"Content-Disposition": 'inline; filename="qupumao_sheet.jpg"'},
                )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = str(e)
            continue
    raise HTTPException(
        status_code=502,
        detail="下载失败："
        + (last_err or "全部候选地址均不可用")
        + f"（已尝试 {max_tries} 个 URL）",
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    html_path = STATIC_DIR / "admin.html"
    if html_path.is_file():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<p>admin.html missing</p>")


@app.get("/viewer")
def viewer_redirect_slash():
    return RedirectResponse(url="/viewer/", status_code=307)


@app.get("/viewer/", response_class=HTMLResponse)
def viewer_page():
    """显式提供阅览页，避免仅依赖 StaticFiles 挂载时在部分环境下 404。"""
    html_path = STATIC_DIR / "viewer" / "index.html"
    if html_path.is_file():
        return HTMLResponse(
            content=html_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    return HTMLResponse(
        "<p>viewer/index.html 缺失，请确认已部署 <code>server/static/viewer/index.html</code></p>",
        status_code=404,
    )


# 静态与打点小工具页面放在最后挂载，保证 /api、/marker-assets 优先匹配
if (STATIC_DIR / "marker").is_dir():
    app.mount("/marker", StaticFiles(directory=str(STATIC_DIR / "marker"), html=True), name="marker")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
