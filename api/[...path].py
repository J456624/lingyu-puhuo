# -*- coding: utf-8 -*-
"""
Vercel Serverless 函数入口（Python）。
统一网关：
  - /api/*  → core.app_dispatch（业务 API）
  - 其余路径 → 从 app/ 目录托管前端静态文件（SPA + 资源）
不再依赖 vercel.json 的静态重写，避免静态托管失效导致根路径落到函数。
"""
import sys
import os
import json
import mimetypes

from werkzeug.wrappers import Request, Response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from core import app_dispatch, CORS, APP_VERSION

STATIC_DIR = os.path.join(ROOT, "app")
TEXT_TYPES = {"text/html", "text/css", "application/javascript", "application/json",
              "image/svg+xml", "application/manifest+json"}


def _content_type(path):
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if ctype in TEXT_TYPES:
        ctype += "; charset=utf-8"
    return ctype


def serve_static(path):
    """从 app/ 目录返回静态文件；未知路径回退到 index.html（SPA 兜底）。"""
    rel = path.split("?")[0].lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = "index.html"
    full = os.path.normpath(os.path.join(STATIC_DIR, rel))
    # 防目录穿越
    if not (full == STATIC_DIR or full.startswith(STATIC_DIR + os.sep)):
        return Response("forbidden", status=403, headers=CORS)
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    if not os.path.isfile(full):
        # 客户端路由兜底：返回 SPA 入口
        full = os.path.join(STATIC_DIR, "index.html")
    try:
        with open(full, "rb") as f:
            data = f.read()
    except Exception:
        return Response("not found", status=404, headers=CORS)
    return Response(data, status=200,
                    headers={"Content-Type": _content_type(full),
                             "Cache-Control": "public, max-age=300"})


@Request.application
def handler(request):
    method = (request.method or "GET").upper()
    path = request.path or "/"
    query = request.args.to_dict() if hasattr(request.args, "to_dict") else dict(request.args)
    headers = dict(request.headers)
    raw = request.get_data()

    if method == "OPTIONS":
        return Response("", status=204, headers=dict(CORS))

    if path.startswith("/api/") or path == "/api":
        status, payload, extra = app_dispatch(method, path, query, headers, raw)
        resp_headers = {"Content-Type": "application/json; charset=utf-8",
                        "Cache-Control": "no-store"}
        resp_headers.update(extra or {})
        return Response(json.dumps(payload, ensure_ascii=False), status=status,
                        headers=resp_headers)

    # 非 API：托管前端静态资源（仅 GET）
    if method == "GET":
        return serve_static(path)
    return Response(json.dumps({"ok": False, "error": "method not allowed"},
                               ensure_ascii=False),
                    status=405, headers={"Content-Type": "application/json; charset=utf-8"})


# 便于本地调试：直接 `python api/\[...path\].py` 时跑一个临时服务
if __name__ == "__main__":
    from werkzeug.serving import run_simple
    run_simple("127.0.0.1", 8090, handler)
