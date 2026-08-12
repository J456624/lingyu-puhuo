# -*- coding: utf-8 -*-
"""
Vercel Serverless 函数入口（Python，纯标准库，无任何第三方依赖）。

统一网关：
  - /api/*  -> core.app_dispatch（业务 API，返回 JSON）
  - 其余路径 -> 从 app/ 目录托管前端静态文件（SPA 入口 + 资源）

路径还原（关键）：
  vercel.json 的全局 rewrite 把任意路径重写到 /api/index.py，
  重写后 WSGI 的 PATH_INFO 会变成目标路径 "/api/index.py" 而非原始请求路径。
  因此我们用 rewrite 的捕获组把原始路径编码进查询参数 ?p=$1，
  本入口优先用 p 还原真实请求路径；本地直跑时 PATH_INFO 即真实路径，亦兼容。
  同时保留一份多源兜底（REQUEST_URI / X-Original-Url 等），以防 ?p 缺失。
"""
import sys
import os
import json
import mimetypes
from urllib.parse import parse_qs

# 把项目根与 api/ 目录加入 sys.path（core/store 在 api/ 同级或同目录）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)
API_DIR = os.path.dirname(os.path.abspath(__file__))
if API_DIR not in sys.path:
    sys.path.append(API_DIR)

STATIC_DIR = os.path.join(ROOT, "app")
KEYGEN_DIR = os.path.join(ROOT, "app-keygen")
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
    """返回 (status, body_bytes, headers_dict)。从 app/（或 /keygen 下的 app-keygen/）读静态文件；未知路径回退 index.html。"""
    base_dir = STATIC_DIR
    # 灵钥·密钥生成器挂在 /keygen 下，使用同域后端（API 走相对 /api/*）
    if path == "/keygen" or path.startswith("/keygen/"):
        base_dir = KEYGEN_DIR
        rel = path[len("/keygen"):].split("?")[0].lstrip("/")
    else:
        rel = path.split("?")[0].lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = "index.html"
    full = os.path.normpath(os.path.join(base_dir, rel))
    # 防目录穿越
    if not (full == base_dir or full.startswith(base_dir + os.sep)):
        return (403, b"forbidden", {"Access-Control-Allow-Origin": "*"})
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    if not os.path.isfile(full):
        # 客户端路由兜底：返回 SPA 入口
        full = os.path.join(base_dir, "index.html")
    try:
        with open(full, "rb") as f:
            data = f.read()
    except Exception:
        return (404, b"not found", {"Access-Control-Allow-Origin": "*"})
    return (200, data, {"Content-Type": _content_type(full),
                        "Cache-Control": "public, max-age=300"})


def _start(status, extra_headers, start_response):
    reason = _STATUS_REASON.get(status, "OK")
    hdrs = []
    for k, v in (extra_headers or {}).items():
        hdrs.append((k, str(v)))
    start_response("%d %s" % (status, reason), hdrs)


def _real_path(environ):
    """还原真实请求路径。优先用 rewrite 注入的 ?p= 参数。"""
    query_string = environ.get("QUERY_STRING") or ""
    query = parse_qs(query_string)
    p = (query.get("p") or [""])[0]
    if p:
        return "/" + p.lstrip("/")
    # 兜底：本地直跑或无 ?p 时回退到 PATH_INFO
    path = environ.get("PATH_INFO") or "/"
    if path == "/api/index.py":
        # 被重写到函数入口但拿不到原始路径，尝试常见原始路径字段
        for key in ("HTTP_X_ORIGINAL_URL", "HTTP_X_FORWARDED_URI",
                    "HTTP_X_VERCEL_ORIGINAL_PATH", "REQUEST_URI",
                    "HTTP_X_REWRITE_URL", "PATH_TRANSLATED"):
            cand = environ.get(key)
            if cand:
                return cand.split("?")[0]
        return "/"
    return path


def app(environ, start_response):
    try:
        # 延迟导入：让导入失败也能以 JSON 形式暴露真实错误
        from core import app_dispatch, CORS, APP_VERSION

        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        raw_path = _real_path(environ)

        # 内置诊断路由（仅排错用，不对外暴露业务）
        if raw_path == "/api/__debug":
            dump = {
                "ok": True, "debug": True, "method": method,
                "raw_path": raw_path,
                "QUERY_STRING": environ.get("QUERY_STRING"),
                "env_keys": sorted(environ.keys()),
            }
            body = json.dumps(dump, ensure_ascii=False).encode("utf-8")
            _start(200, {"Content-Type": "application/json; charset=utf-8"}, start_response)
            return [body]

        query_string = environ.get("QUERY_STRING") or ""
        query = parse_qs(query_string)
        query.pop("p", None)  # 移除 rewrite 注入的路径参数，业务不应感知

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
        _start(405, {"Content-Type": "application/json; charset=utf-8",
                     "Access-Control-Allow-Origin": "*"}, start_response)
        return [resp]

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        err_body = json.dumps(
            {"ok": False, "error": "handler_exception", "detail": tb},
            ensure_ascii=False
        ).encode("utf-8")
        try:
            start_response("500 Internal Server Error",
                           [("Content-Type", "application/json; charset=utf-8")])
        except Exception:
            pass
        return [err_body]


# 本地调试：直接 `python api/index.py`
if __name__ == "__main__":
    from wsgiref.simple_server import make_server  # 仅本地调试用，标准库
    port = int(os.environ.get("PORT", "8090"))
    print("Serving on http://127.0.0.1:%d" % port)
    make_server("127.0.0.1", port, app).serve_forever()
