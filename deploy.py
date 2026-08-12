# -*- coding: utf-8 -*-
"""通过 Vercel REST API 直接部署当前磁盘上的代码到生产环境（无需 git push）。"""
import os, sys, base64, json, time
import urllib.request, urllib.error

TOKEN = os.environ.get("VERCEL_TOKEN", "")
TEAM = "team_JkplRRR0b1fGVJpOAOQNKmiu"
PROJECT = "prj_JimdQhGo0Qv5nzM3kpWj3bXARvtD"
ROOT = os.path.dirname(os.path.abspath(__file__))

SKIP_DIRS = {".git", ".workbuddy", "node_modules", "__pycache__", ".venv", "venv",
             "env", "dist", "build", ".idea", ".vscode", ".next", ".vercel"}
SKIP_FILES = {".env", ".env.local", "deploy.py", "test_wsgi.py", ".gitignore"}
SKIP_EXT = {".pyc", ".log", ".tmp"}


# 只上传灵鱼铺货 App 真正需要的文件，避免把图片/缓存/报告等无关产物打进部署包（>10MB 会被拒）。
ALLOW = [
    "api/index.py", "api/core.py", "api/store.py",
    "app/index.html", "app/app.js", "app/data.js", "app/deeplink.js",
    "app/icon.svg", "app/keylib.js", "app/manifest.webmanifest",
    "app/products.js", "app/products.json", "app/style.css", "app/sw.js",
    "app-keygen/index.html", "app-keygen/app.js", "app-keygen/deeplink.js",
    "app-keygen/icon.svg", "app-keygen/keylib.js", "app-keygen/manifest.webmanifest",
    "app-keygen/style.css", "app-keygen/sw.js",
    "vercel.json", "requirements.txt",
]


def collect():
    files = []
    for rel in ALLOW:
        full = os.path.join(ROOT, rel)
        if os.path.isfile(full):
            files.append((rel, full))
        else:
            print("  ! MISSING (skipped):", rel)
    return sorted(files)


def main():
    if not TOKEN:
        print("ERROR: 请先设置环境变量 VERCEL_TOKEN（Vercel API Token），例如：")
        print("  export VERCEL_TOKEN=vcp_xxx")
        sys.exit(1)
    files = collect()
    payload_files = []
    for rel, full in files:
        with open(full, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        payload_files.append({"file": rel, "data": data, "encoding": "base64"})
        print("  +", rel)
    body = {"name": "lingyu-puhuo", "target": "production", "files": payload_files}
    url = "https://api.vercel.com/v13/deployments?teamId=%s&projectId=%s" % (TEAM, PROJECT)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % TOKEN, "Content-Type": "application/json"},
        method="POST")
    print("\nUploading %d files to Vercel..." % len(payload_files))
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            res = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.read().decode("utf-8")[:2000])
        sys.exit(1)
    dpl_id = res.get("id")
    print("Deployment created:", dpl_id, "| url:", res.get("url"))
    if res.get("error"):
        print("API error:", res.get("error"))
    for i in range(60):
        time.sleep(5)
        gurl = "https://api.vercel.com/v13/deployments/%s?teamId=%s" % (dpl_id, TEAM)
        greq = urllib.request.Request(gurl, headers={"Authorization": "Bearer %s" % TOKEN})
        with urllib.request.urlopen(greq, timeout=30) as g:
            gres = json.loads(g.read().decode("utf-8"))
        rs = gres.get("readyState")
        print("  [%d] readyState=%s" % (i, rs))
        if rs == "READY":
            print("DEPLOYED & READY ->", gres.get("url"))
            print("inspector:", gres.get("inspectorUrl"))
            return
        if rs == "ERROR":
            print("DEPLOY ERROR:", json.dumps(gres, ensure_ascii=False)[:2000])
            return
    print("Timed out waiting for READY")


if __name__ == "__main__":
    main()
