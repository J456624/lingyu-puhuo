#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵鱼·商品铺货助手 —— 本地全栈服务
- 提供 app/ 静态资源(可安装 PWA)
- 提供 /images/ 商品图
- 提供 /api/products : 读取工作目录中最新一份「二次元闲鱼选品_Top10_*.json」→ 联网 + 每日自动更新
- 提供业务状态机 API(仿 1688 自动分销工具)：
    一键铺货 / 智能选品 / 一键采购 / 一键发货 / 一键售后 / 实时消息
  状态持久化到 app_state.json，SSE 推送实时消息。
"""
import http.server
import json
import os
import sys
import re
import time
import glob
import math
import random
import subprocess
import threading
import socketserver
import hashlib
import hmac as _hmac
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))          # 工作目录(含 server.py / JSON / images)
APP_DIR = os.path.join(BASE, "app")                         # 前端静态资源
WS = BASE
PORT = int(os.environ.get("PORT", "8080"))
JSON_GLOB = os.path.join(WS, "二次元闲鱼选品_Top10_*.json")
STATE_PATH = os.path.join(BASE, "app_state.json")

LOCK = threading.Lock()
SUBS = []                 # SSE 订阅者队列列表
SUB_LOCK = threading.Lock()

# ===== 状态持久化 =====
def default_state():
    return {
        "seq": 1000,
        "listings": [],    # {id, productId, platforms, price, status, createdAt}
        "orders": [],      # {id, productId, title, buyer, addr, spec, price, profit, cost, status, purchaseId, createdAt, refund}
        "purchases": [],   # {id, orderId, productId, supplier, cost, link, status, trackingNo, createdAt}
        "messages": [],    # {id, type, title, desc, ts, read}
        "aftersales": {"auto": True, "fast": True, "manual": False},
        "keys": [],          # 密钥登记表: {key, account, expiresAt, issuedAt, status, revokedAt, revokedBy, note}
        "revokedKeys": [],   # 已吊销密钥(快速查表，与 keys 中的 status=revoked 同步)
    }

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                st = json.load(f)
            # 兼容旧版：补齐新增字段（如密钥登记表）
            for k, v in default_state().items():
                st.setdefault(k, v)
            return st
        except Exception:
            pass
    return default_state()

def save_state(st):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)

STATE = load_state()

BUYERS = [
    ("兔兔酱**", "广州市天河区****"), ("芝麻馅**", "杭州市西湖区****"),
    ("kk_07**", "成都市武侯区****"), ("阿白**", "武汉市江汉区****"),
    ("喵了个喵**", "南京市鼓楼区****"), ("小鹿乱撞**", "西安市雁塔区****"),
    ("咸鱼翻身**", "重庆市渝中区****"), ("柚子味的**", "苏州市工业园区****"),
]
def pick_buyer():
    return random.choice(BUYERS)

def gen_tracking():
    carriers = ["YT", "ZTO", "YD", "JT", "SF"]
    c = random.choice(carriers)
    return c + str(random.randint(10**11, 10**12 - 1))

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def now_ts():
    return int(time.time() * 1000)

def push_message(st, mtype, title, desc):
    mid = "M%d" % (now_ts())
    st["messages"].append({"id": mid, "type": mtype, "title": title,
                           "desc": desc, "ts": now_ts(), "read": False})
    if len(st["messages"]) > 200:
        st["messages"] = st["messages"][-200:]
    broadcast({"type": "message", "payload": st["messages"][-1]})

def broadcast(obj):
    with SUB_LOCK:
        dead = []
        for q in SUBS:
            try:
                q.put(obj)
            except Exception:
                dead.append(q)
        for q in dead:
            SUBS.remove(q)

# ===== 密钥登记表（注册 / 校验 / 吊销）=====
# 与主/副软件共享同一签名算法(keylib.js)：HMAC-SHA256 + base20 编码
# 结构: [4位有效期编码][26位签名][2位校验位]，种子(seed)两端一致即"相互关联"。
CHARSET = '0123456789!@#$%^&*()'   # 10 数字 + 10 特殊字符 = 20 进制
BASE20 = 20
KEY_EPOCH = 1767225600000          # 2026-01-01T00:00:00Z（与 keylib.js 一致）
KEY_DAY = 86400000
DEFAULT_SEED = 'LINGYU@MAKE#2026*SEED'
MAKER_ACCOUNTS = set(a.strip() for a in os.environ.get('MAKER_ACCOUNTS', 'maker').split(',') if a.strip())
KEY_SEED = os.environ.get('KEY_SEED') or DEFAULT_SEED


def _to_base_n(num, length):
    num = int(num)
    chars = []
    for _ in range(length):
        chars.append(CHARSET[num % BASE20])
        num //= BASE20
    return ''.join(reversed(chars))


def _from_base_n(s):
    n = 0
    for c in s:
        idx = CHARSET.find(c)
        if idx < 0:
            return None
        n = n * BASE20 + idx
    return n


def _bytes_to_bigint(b):
    n = 0
    for byte in b:
        n = (n << 8) | byte
    return n


def _hash_mod(s, mod):
    # FNV-1a 32 位，与 keylib.js 的 Math.imul 行为一致
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xffffffff
    return h % mod


def _hmac_seed(seed, msg):
    return _hmac.new(seed.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()


def key_generate(account, days, seed=None):
    seed = seed or DEFAULT_SEED
    account = (account or '').strip()
    now = int(time.time() * 1000)
    today_offset = (now - KEY_EPOCH) // KEY_DAY
    valid = max(0, min(159999 - today_offset, int(days or 0)))
    expiry_days = today_offset + valid
    expiry_str = _to_base_n(expiry_days, 4)
    mac_bytes = _hmac_seed(seed, account + '|' + str(expiry_days))[:14]
    mac = _to_base_n(_bytes_to_bigint(mac_bytes), 26)
    checksum = _to_base_n(_hash_mod(expiry_str + mac + seed, 400), 2)
    return expiry_str + mac + checksum, expiry_days


def key_verify(key, account, seed=None):
    seed = seed or DEFAULT_SEED
    key = (key or '').strip()
    account = (account or '').strip()
    if len(key) != 32:
        return {'ok': False, 'reason': 'len'}
    if not re.fullmatch(r'[0-9!@#$%^&*()]+', key):
        return {'ok': False, 'reason': 'chars'}
    expiry_str, mac, checksum = key[:4], key[4:30], key[30:32]
    if _to_base_n(_hash_mod(expiry_str + mac + seed, 400), 2) != checksum:
        return {'ok': False, 'reason': 'checksum'}
    expiry_days = _from_base_n(expiry_str)
    if expiry_days is None:
        return {'ok': False, 'reason': 'expiry'}
    mac_calc = _to_base_n(_bytes_to_bigint(_hmac_seed(seed, account + '|' + str(expiry_days))[:14]), 26)
    if mac_calc != mac:
        return {'ok': False, 'reason': 'mac'}
    expires_at = KEY_EPOCH + expiry_days * KEY_DAY
    if expires_at < int(time.time() * 1000):
        return {'ok': False, 'reason': 'expired',
                'expiresAt': datetime.utcfromtimestamp(expires_at / 1000).isoformat() + 'Z'}
    return {'ok': True, 'expiresAt': datetime.utcfromtimestamp(expires_at / 1000).isoformat() + 'Z',
            'days': (expires_at - int(time.time() * 1000)) // KEY_DAY}


def key_fingerprint(seed=None):
    s = seed or DEFAULT_SEED
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xffffffff
    n = h
    digits = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    out = ''
    while n > 0:
        out = digits[n % 36] + out
        n //= 36
    return out.zfill(7)


def _resolve_seed(body):
    return (body.get('seed') or KEY_SEED) if isinstance(body, dict) else KEY_SEED


# ---- 密钥登记（灵钥生成后上报；签名须有效）----
def _keys_register(self):
    body = self._body()
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    seed = _resolve_seed(body)
    if not account or len(key) != 32:
        self._json({'ok': False, 'error': '账号或密钥无效'}, 400); return
    v = key_verify(key, account, seed)
    if not v['ok']:
        self._json({'ok': False, 'error': '密钥校验失败: ' + str(v.get('reason'))}, 400); return
    with LOCK:
        STATE.setdefault('revokedKeys', [])
        revoked = key in STATE['revokedKeys']
        rec = next((r for r in STATE['keys'] if r['key'] == key), None)
        if rec:
            rec['account'] = account
            rec['expiresAt'] = v['expiresAt']
            if rec.get('status') != 'revoked':
                rec['status'] = 'revoked' if revoked else 'active'
        else:
            STATE['keys'].append({
                'key': key, 'account': account, 'expiresAt': v['expiresAt'],
                'issuedAt': now_iso(), 'status': 'revoked' if revoked else 'active',
                'revokedAt': None, 'revokedBy': None, 'note': body.get('note', '') or ''})
        save_state(STATE)
    self._json({'ok': True, 'key': key, 'account': account,
                'expiresAt': v['expiresAt'], 'status': 'revoked' if revoked else 'active'})


# ---- 密钥校验（灵鱼登录时调用；支持吊销拦截）----
def _keys_verify(self):
    body = self._body()
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    seed = _resolve_seed(body)
    v = key_verify(key, account, seed)
    if not v['ok']:
        self._json({'ok': False, 'reason': v.get('reason'), 'expiresAt': v.get('expiresAt')}); return
    with LOCK:
        STATE.setdefault('revokedKeys', [])
        if key in STATE['revokedKeys']:
            self._json({'ok': False, 'reason': 'revoked'}); return
        rec = next((r for r in STATE['keys'] if r['key'] == key), None)
        if rec and rec.get('status') == 'revoked':
            self._json({'ok': False, 'reason': 'revoked'}); return
        self._json({'ok': True, 'account': account, 'expiresAt': v['expiresAt'],
                    'days': v.get('days'), 'registered': bool(rec)})


# ---- 密钥吊销（制造者凭 maker 密钥授权；或本人撤销自己的密钥）----
def _keys_revoke(self):
    body = self._body()
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    auth_key = (body.get('authKey') or '').strip()
    auth_account = (body.get('authAccount') or '').strip()
    seed = _resolve_seed(body)
    av = key_verify(auth_key, auth_account, seed)
    if not av['ok']:
        self._json({'ok': False, 'error': '管理凭证无效: ' + str(av.get('reason'))}, 403); return
    if auth_account not in MAKER_ACCOUNTS and auth_account != account:
        self._json({'ok': False, 'error': '无权限撤销该密钥'}, 403); return
    with LOCK:
        STATE.setdefault('revokedKeys', [])
        if key not in STATE['revokedKeys']:
            STATE['revokedKeys'].append(key)
        rec = next((r for r in STATE['keys'] if r['key'] == key), None)
        if rec:
            rec['status'] = 'revoked'
            rec['revokedAt'] = now_iso()
            rec['revokedBy'] = auth_account
        else:
            STATE['keys'].append({
                'key': key, 'account': account, 'expiresAt': None, 'issuedAt': None,
                'status': 'revoked', 'revokedAt': now_iso(), 'revokedBy': auth_account, 'note': '外部吊销'})
        save_state(STATE)
        push_message(STATE, 'system', '密钥已吊销 · ' + account,
                     '账号 %s 的密钥 %s… 已被制造者吊销，该账号将无法登录' % (account, key[:6]))
    self._json({'ok': True, 'account': account, 'key': key, 'status': 'revoked'})


# ---- 制造者查询已登记密钥列表 ----
def _keys_list(self):
    q = parse_qs(urlparse(self.path).query)
    maker_key = (q.get('makerKey', [''])[0] or '').strip()
    maker_account = (q.get('makerAccount', [''])[0] or '').strip()
    seed = (q.get('seed', [''])[0] or '') or KEY_SEED
    av = key_verify(maker_key, maker_account, seed)
    if not av['ok'] or maker_account not in MAKER_ACCOUNTS:
        self._json({'ok': False, 'error': '无权限'}, 403); return
    with LOCK:
        keys = [dict(k) for k in STATE['keys']]
        revoked = list(STATE.get('revokedKeys', []))
    self._json({'ok': True, 'keys': keys, 'revokedKeys': revoked})

# ===== 商品读取(供订单取材) =====
def latest_top10_path():
    files = glob.glob(JSON_GLOB)
    return max(files, key=os.path.getmtime) if files else None

def build_products():
    path = latest_top10_path()
    if not path:
        return {"updated": None, "source": "none", "products": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"updated": None, "source": "error:%s" % e, "products": []}
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    date_str = date_match.group(1) if date_match else ""
    img_dir = os.path.join(WS, "images", date_str) if date_str else ""
    out = []
    for p in data.get("products", []):
        rank = p.get("rank", 0)
        offer_id = p.get("offerId", "")
        local_img = ""
        if img_dir:
            cand = os.path.join(img_dir, "%02d_%s.jpg" % (rank, offer_id))
            if os.path.exists(cand):
                local_img = "/images/%s/%02d_%s.jpg" % (date_str, rank, offer_id)
        out.append({
            "id": offer_id,
            "rank": rank,
            "title": p.get("xianyu_title") or p.get("title", ""),
            "srcTitle": p.get("title", ""),
            "image": local_img or (p.get("imageUrl") or ""),
            "imageRemote": p.get("imageUrl") or "",
            "suggestPrice": p.get("suggest_price", 0),
            "consignPrice": p.get("consignPrice", 0),
            "profit": p.get("profit", 0),
            "margin": p.get("margin", 0),
            "sales": p.get("demand_label", ""),
            "src": p.get("src", ""),
            "tier": p.get("tier", "利润款"),
            "supplier": p.get("company", ""),
            "link": p.get("asinUrl", ""),
            "link1688": p.get("asinUrl") or ("https://detail.1688.com/offer/%s.html" % offer_id),
            "leadTime": p.get("deliveryTime", "—"),
            "body": p.get("xianyu_body", ""),
            "tags": p.get("tags", []),
        })
    return {"updated": date_str, "source": os.path.basename(path), "products": out}

def product_by_id(pid):
    for p in build_products().get("products", []):
        if p["id"] == pid:
            return p
    return None

def new_id(st, prefix):
    st["seq"] += 1
    return "%s%d" % (prefix, st["seq"])

# ===== HTTP 处理 =====
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

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

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/products":
            self._json(build_products()); return
        if path == "/api/health":
            self._json({"ok": True, "latest": (latest_top10_path() or "").replace(WS, ""),
                        "orders": len(STATE["orders"]), "listings": len(STATE["listings"]),
                        "keySeedFingerprint": key_fingerprint(KEY_SEED)}); return
        if path == "/api/state":
            with LOCK:
                self._json({"listings": STATE["listings"], "orders": STATE["orders"],
                            "purchases": STATE["purchases"], "messages": STATE["messages"],
                            "aftersales": STATE["aftersales"]}); return
        if path == "/api/keys":
            _keys_list(self); return
        if path == "/api/stream":
            self._sse(); return
        if path.startswith("/images/"):
            fpath = os.path.normpath(os.path.join(WS, parsed.path.lstrip("/")))
            if os.path.isfile(fpath):
                self._file(fpath); return
            self.send_error(404); return
        super().do_GET()

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        q = __import__("queue").Queue()
        with SUB_LOCK:
            SUBS.append(q)
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    obj = q.get(timeout=20)
                    self.wfile.write(("data: %s\n\n" % json.dumps(obj, ensure_ascii=False)).encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except Exception:
            pass
        finally:
            with SUB_LOCK:
                if q in SUBS:
                    SUBS.remove(q)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        # /api/orders/{id}/{action}
        m = re.match(r"^/api/orders/([^/]+)/(purchase|ship|request-refund|aftersale)$", path)
        if m:
            oid, action = m.group(1), m.group(2)
            return self._order_action(oid, action)
        if path == "/api/listings":
            return self._listings()
        m = re.match(r"^/api/listings/([^/]+)/(handoff|confirm)$", path)
        if m:
            lid, action = m.group(1), m.group(2)
            return self._listing_action(lid, action)
        if path == "/api/orders/simulate":
            return self._simulate_order()
        if path == "/api/aftersales":
            return self._aftersales()
        if path == "/api/keys/register":
            return _keys_register(self)
        if path == "/api/keys/verify":
            return _keys_verify(self)
        if path == "/api/keys/revoke":
            return _keys_revoke(self)
        if path == "/api/select/refresh":
            return self._select_refresh()
        if path == "/api/reset":
            return self._reset()
        self._json({"ok": False, "error": "unknown endpoint"}, 404)

    # ---- 一键铺货（唤起手机内已登录的闲鱼App，后端仅记录状态）----
    def _listings(self):
        body = self._body()
        pid = body.get("productId")
        platforms = body.get("platforms") or ["xianyu"]
        price = body.get("price")
        handoff = body.get("handoff", False)
        p = product_by_id(pid)
        if not p:
            self._json({"ok": False, "error": "商品不存在"}, 400); return
        if price is None:
            price = p["suggestPrice"]
        with LOCK:
            # 同款已铺货则复用，避免重复
            existing = next((l for l in reversed(STATE["listings"]) if l["productId"] == pid), None)
            if existing:
                lid = existing["id"]
                if existing["status"] != "已发布":
                    existing["status"] = "待闲鱼确认" if handoff else "已发布"
                    existing["platforms"] = platforms
                    existing["price"] = price
            else:
                lid = new_id(STATE, "L")
                STATE["listings"].append({
                    "id": lid, "productId": pid, "platforms": platforms,
                    "price": price, "status": ("待闲鱼确认" if handoff else "已发布"),
                    "createdAt": now_iso()})
            save_state(STATE)
            if handoff:
                push_message(STATE, "publish", "已唤起闲鱼App · 待确认",
                             "《%s》已转交闲鱼App铺货，请在闲鱼内完成发布后点「确认已上架」" % p["title"])
            else:
                for pl in platforms:
                    push_message(STATE, "publish", "铺货成功 · %s" % pl,
                                 "《%s》已上架到 %s，建议价 ¥%.1f" % (p["title"], pl, price))
        self._json({"ok": True, "listingId": lid, "handoff": bool(handoff), "platforms": platforms})

    def _listing_action(self, lid, action):
        with LOCK:
            l = next((x for x in STATE["listings"] if x["id"] == lid), None)
            if not l:
                self._json({"ok": False, "error": "铺货记录不存在"}, 404); return
            p = product_by_id(l["productId"]) or {}
            if action == "confirm":
                if l["status"] == "已发布":
                    self._json({"ok": True, "status": l["status"]}); return
                l["status"] = "已发布"
                save_state(STATE)
                push_message(STATE, "publish", "铺货成功 · 闲鱼",
                             "《%s》已在闲鱼App确认上架，建议价 ¥%.1f" % (p.get("title", "商品"), l["price"]))
                self._json({"ok": True, "status": "已发布"}); return
            if action == "handoff":
                l["status"] = "待闲鱼确认"
                save_state(STATE)
                self._json({"ok": True, "status": "待闲鱼确认"}); return
        self._json({"ok": False, "error": "unsupported"}, 400)

    # ---- 模拟接单 ----
    def _simulate_order(self):
        body = self._body()
        pid = body.get("productId")
        p = product_by_id(pid) if pid else None
        if not p:
            prods = build_products().get("products", [])
            p = random.choice(prods) if prods else None
        if not p:
            self._json({"ok": False, "error": "暂无商品"}, 400); return
        buyer, addr = pick_buyer()
        refund = body.get("refund", False)
        status = "退款中" if refund else "待采购"
        with LOCK:
            oid = new_id(STATE, "O")
            cost = p["consignPrice"]
            profit = round(p["suggestPrice"] - cost - 2, 1)
            STATE["orders"].append({
                "id": oid, "productId": pid, "title": p["title"],
                "buyer": buyer, "addr": addr,
                "spec": "默认规格 · 1件", "price": p["suggestPrice"],
                "profit": profit, "cost": cost, "status": status,
                "purchaseId": None, "createdAt": now_iso(), "refund": refund})
            save_state(STATE)
            if refund:
                push_message(STATE, "aftersale", "退款申请 · %s" % p["title"],
                             "买家 %s 申请仅退款 ¥%.1f，待你一键售后处理" % (buyer, p["suggestPrice"]))
            else:
                push_message(STATE, "order", "新订单 · %s" % p["title"],
                             "买家 %s 已付款 ¥%.1f，待你一键采购代发" % (buyer, p["suggestPrice"]))
        self._json({"ok": True, "orderId": oid, "status": status})

    # ---- 一键采购 / 一键发货 / 退款申请 / 一键售后 ----
    def _order_action(self, oid, action):
        with LOCK:
            o = next((x for x in STATE["orders"] if x["id"] == oid), None)
            if not o:
                self._json({"ok": False, "error": "订单不存在"}, 404); return
            p = product_by_id(o["productId"]) or {}
            if action == "purchase":
                if o["status"] not in ("待采购",):
                    self._json({"ok": False, "error": "当前状态不可采购(%s)" % o["status"]}, 400); return
                o["status"] = "待发货"
                pid_ = new_id(STATE, "P")
                STATE["purchases"].append({
                    "id": pid_, "orderId": oid, "productId": o["productId"],
                    "supplier": p.get("supplier", o.get("supplier", "—")),
                    "cost": o["cost"], "link": p.get("link", ""),
                    "status": "已下单", "trackingNo": None, "createdAt": now_iso()})
                o["purchaseId"] = pid_
                save_state(STATE)
                push_message(STATE, "purchase", "采购完成 · %s" % o["title"],
                             "已向 1688 %s 代付 ¥%.1f，等待厂家发货" % (p.get("supplier", "供应商"), o["cost"]))
                self._json({"ok": True, "purchaseId": pid_, "orderStatus": o["status"]}); return
            if action == "ship":
                if o["status"] not in ("待发货",):
                    self._json({"ok": False, "error": "当前状态不可发货(%s)" % o["status"]}, 400); return
                pur = next((x for x in STATE["purchases"] if x["id"] == o["purchaseId"]), None)
                if pur:
                    pur["status"] = "已发货"
                    pur["trackingNo"] = gen_tracking()
                o["status"] = "待收货"
                save_state(STATE)
                push_message(STATE, "logistics", "物流已发出 · %s" % o["title"],
                             "运单号 %s 已回传闲鱼，买家可查收" % (pur["trackingNo"] if pur else "—"))
                self._json({"ok": True, "trackingNo": pur["trackingNo"] if pur else None, "orderStatus": o["status"]}); return
            if action == "request-refund":
                if o["status"] in ("待收货", "待发货", "待采购"):
                    o["status"] = "退款中"; o["refund"] = True
                    save_state(STATE)
                    push_message(STATE, "aftersale", "退款申请 · %s" % o["title"],
                                 "买家 %s 申请仅退款 ¥%.1f" % (o["buyer"], o["price"]))
                    self._json({"ok": True, "orderStatus": o["status"]}); return
                self._json({"ok": False, "error": "当前状态不可申请退款(%s)" % o["status"]}, 400); return
            if action == "aftersale":
                if o["status"] != "退款中":
                    self._json({"ok": False, "error": "订单非退款中，无需售后"}, 400); return
                o["status"] = "已退款"
                o["refund"] = "done"
                save_state(STATE)
                push_message(STATE, "aftersale", "售后完成 · %s" % o["title"],
                             "已自动向 1688 厂商同步退款，¥%.1f 退回买家" % o["price"])
                self._json({"ok": True, "orderStatus": o["status"]}); return
        self._json({"ok": False, "error": "unsupported"}, 400)

    # ---- 售后设置 ----
    def _aftersales(self):
        body = self._body()
        with LOCK:
            if "auto" in body: STATE["aftersales"]["auto"] = bool(body["auto"])
            if "fast" in body: STATE["aftersales"]["fast"] = bool(body["fast"])
            if "manual" in body: STATE["aftersales"]["manual"] = bool(body["manual"])
            save_state(STATE)
        self._json({"ok": True, "aftersales": STATE["aftersales"]})

    # ---- 智能选品：重拉 1688 实时精选 ----
    def _select_refresh(self):
        py = os.path.join(WS, "daily_pipeline.py")
        if not os.path.exists(py):
            self._json({"ok": False, "error": "未找到 daily_pipeline.py"}, 400); return
        try:
            env = dict(os.environ)
            env.setdefault("LINKFOX_AGENT_API_KEY", os.environ.get("LINKFOX_AGENT_API_KEY", ""))
            r = subprocess.run([PYTHON, py, WS], capture_output=True, text=True, timeout=180, env=env)
            if r.returncode != 0:
                self._json({"ok": False, "error": (r.stderr or "pipeline failed")[:300]}, 500); return
        except Exception as e:
            self._json({"ok": False, "error": str(e)[:200]}, 500); return
        self._json(build_products())

    # ---- 重置演示 ----
    def _reset(self):
        with LOCK:
            global STATE
            STATE = default_state()
            save_state(STATE)
            push_message(STATE, "system", "演示数据已重置", "已清空铺货/订单/消息，可重新体验全流程")
        self._json({"ok": True})

    def log_message(self, fmt, *args):
        pass


PYTHON = os.environ.get("PYTHON", sys.executable)
try:
    import queue  # noqa
except Exception:
    pass

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(BASE)
    httpd = Server(("0.0.0.0", PORT), Handler)
    print("灵鱼铺货后台已启动: http://0.0.0.0:%d  (Ctrl+C 停止)" % PORT)
    print("数据来源匹配: %s" % JSON_GLOB)
    httpd.serve_forever()
