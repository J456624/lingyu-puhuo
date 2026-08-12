# -*- coding: utf-8 -*-
"""
状态持久化层（Vercel 友好）：
- 若配置了 UPSTASH_REST_URL / UPSTASH_REST_TOKEN（Upstash Redis REST，免费），走 Redis；
- 否则回退本地 app_state.json（本地 server_local.py 使用）。
Upstash REST 仅用标准库 urllib，无需任何第三方依赖。
"""
import os
import json
import urllib.request

UPSTASH_URL = os.environ.get("UPSTASH_REST_URL", "").strip().rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REST_TOKEN", "").strip()
LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_state.json")
REDIS_KEY = "lingyu_state"

# 当前持久化模式：两个 Upstash 变量都非空 → upstash；否则 → 内存兜底（不跨实例持久）
STORAGE_MODE = "upstash" if (UPSTASH_URL and UPSTASH_TOKEN) else "memory"

# 只读文件系统（如 Vercel 未配 Upstash）时的内存兜底：本次调用/热实例内可读写，不跨实例持久。
_MEMORY_STATE = None


def _upstash_get():
    req = urllib.request.Request(
        UPSTASH_URL + "/get/" + REDIS_KEY,
        headers={"Authorization": "Bearer " + UPSTASH_TOKEN},
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        data = json.loads(r.read())
    if data.get("result"):
        return json.loads(data["result"])
    return None


def _upstash_set(value):
    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        UPSTASH_URL + "/set/" + REDIS_KEY,
        data=body,
        headers={"Authorization": "Bearer " + UPSTASH_TOKEN,
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        r.read()


def load_state_raw(default):
    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            st = _upstash_get()
            if st is not None:
                for k, v in default.items():
                    st.setdefault(k, v)
                return st
        except Exception:
            pass
    if _MEMORY_STATE is not None:
        st = _MEMORY_STATE
        for k, v in default.items():
            st.setdefault(k, v)
        return st
    if os.path.exists(LOCAL_PATH):
        try:
            with open(LOCAL_PATH, encoding="utf-8") as f:
                st = json.load(f)
            for k, v in default.items():
                st.setdefault(k, v)
            return st
        except Exception:
            pass
    return default


def save_state_raw(st):
    global _MEMORY_STATE
    if UPSTASH_URL and UPSTASH_TOKEN:
        try:
            _upstash_set(st)
            return
        except Exception:
            pass
    # 回退：本地文件（本地开发，可写）或内存（Vercel 只读 FS，避免 500）
    try:
        tmp = LOCAL_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, LOCAL_PATH)
        _MEMORY_STATE = None
        return
    except Exception:
        _MEMORY_STATE = st
