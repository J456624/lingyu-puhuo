#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵鱼·商品铺货助手 —— 本地常驻服务（开发 / 内网使用）
- 同源托管 app/ 静态资源(可安装 PWA) 与 /images/ 商品图
- 所有 /api/* 业务由 core.app_dispatch 统一处理
- 公网部署请用 Vercel：api/[...path].py（Serverless 函数）+ vercel.json
"""
import os
import sys
import json
import socketserver
import http.server
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import app_dispatch, APP_DIR, WS, PORT

import core as _core


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=APP_DIR, **k)

    def _json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fpath):
        ext = os.path.splitext(fpath)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".svg": "image/svg+xml", ".gif": "image/gif", ".webp": "image/webp",
                ".webmanifest": "application/manifest+json"}.get(ext, "application/octet-stream")
        with open(fpath, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/images/"):
            fpath = os.path.normpath(os.path.join(WS, parsed.path.lstrip("/")))
            if os.path.isfile(fpath):
                self._file(fpath); return
            self.send_error(404); return
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        status, payload, extra = app_dispatch("GET", path, query, dict(self.headers), b"")
        self._json(payload, status)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b""
        status, payload, extra = app_dispatch("POST", path, {}, dict(self.headers), raw)
        self._json(payload, status)

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = Server(("0.0.0.0", PORT), Handler)
    print("灵鱼铺货后台已启动: http://0.0.0.0:%d  (Ctrl+C 停止)" % PORT)
    print("数据来源匹配: %s" % _core.JSON_GLOB)
    httpd.serve_forever()
