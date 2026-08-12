# -*- coding: utf-8 -*-
"""
Vercel Serverless 函数入口（Python，纯标准库，无任何第三方依赖）。

统一网关：
  - /api/*  -> core.app_dispatch（业务 API，返回 JSON）
  - 其余路径 -> 从 app/ 目录托管前端静态文件（SPA 入口 + 资源）

使用纯标准库实现 WSGI 入口，避免对 werkzeug 等第三方包的依赖，
彻底规避 Vercel 构建/部署阶段依赖未安装导致的 FUNCTION_INVOCATION_FAILED。
"""
import sys
import os
import json
import mimetypes
from urllib.parse import parse_qs

# 把项目根加入 sys.path，确保能 import 同目录的 core / store
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from core import app_dispatch, CORS, APP_VERSION

STATIC_DIR = os.path.join(ROOT, "app")
TEXT_TYPES = {"text/html", "text/css", "application/javascript", "application/json",
              "image/svg+xml", "application/manifest+json"}

_STATUS_REASON = {
    200: "OK", 201: "Created", 204: "No Content",
    301: "Moved Permanently", 302: "Found",
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed",
    409: "Conflict", 422: "Unprocessable Entity", 500: "Internal Server Error",
}


def _content_type(path):
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if ctype in TEXT_TYPES:
        ctype += "; charset=utf-8"
    return ctype


def serve_static(path):
    """返回 (status, body_bytes, headers_dict)。从 app/ 读静态文件；未知路径回退 index.html。"""
    rel = path.split("?")[0].lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = "index.html"
    full = os.path.normpath(os.path.join(STATIC_DIR, rel))
    # 防目录穿越
    if not (full == STATIC_DIR or full.startswith(STATIC_DIR + os.sep)):
        return (403, b"forbidden", dict(CORS))
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    if not os.path.isfile(full):
        # 客户端路由兜底：返回 SPA 入口
        full = os.path.join(STATIC_DIR, "index.html")
    try:
        with open(full, "rb") as f:
            data = f.read()
    except Exception:
        return (404, b"not found", dict(CORS))
    return (200, data, {"Content-Type": _content_type(full),
                        "Cache-Control": "public, max-age=300"})


def _start(status, extra_headers, start_response):
    reason = _STATUS_REASON.get(status, "OK")
    hdrs = []
    for k, v in (extra_headers or {}).items():
        hdrs.append((k, str(v)))
    start_response("%d %s" % (status, reason), hdrs)


def app(environ, start_response):
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    raw_path = environ.get("PATH_INFO") or "/"
    query_string = environ.get("QUERY_STRING") or ""
    query = parse_qs(query_string)

    # 请求头
    headers_in = {}
    for k, v in environ.items():
        if k.startswith("HTTP_"):
            name = k[5:].replace("_", "-").title()
            headers_in[name] = v

    # 请求体
    try:
        cl = int(environ.get("CONTENT_LENGTH") or 0)
    except (ValueError, TypeError):
        cl = 0
    body = b""
    if cl > 0:
        body = environ["wsgi.input"].read(cl)

    # OPTIONS 预检
    if method == "OPTIONS":
        status, payload, extra = app_dispatch(method, raw_path, query, headers_in, body)
        _start(status, extra, start_response)
        return [b""]

    # 业务 API
    if raw_path.startswith("/api/") or raw_path == "/api":
        status, payload, extra = app_dispatch(method, raw_path, query, headers_in, body)
        resp_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        base = {"Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store"}
        base.update(extra or {})
        _start(status, base, start_response)
        return [resp_body]

    # 非 API：托管前端静态资源（仅 GET）
    if method == "GET":
        status, body_bytes, shdrs = serve_static(raw_path)
        _start(status, shdrs, start_response)
        return [body_bytes]

    # 其他非 API 方法
    resp = json.dumps({"ok": False, "error": "method not allowed"}, ensure_ascii=False).encode("utf-8")
    hdrs = dict(CORS)
    hdrs["Content-Type"] = "application/json; charset=utf-8"
    _start(405, hdrs, start_response)
    return [resp]


# 本地调试：直接 `python api/index.py`
if __name__ == "__main__":
    from wsgiref.simple_server import make_server  # 仅本地调试用，标准库
    port = int(os.environ.get("PORT", "8090"))
    print("Serving on http://127.0.0.1:%d  (version %s)" % (port, APP_VERSION))
    make_server("127.0.0.1", port, app).serve_forever()
