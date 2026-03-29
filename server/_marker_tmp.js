
    const sheet = document.getElementById("sheet");
    const overlay = document.getElementById("overlay");
    const ctx =
      overlay && typeof overlay.getContext === "function" ? overlay.getContext("2d") : null;
    const audio = document.getElementById("audio");
    const statusEl = document.getElementById("status");
    const debugLogEl = document.getElementById("debugLog");
    const preview = document.getElementById("preview");
    const appTokenMarker = document.getElementById("appTokenMarker");
    const apiBaseMarker = document.getElementById("apiBaseMarker");
    const savedMarkerToken = localStorage.getItem("yuepu_marker_app_token");
    if (appTokenMarker) {
      if (savedMarkerToken) appTokenMarker.value = savedMarkerToken;
      else if (!appTokenMarker.value.trim()) appTokenMarker.value = "dev-app-token-change-me";
    }
    const savedApiBase = localStorage.getItem("yuepu_marker_api_base");
    if (apiBaseMarker && savedApiBase) apiBaseMarker.value = savedApiBase;
    const qApi = new URLSearchParams(location.search).get("api");
    if (apiBaseMarker && qApi && qApi.trim()) apiBaseMarker.value = qApi.trim().replace(/\/$/, "");

    if (location.protocol === "file:") {
      const fpw = document.getElementById("fileProtoWarn");
      if (fpw) fpw.style.display = "block";
    }

    /** 仅 http(s) 页面可连后端；file:// 下相对路径会失效 */
    function httpOrigin() {
      if (location.protocol === "http:" || location.protocol === "https:") return location.origin;
      return "";
    }

    /** 上传与资源 URL 共用：可手动填后端根地址（侧边预览等场景） */
    function getMarkerApiBase() {
      const v = apiBaseMarker ? (apiBaseMarker.value || "").trim().replace(/\/$/, "") : "";
      if (v) return v;
      return httpOrigin();
    }

    function toAbsUrl(pathOrUrl) {
      const o = getMarkerApiBase();
      if (!pathOrUrl || typeof pathOrUrl !== "string") return "";
      if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) return pathOrUrl;
      if (!o) return pathOrUrl;
      const p = pathOrUrl.startsWith("/") ? pathOrUrl : "/" + pathOrUrl;
      return new URL(p, o + "/").href;
    }

    function showMarkerApiWarn(html) {
      const el = document.getElementById("markerApiWarn");
      if (!el) return;
      el.style.display = "block";
      el.innerHTML = html;
    }

    function appendStatus(line) {
      if (!line || !statusEl) return;
      statusEl.textContent = (statusEl.textContent ? statusEl.textContent + "\n" : "") + line;
    }

    function debug(line) {
      if (!line || !debugLogEl) return;
      const t = new Date().toLocaleTimeString();
      debugLogEl.textContent += "[" + t + "] " + line + "\n";
      debugLogEl.scrollTop = debugLogEl.scrollHeight;
    }

    window.addEventListener("error", (e) => {
      const msg = e && e.message ? e.message : "unknown error";
      if (statusEl) statusEl.textContent = "页面脚本错误：" + msg;
      debug("window.error: " + msg);
    });
    window.addEventListener("unhandledrejection", (e) => {
      const reason = e && e.reason ? String(e.reason) : "unknown rejection";
      if (statusEl) statusEl.textContent = "页面脚本异常：" + reason;
      debug("unhandledrejection: " + reason);
    });

    (async function checkMarkerBackend() {
      const base = getMarkerApiBase();
      debug("page loaded, apiBase=" + (base || "(empty)"));
      if (!base) return;
      try {
        const r = await fetch(base + "/openapi.json", { method: "GET" });
        if (!r.ok) return;
        const spec = await r.json();
        if (!spec.paths || !spec.paths["/api/marker/upload"]) {
          showMarkerApiWarn(
            "已连上后端，但<strong>没有</strong>打点上传统接口 <code>/api/marker/upload</code>（多为 uvicorn 仍在跑<strong>旧代码</strong>）。请在终端里对该进程按 <strong>Ctrl+C</strong> 停止，然后在 <code>server</code> 目录执行：" +
              "<code>python -m uvicorn app.main:app --host 0.0.0.0 --port 8000</code>，再<strong>硬刷新</strong>本页（Ctrl+F5）。"
          );
        }
      } catch (e) {
        /* 忽略：离线或非同源策略 */
        debug("openapi check failed: " + (e && e.message ? e.message : String(e)));
      }
    })();

    let naturalW = 0, naturalH = 0;
    let drawing = false;
    let startX = 0, startY = 0;
    let currentRect = null;
    /** @type {{id:number,startTimeMs:number,endTimeMs:number,rect:{x:number,y:number,w:number,h:number}}[]} */
    let measures = [];
    let draftRects = [];
    let lastMarkerMs = 0;
    /** @type {string|null} blob 模式时持有，便于替换时 revoke */
    let currentImageObjectUrl = null;
    /** @type {string|null} */
    let currentAudioObjectUrl = null;
    /** @type {string|null} 服务器资源 blob URL（用于强制预览） */
    let currentServerImageObjectUrl = null;
    /** @type {string|null} */
    let currentServerAudioObjectUrl = null;
    let overlaySyncAttempts = 0;

    const MAX_IMAGE_DATA_URL = 85 * 1024 * 1024;
    const MAX_AUDIO_DATA_URL = 48 * 1024 * 1024;

    function formatSize(n) {
      if (n < 1024) return n + " B";
      if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
      return (n / 1048576).toFixed(2) + " MB";
    }

    async function ensureOk(url, token) {
      const r = await fetch(url, {
        method: "GET",
        headers: token ? { Authorization: "Bearer " + token } : undefined,
        mode: "cors",
        credentials: "omit",
        cache: "no-store",
      });
      if (!r.ok) {
        throw new Error("GET " + url + " -> HTTP " + r.status);
      }
      return r;
    }

    async function loadServerAssetsViaBlob(absImg, absAud, token) {
      appendStatus("开始拉取服务器资源（用于强制预览）…");
      const [imgResp, audResp] = await Promise.all([ensureOk(absImg, token), ensureOk(absAud, token)]);
      const [imgBlob, audBlob] = await Promise.all([imgResp.blob(), audResp.blob()]);

      if (currentServerImageObjectUrl) {
        URL.revokeObjectURL(currentServerImageObjectUrl);
        currentServerImageObjectUrl = null;
      }
      if (currentServerAudioObjectUrl) {
        URL.revokeObjectURL(currentServerAudioObjectUrl);
        currentServerAudioObjectUrl = null;
      }
      currentServerImageObjectUrl = URL.createObjectURL(imgBlob);
      currentServerAudioObjectUrl = URL.createObjectURL(audBlob);

      sheet.src = currentServerImageObjectUrl;
      audio.src = currentServerAudioObjectUrl;
      audio.load();
      appendStatus(
        "资源已下载：图片 " + formatSize(imgBlob.size) + "，音频 " + formatSize(audBlob.size) + "。正在解码…"
      );
    }

    function loadImageFromBlobUrl(f) {
      if (currentImageObjectUrl) {
        URL.revokeObjectURL(currentImageObjectUrl);
        currentImageObjectUrl = null;
      }
      sheet.onerror = () => {
        naturalW = 0;
        naturalH = 0;
        statusEl.textContent =
          "图片加载失败（blob）。请改用本地已下载的 JPG/PNG，或换 Chrome/Edge。";
      };
      const url = URL.createObjectURL(f);
      currentImageObjectUrl = url;
      sheet.onload = () => {
        if (typeof sheet.decode === "function") {
          sheet.decode().then(applyLoadedImage).catch(applyLoadedImage);
        } else {
          applyLoadedImage();
        }
      };
      sheet.src = url;
    }

    function loadAudioFromBlobUrl(f) {
      if (currentAudioObjectUrl) {
        URL.revokeObjectURL(currentAudioObjectUrl);
        currentAudioObjectUrl = null;
      }
      const url = URL.createObjectURL(f);
      currentAudioObjectUrl = url;
      audio.onerror = () => {
        statusEl.textContent = "音频无法加载（blob），请换标准 MP3。";
      };
      audio.src = url;
      audio.load();
      statusEl.textContent = "音频已加载（" + formatSize(f.size) + "）。请点下方播放条试听。";
    }

    function syncOverlaySize() {
      if (!ctx || !overlay) return;
      const w = sheet.clientWidth;
      const h = sheet.clientHeight;
      if (naturalW > 0 && naturalH > 0 && (w < 2 || h < 2) && overlaySyncAttempts < 40) {
        overlaySyncAttempts++;
        requestAnimationFrame(syncOverlaySize);
        return;
      }
      overlaySyncAttempts = 0;
      overlay.width = Math.max(1, Math.floor(w));
      overlay.height = Math.max(1, Math.floor(h));
      overlay.style.width = w + "px";
      overlay.style.height = h + "px";
      redraw();
    }

    function imgToNatural(ix, iy) {
      const sx = naturalW / sheet.clientWidth;
      const sy = naturalH / sheet.clientHeight;
      return { x: ix * sx, y: iy * sy };
    }

    function redraw() {
      if (!ctx) {
        updatePreview();
        return;
      }
      const w = overlay.width;
      const h = overlay.height;
      ctx.clearRect(0, 0, w, h);
      if (!naturalW || !naturalH || w < 1 || h < 1) {
        updatePreview();
        return;
      }
      const scaleX = w / naturalW;
      const scaleY = h / naturalH;
      ctx.strokeStyle = "rgba(255,193,7,0.9)";
      ctx.lineWidth = 2;
      measures.forEach((m) => {
        ctx.strokeRect(m.rect.x * scaleX, m.rect.y * scaleY, m.rect.w * scaleX, m.rect.h * scaleY);
      });
      draftRects.forEach((r) => {
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(r.x * scaleX, r.y * scaleY, r.w * scaleX, r.h * scaleY);
        ctx.setLineDash([]);
      });
      if (currentRect) {
        const r = currentRect;
        ctx.strokeStyle = "rgba(33,150,243,0.95)";
        ctx.strokeRect(r.x * scaleX, r.y * scaleY, r.w * scaleX, r.h * scaleY);
      }
      updatePreview();
    }

    function updatePreview() {
      const songId = document.getElementById("songId").value.trim() || "demo_song";
      const title = document.getElementById("title").value.trim() || songId;
      const imageFile = "sheet.jpg";
      const audioFile = "audio.mp3";
      const obj = { songId, title, imageFile, audioFile, measures };
      preview.textContent = JSON.stringify(obj, null, 2);
    }

    function applyLoadedImage() {
      naturalW = sheet.naturalWidth;
      naturalH = sheet.naturalHeight;
      if (!naturalW || !naturalH) {
        statusEl.textContent = "图片无法读取尺寸，请换一张图或检查格式（建议 JPG/PNG）";
        return;
      }
      overlaySyncAttempts = 0;
      syncOverlaySize();
      statusEl.textContent =
        "图片已加载（" + naturalW + "×" + naturalH + "）。在右侧谱面上按住拖动画框；可用下方播放器或「播放/暂停」。";
    }

    document.getElementById("imgFile").addEventListener("change", (e) => {
      const f = e.target.files[0];
      if (!f) return;
      if (currentImageObjectUrl) {
        URL.revokeObjectURL(currentImageObjectUrl);
        currentImageObjectUrl = null;
      }
      let hint = "已选图片：" + f.name + "（" + formatSize(f.size) + "）";
      if (f.size === 0) {
        statusEl.textContent =
          hint +
          " — 大小为 0，无法加载。常见于「照片/iPhone 导入」等云端占位：请先把文件**复制到桌面或文档**再选，或右键文件选「始终保留在此设备上」。";
        return;
      }
      if (/^import-/i.test(f.name)) {
        hint += "（若为系统导入文件仍失败，请复制到普通文件夹后再选）";
      }
      statusEl.textContent = hint + "，正在读取…";

      if (f.size > MAX_IMAGE_DATA_URL) {
        statusEl.textContent += " 文件较大，使用 blob 加载。";
        loadImageFromBlobUrl(f);
        return;
      }

      const reader = new FileReader();
      reader.onerror = () => {
        naturalW = 0;
        naturalH = 0;
        statusEl.textContent = "读取图片失败，请重试或换一张图。";
      };
      reader.onload = () => {
        const dataUrl = reader.result;
        if (typeof dataUrl !== "string") return;
        sheet.onerror = () => {
          naturalW = 0;
          naturalH = 0;
          statusEl.textContent =
            "图片解码失败（可能不是浏览器支持的格式）。请导出为 JPG/PNG 再选。";
        };
        sheet.onload = () => {
          if (typeof sheet.decode === "function") {
            sheet.decode().then(applyLoadedImage).catch(applyLoadedImage);
          } else {
            applyLoadedImage();
          }
        };
        sheet.src = dataUrl;
      };
      reader.readAsDataURL(f);
    });

    document.getElementById("audioFile").addEventListener("change", (e) => {
      const f = e.target.files[0];
      if (!f) return;
      if (currentAudioObjectUrl) {
        URL.revokeObjectURL(currentAudioObjectUrl);
        currentAudioObjectUrl = null;
      }
      let hint = "已选音频：" + f.name + "（" + formatSize(f.size) + "）";
      if (f.size === 0) {
        statusEl.textContent =
          hint +
          " — 大小为 0，无法播放。请将 MP3 复制到本机文件夹后再选（勿选仅云端的占位）。";
        audio.removeAttribute("src");
        audio.load();
        return;
      }
      statusEl.textContent = hint + "，正在读取…";

      if (f.size > MAX_AUDIO_DATA_URL) {
        statusEl.textContent += " 文件较大，使用 blob 加载。";
        loadAudioFromBlobUrl(f);
        return;
      }

      const reader = new FileReader();
      reader.onerror = () => {
        statusEl.textContent = "读取音频失败，请重试或换 MP3。";
      };
      reader.onload = () => {
        const dataUrl = reader.result;
        if (typeof dataUrl !== "string") return;
        audio.onerror = () => {
          statusEl.textContent = "音频解码失败，请换标准 MP3（如用 FFmpeg 重编码）。";
        };
        audio.src = dataUrl;
        const onMeta = () => {
          audio.removeEventListener("loadedmetadata", onMeta);
          if (audio.duration && isFinite(audio.duration)) {
            statusEl.textContent =
              "音频就绪（" + formatSize(f.size) + "），时长约 " + Math.round(audio.duration) + " 秒。可点下方播放条播放。";
          }
        };
        audio.addEventListener("loadedmetadata", onMeta);
        audio.load();
        statusEl.textContent =
          "音频数据已载入，正在解码…若时长仍为 0:00 请等待数秒或点播放键。";
      };
      reader.readAsDataURL(f);
    });

    window.addEventListener("resize", () => { if (naturalW) syncOverlaySize(); });

    if (overlay) {
      overlay.addEventListener("pointerdown", (e) => {
        if (!naturalW) return;
        overlay.setPointerCapture(e.pointerId);
        drawing = true;
        const rect = overlay.getBoundingClientRect();
        const ix = e.clientX - rect.left;
        const iy = e.clientY - rect.top;
        const n = imgToNatural(ix, iy);
        startX = n.x;
        startY = n.y;
        currentRect = { x: startX, y: startY, w: 0, h: 0 };
      });

      overlay.addEventListener("pointermove", (e) => {
        if (!drawing || !currentRect) return;
        const rect = overlay.getBoundingClientRect();
        const ix = e.clientX - rect.left;
        const iy = e.clientY - rect.top;
        const n = imgToNatural(ix, iy);
        const x = Math.min(startX, n.x);
        const y = Math.min(startY, n.y);
        const w = Math.abs(n.x - startX);
        const h = Math.abs(n.y - startY);
        currentRect = { x, y, w, h };
        redraw();
      });

      overlay.addEventListener("pointerup", (e) => {
        if (!drawing) return;
        drawing = false;
        overlay.releasePointerCapture(e.pointerId);
        if (currentRect && currentRect.w > 4 && currentRect.h > 4) {
          draftRects.push({ ...currentRect });
          statusEl.textContent = "已添加框，按空格绑定时间（毫秒: " + Math.floor(audio.currentTime * 1000) + "）";
        }
        currentRect = null;
        redraw();
      });

      overlay.style.pointerEvents = "auto";
      overlay.style.position = "absolute";
      overlay.style.left = "0";
      overlay.style.top = "0";
    }

    const onUploadClick = async () => {
      debug("click 上传到服务器");
      const imgIn = document.getElementById("imgFile").files[0];
      const audIn = document.getElementById("audioFile").files[0];
      if (!imgIn || !audIn) {
        debug("blocked: missing image or audio");
        statusEl.textContent = "请先选择谱面图片和音频，再点「上传到服务器」。";
        return;
      }
      const token = (appTokenMarker && appTokenMarker.value ? appTokenMarker.value : "").trim();
      if (!token) {
        debug("blocked: missing app token");
        statusEl.textContent = "请填写 App Token（须与服务器环境变量 APP_TOKEN 一致）。";
        return;
      }
      const origin = getMarkerApiBase();
      if (!origin) {
        debug("blocked: missing api base");
        statusEl.textContent =
          "无法上传：请用浏览器访问后端地址打开本页，或在「后端根地址」填写 http://127.0.0.1:8000；不要只用 file:// 打开。";
        return;
      }
      const btn = document.getElementById("btnUploadServer");
      btn.disabled = true;
      statusEl.textContent = "正在上传到服务器…";
      try {
        const fd = new FormData();
        fd.append("image", imgIn);
        fd.append("audio", audIn);
        const r = await fetch(origin + "/api/marker/upload", {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
          body: fd,
          mode: "cors",
          credentials: "omit",
        });
        debug("upload response HTTP " + r.status);
        const text = await r.text();
        let j;
        try {
          j = JSON.parse(text);
        } catch {
          j = { raw: text };
        }
        if (!r.ok) {
          const d = j.detail;
          let tail = "";
          if (r.status === 404) {
            tail =
              " （404 常见原因：8000 端口上的进程不是本仓库最新代码。请停止旧 uvicorn 后在 server 目录重新启动。）";
          }
          debug("upload failed body=" + text.slice(0, 200));
          statusEl.textContent =
            "上传失败（HTTP " + r.status + "）：" +
            (typeof d === "string" ? d : JSON.stringify(d || j.raw || j)) +
            tail;
          return;
        }
        if (!j.imageUrl || !j.audioUrl) {
          statusEl.textContent = "上传返回异常（缺少 imageUrl/audioUrl）：" + text.slice(0, 600);
          return;
        }
        /** 必须与本次 POST 使用同一基址（侧边预览 origin 常不等于真实 API 主机） */
        const baseNoSlash = origin.replace(/\/$/, "");
        const absImg = baseNoSlash + (j.imageUrl.startsWith("/") ? j.imageUrl : "/" + j.imageUrl);
        const absAud = baseNoSlash + (j.audioUrl.startsWith("/") ? j.audioUrl : "/" + j.audioUrl);
        localStorage.setItem("yuepu_marker_app_token", token);
        if (apiBaseMarker && (apiBaseMarker.value || "").trim()) {
          localStorage.setItem("yuepu_marker_api_base", apiBaseMarker.value.trim().replace(/\/$/, ""));
        }
        if (currentImageObjectUrl) {
          URL.revokeObjectURL(currentImageObjectUrl);
          currentImageObjectUrl = null;
        }
        if (currentAudioObjectUrl) {
          URL.revokeObjectURL(currentAudioObjectUrl);
          currentAudioObjectUrl = null;
        }
        sheet.onerror = () => {
          naturalW = 0;
          naturalH = 0;
          statusEl.textContent =
            "从服务器加载图片失败。请检查地址是否与当前站点一致。URL：" + (sheet.src || "").slice(0, 160);
        };
        sheet.onload = () => {
          if (typeof sheet.decode === "function") {
            sheet.decode().then(applyLoadedImage).catch(applyLoadedImage);
          } else {
            applyLoadedImage();
          }
        };
        audio.onerror = () => {
          statusEl.textContent =
            "从服务器加载音频失败（404/格式不支持）。请确认本页地址与后端一致，或换标准 MP3 后重传。当前 src：" +
            (audio.src || "").slice(0, 120);
        };
        const onMeta = () => {
          audio.removeEventListener("loadedmetadata", onMeta);
          if (audio.duration && isFinite(audio.duration)) {
            statusEl.textContent =
              "上传成功，已从服务器加载。音频时长约 " + Math.round(audio.duration) + " 秒。可在图上画框打点。";
          } else {
            statusEl.textContent =
              "上传成功，但浏览器未报告音频时长（仍为 0:00 时可点播放条试播；若无法播放请换 MP3 编码）。";
          }
        };
        audio.addEventListener("loadedmetadata", onMeta);
        statusEl.textContent =
          "上传成功（会话 " +
          (j.session || "").slice(0, 8) +
          "…）。正在校验并拉取谱面与音频…";
        appendStatus("图片 URL: " + absImg);
        appendStatus("音频 URL: " + absAud);
        debug("asset urls ready");
        try {
          await loadServerAssetsViaBlob(absImg, absAud, token);
          debug("blob preview loaded");
        } catch (loadErr) {
          debug("blob preview failed: " + (loadErr && loadErr.message ? loadErr.message : String(loadErr)));
          appendStatus(
            "blob 预览失败，回退直链模式：" +
              (loadErr && loadErr.message ? loadErr.message : String(loadErr))
          );
          sheet.src = absImg;
          audio.src = absAud;
          audio.load();
        }
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        statusEl.textContent =
          "请求异常：" +
          msg +
          "。若含 Failed to fetch：请用 http(s) 打开本页（勿用 file://）、确认 uvicorn 已启动且端口一致。";
      } finally {
        btn.disabled = false;
      }
    };
    window.markerUploadClick = onUploadClick;
    document.getElementById("btnUploadServer").onclick = onUploadClick;

    document.getElementById("btnPlay").onclick = () => {
      if (!audio.src) {
        statusEl.textContent = "请先选择音频并点「上传到服务器」，或使用本机读取。";
        return;
      }
      if (audio.paused) {
        audio.play().catch((err) => {
          statusEl.textContent = "无法播放音频：" + (err && err.message ? err.message : String(err));
        });
      } else {
        audio.pause();
      }
    };

    document.getElementById("btnUndo").onclick = () => {
      if (measures.length) measures.pop();
      else if (draftRects.length) draftRects.pop();
      redraw();
      statusEl.textContent = "已撤销";
    };

    window.addEventListener("keydown", (e) => {
      if (e.code !== "Space") return;
      e.preventDefault();
      const t = Math.floor(audio.currentTime * 1000);
      if (!draftRects.length) {
        statusEl.textContent = "请先画框";
        return;
      }
      const r = draftRects.pop();
      const id = measures.length + 1;
      const startTimeMs = lastMarkerMs;
      const endTimeMs = Math.max(t, startTimeMs + 1);
      measures.push({
        id,
        startTimeMs,
        endTimeMs,
        rect: { x: r.x, y: r.y, w: r.w, h: r.h },
      });
      lastMarkerMs = endTimeMs;
      statusEl.textContent = "小节 " + id + " : start=" + startTimeMs + " end=" + endTimeMs;
      redraw();
    });

    document.getElementById("btnExport").onclick = () => {
      const songId = document.getElementById("songId").value.trim() || "demo_song";
      const title = document.getElementById("title").value.trim() || songId;
      const obj = {
        songId,
        title,
        imageFile: "sheet.jpg",
        audioFile: "audio.mp3",
        measures,
      };
      const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "data.json";
      a.click();
      URL.revokeObjectURL(a.href);
    };

    document.getElementById("songId").addEventListener("input", updatePreview);
    document.getElementById("title").addEventListener("input", updatePreview);
    updatePreview();
  