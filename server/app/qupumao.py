"""曲谱猫 www.qupumao.com：服务端搜索与谱图拉取（避免浏览器跨域）。

解析与请求策略对齐 cursor_workspace/backend/src/search/qupumao.js：
- 搜索：article.post-list 内 /qupu/*.html；slug 允许字母数字 ._-
- 详情：.single-entry 内 img[src]，过滤噪声与扩展名规则后收集 URL
- HTTP：列表/详情 HTML 请求带 Referer；图片请求带 Referer（曲谱猫站点）
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

QU_ORIGIN = "https://www.qupumao.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
CACHE_SEC = 600

_PATH_OK = re.compile(r"^/qupu/[a-zA-Z0-9._-]+\.html$", re.I)
_SLUG_MIN_LEN = 3


def _get(url: str, timeout: int = 35) -> str:
    """与参考实现 fetchText 一致：Referer + Accept，降低空页面/拦截概率。"""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Referer": QU_ORIGIN + "/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _abs_resource_url(src: str) -> str:
    s = (src or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return QU_ORIGIN + s
    return f"{QU_ORIGIN}/{s}"


def _is_noise_img(url: str) -> bool:
    return bool(re.search(r"logo|jianpuku\.com/res/home/imgs/pic/", url, re.I))


def _slice_single_entry(html: str) -> str:
    """近似 cheerio 的 .single-entry 区域，减少导航图等干扰。"""
    m = re.search(r'<div[^>]*\bsingle-entry\b[^>]*>', html, re.I)
    if not m:
        return html
    rest = html[m.end() : m.end() + 600_000]
    end_m = re.search(
        r'<div[^>]*class="[^"]*\b(?:single-bottom|related-post|sidebar|comments-area)\b[^"]*"',
        rest,
        re.I,
    )
    if end_m:
        rest = rest[: end_m.start()]
    return rest


def _parse_detail_meta_image_urls(html: str) -> list[str]:
    """对齐 parseDetailMeta：single-entry 内 img[src]，去重、保序。"""
    slice_html = _slice_single_entry(html)
    urls: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"<img[^>]*\bsrc\s*=\s*\"([^\"]+)\"", slice_html, re.I):
        raw = m.group(1).strip()
        full = _abs_resource_url(raw)
        if not full or _is_noise_img(full):
            continue
        if re.search(r"\.(gif|jpe?g|png|webp)(\?|$|#)", full, re.I) or re.search(
            r"jianpu|attachment|qupu|92kk", full, re.I
        ):
            if full not in seen:
                seen.add(full)
                urls.append(full)
    for m in re.finditer(r"<img[^>]*\bsrc\s*=\s*'([^']+)'", slice_html, re.I):
        raw = m.group(1).strip()
        full = _abs_resource_url(raw)
        if not full or _is_noise_img(full):
            continue
        if re.search(r"\.(gif|jpe?g|png|webp)(\?|$|#)", full, re.I) or re.search(
            r"jianpu|attachment|qupu|92kk", full, re.I
        ):
            if full not in seen:
                seen.add(full)
                urls.append(full)
    return urls


def _fallback_regex_image_urls(html: str) -> list[str]:
    """旧版 imgs.92kk / attachment/jianpu 正则兜底（全文扫描）。"""
    pat = re.compile(
        r'src="(https?://imgs\.92kk\.com[^"]+)"'
        r'|src="(https?://[^"]*attachment/jianpu[^"]+)"',
        re.I,
    )
    out: list[str] = []
    seen: set[str] = set()
    for m in pat.finditer(html):
        u = m.group(1) or m.group(2)
        if u and u not in seen and "92kk.com" in u:
            seen.add(u)
            out.append(u)
    return out


def search_qupumao(key: str, *, limit: int = 15) -> list[dict[str, Any]]:
    key = (key or "").strip()
    if not key:
        return []
    now = time.time()
    if key in _search_cache and now - _search_cache[key][0] < CACHE_SEC:
        return list(_search_cache[key][1])

    q = urllib.parse.urlencode({"key": key})
    url = f"{QU_ORIGIN}/search.html?{q}"
    html = _get(url)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def append_result(path: str, title: str) -> None:
        slug = path.rsplit("/", 1)[-1].replace(".html", "")
        if len(slug) < _SLUG_MIN_LEN:
            return
        if path in seen:
            return
        seen.add(path)
        t = (title or "").strip() or path.replace("/qupu/", "").replace(".html", "")
        out.append({"title": t, "path": path, "url": QU_ORIGIN + path})

    # 1) 与参考实现一致：article.post-list
    for art_m in re.finditer(
        r"<article[^>]*\bpost-list\b[^>]*>([\s\S]*?)</article>",
        html,
        re.I,
    ):
        block = art_m.group(1)
        for hm in re.finditer(r'href\s*=\s*"(/qupu/[a-zA-Z0-9._-]+\.html)"', block, re.I):
            path = hm.group(1)
            if path in seen:
                continue
            pa_e = re.escape(path)
            t = ""
            tm = re.search(rf'<a[^>]+href="{pa_e}"[^>]*title="([^"]+)"', block, re.I)
            if tm:
                t = tm.group(1).strip()
            xm = re.search(rf'<a[^>]+href="{pa_e}"[^>]*>([\s\S]*?)</a>', block, re.I)
            tx = re.sub(r"<[^>]+>", "", xm.group(1)).strip() if xm else ""
            append_result(path, t or tx)
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break

    # 2) 兜底：原 entry-header / h3 内链接（slug 已放宽）
    if len(out) < limit:
        for art in re.finditer(r"<article[^>]*>([\s\S]*?)</article>", html, re.I):
            block = art.group(1)
            hdr = re.search(
                r'<header[^>]*class="[^"]*entry-header[^"]*"[^>]*>([\s\S]*?)</header>',
                block,
                re.I,
            )
            link_block = hdr.group(1) if hdr else block
            h3a = re.search(
                r'<h3[^>]*>\s*<a\s+([^>]*?)href="(/qupu/[a-zA-Z0-9._-]+\.html)"[^>]*>([\s\S]*?)</a>',
                link_block,
                re.I,
            )
            if not h3a:
                h3a = re.search(
                    r'<h3[^>]*>\s*<a\s+([^>]*?)href="(/qupu/[a-zA-Z0-9._-]+\.html)"[^>]*>([\s\S]*?)</a>',
                    block,
                    re.I,
                )
            if not h3a:
                continue
            path = h3a.group(2)
            if path in seen:
                continue
            aopen = h3a.group(0)[:800]
            tm = re.search(r'title="([^"]+)"', aopen)
            inner = h3a.group(3)
            title = (tm.group(1).strip() if tm else re.sub(r"<[^>]+>", "", inner).strip())
            append_result(path, title)
            if len(out) >= limit:
                break

    _search_cache[key] = (now, out)
    return out


def validate_qupu_path(path: str) -> str:
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    if not _PATH_OK.match(p):
        raise ValueError("invalid qupu path")
    return p


def resolve_sheet_image_urls(article_path: str) -> list[str]:
    """详情页中候选谱图 URL 列表（先 single-entry 解析，再全局正则兜底）。"""
    p = validate_qupu_path(article_path)
    page_html = _get(QU_ORIGIN + p)
    urls = _parse_detail_meta_image_urls(page_html)
    if not urls:
        urls = _fallback_regex_image_urls(page_html)
    return urls


def resolve_sheet_image_url(article_path: str) -> str:
    urls = resolve_sheet_image_urls(article_path)
    if not urls:
        raise RuntimeError("未在文章中找到可用谱图地址")
    return urls[0]


def fetch_url_bytes(
    url: str,
    timeout: int = 45,
    *,
    referer: str | None = None,
) -> tuple[bytes, str]:
    """对齐 downloadImage：合适 Accept；CDN/防盗链依赖 Referer。"""
    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    ref = referer or ""
    if not ref:
        if "92kk.com" in url or "qupumao.com" in url:
            ref = QU_ORIGIN + "/"
    if ref:
        headers["Referer"] = ref
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        ct = r.headers.get("Content-Type", "image/jpeg")
    return data, ct.split(";")[0].strip() or "image/jpeg"
