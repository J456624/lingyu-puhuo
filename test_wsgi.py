# -*- coding: utf-8 -*-
"""本地离线验证 api/index.py 的路由还原逻辑（无需 Vercel）。"""
import sys, os, io, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api"))
import index as idx

def call(method, path_info, query_string=""):
    out = io.BytesIO()
    captured = {}
    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path_info,
        "QUERY_STRING": query_string,
        "wsgi.input": io.BytesIO(b""),
        "CONTENT_LENGTH": "0",
        "HTTP_HOST": "localhost",
    }
    body = b"".join(idx.app(environ, start_response))
    return captured.get("status"), body

print("=== Case 1: 本地直跑 PATH_INFO=/api/health (无 p 参数) ===")
st, b = call("GET", "/api/health")
print("status:", st)
try:
    print("json:", json.loads(b.decode("utf-8")))
except Exception as e:
    print("body:", b[:200])

print("\n=== Case 2: Vercel 重写 PATH_INFO=/api/index.py, p=api/health ===")
st, b = call("GET", "/api/index.py", "p=api/health")
print("status:", st)
try:
    print("json:", json.loads(b.decode("utf-8")))
except Exception as e:
    print("body:", b[:200])

print("\n=== Case 3: 根路径重写 PATH_INFO=/api/index.py, p= (空) ===")
st, b = call("GET", "/api/index.py", "p=")
print("status:", st)
print("is_html:", b[:60].decode("utf-8", "replace").replace("\n", " "))
print("len:", len(b))

print("\n=== Case 4: 静态资源重写 p=app.js ===")
st, b = call("GET", "/api/index.py", "p=app.js")
print("status:", st, "len:", len(b), "head:", b[:40])

print("\n=== Case 5: 带查询参数的 API /api/products?category=x (Vercel 合并查询) ===")
st, b = call("GET", "/api/index.py", "p=api/products&category=x")
print("status:", st)
try:
    print("json:", json.loads(b.decode("utf-8")).get("ok"), json.loads(b.decode("utf-8")).get("error"))
except Exception as e:
    print("body:", b[:200])

print("\n=== Case 6: __debug 路由 ===")
st, b = call("GET", "/api/index.py", "p=api/__debug")
print("status:", st)
try:
    print("json:", json.loads(b.decode("utf-8")))
except Exception as e:
    print("body:", b[:200])

print("\n=== Case 7: 灵钥挂在 /keygen (Vercel 重写 p=keygen) ===")
st, b = call("GET", "/api/index.py", "p=keygen")
print("status:", st, "head:", b[:60].decode("utf-8", "replace").replace("\n", " "))

print("\n=== Case 8: 灵钥静态资源 p=keygen/app.js ===")
st, b = call("GET", "/api/index.py", "p=keygen/app.js")
print("status:", st, "len:", len(b), "head:", b[:40])
