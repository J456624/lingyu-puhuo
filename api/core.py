# -*- coding: utf-8 -*-
"""
灵鱼·商品铺货助手 —— 共享后端内核
本地 server.py 与 Vercel 函数 api/[...path].py 共用本模块。
对外唯一入口：app_dispatch(method, path, query, headers, raw_body) -> (status, payload, extra_headers)
状态持久化走 store（Upstash Redis / 本地文件）。SSE 已改为前端轮询，故本模块不再推送。
"""
import os
import re
import time
import glob
import json
import math
import random
import subprocess
import threading
import hashlib
import hmac as _hmac
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# ---------- 路径 / 运行参数 ----------
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))     # 项目根(server.py/core.py 所在目录)
WS = _CORE_DIR
APP_DIR = os.path.join(_CORE_DIR, "app")
JSON_GLOB = os.path.join(WS, "二次元闲鱼选品_Top10_*.json")
PORT = int(os.environ.get("PORT", "8080"))
PYTHON = os.environ.get("PYTHON", "python3")
LINKFOX_KEY = os.environ.get("LINKFOX_AGENT_API_KEY", "")

LOCK = threading.Lock()

# ---------- 密钥算法常量（与 app/keylib.js 一致）----------
CHARSET = '0123456789!@#$%^&*()'   # 10 数字 + 10 特殊字符 = 20 进制
BASE20 = 20
KEY_EPOCH = 1767225600000          # 2026-01-01T00:00:00Z
KEY_DAY = 86400000
DEFAULT_SEED = 'LINGYU@MAKE#2026*SEED'
MAKER_ACCOUNTS = set(a.strip() for a in os.environ.get('MAKER_ACCOUNTS', 'maker').split(',') if a.strip())
KEY_SEED = os.environ.get('KEY_SEED') or DEFAULT_SEED

from store import load_state_raw, save_state_raw, STORAGE_MODE

STATE = None  # 每次请求由 app_dispatch 载入


def default_state():
    return {
        "seq": 1000,
        "listings": [],
        "orders": [],
        "purchases": [],
        "messages": [],
        "aftersales": {"auto": True, "fast": True, "manual": False},
        "keys": [],
        "revokedKeys": [],
    }


def load_state():
    return load_state_raw(default_state())


def save_state(st):
    save_state_raw(st)


# ---------- 工具 ----------
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
    return random.choice(carriers) + str(random.randint(10**11, 10**12 - 1))

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def now_ts():
    return int(time.time() * 1000)

def push_message(st, mtype, title, desc):
    mid = "M%d" % now_ts()
    st["messages"].append({"id": mid, "type": mtype, "title": title,
                           "desc": desc, "ts": now_ts(), "read": False})
    if len(st["messages"]) > 200:
        st["messages"] = st["messages"][-200:]
    # SSE 已改为前端轮询，无需服务端推送

def broadcast(obj):
    pass


# ---------- 密钥算法 ----------
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


# ---------- 密钥登记表处理 ----------
def keys_register(body, st):
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    seed = _resolve_seed(body)
    if not account or len(key) != 32:
        return (400, {"ok": False, "error": "账号或密钥无效"})
    v = key_verify(key, account, seed)
    if not v['ok']:
        return (400, {"ok": False, "error": "密钥校验失败: " + str(v.get('reason'))})
    st.setdefault('revokedKeys', [])
    revoked = key in st['revokedKeys']
    rec = next((r for r in st['keys'] if r['key'] == key), None)
    if rec:
        rec['account'] = account
        rec['expiresAt'] = v['expiresAt']
        if rec.get('status') != 'revoked':
            rec['status'] = 'revoked' if revoked else 'active'
    else:
        st['keys'].append({
            'key': key, 'account': account, 'expiresAt': v['expiresAt'],
            'issuedAt': now_iso(), 'status': 'revoked' if revoked else 'active',
            'revokedAt': None, 'revokedBy': None, 'note': body.get('note', '') or ''})
    save_state(st)
    return (200, {"ok": True, "key": key, "account": account,
                  "expiresAt": v['expiresAt'], "status": 'revoked' if revoked else 'active'})


def keys_verify(body, st):
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    seed = _resolve_seed(body)
    v = key_verify(key, account, seed)
    if not v['ok']:
        return (200, {"ok": False, "reason": v.get('reason'), "expiresAt": v.get('expiresAt')})
    st.setdefault('revokedKeys', [])
    if key in st['revokedKeys']:
        return (200, {"ok": False, "reason": 'revoked'})
    rec = next((r for r in st['keys'] if r['key'] == key), None)
    if rec and rec.get('status') == 'revoked':
        return (200, {"ok": False, "reason": 'revoked'})
    return (200, {"ok": True, "account": account, "expiresAt": v['expiresAt'],
                  "days": v.get('days'), "registered": bool(rec)})


def keys_revoke(body, st):
    account = (body.get('account') or '').strip()
    key = (body.get('key') or '').strip()
    auth_key = (body.get('authKey') or '').strip()
    auth_account = (body.get('authAccount') or '').strip()
    seed = _resolve_seed(body)
    av = key_verify(auth_key, auth_account, seed)
    if not av['ok']:
        return (403, {"ok": False, "error": "管理凭证无效: " + str(av.get('reason'))})
    if auth_account not in MAKER_ACCOUNTS and auth_account != account:
        return (403, {"ok": False, "error": "无权限撤销该密钥"})
    st.setdefault('revokedKeys', [])
    if key not in st['revokedKeys']:
        st['revokedKeys'].append(key)
    rec = next((r for r in st['keys'] if r['key'] == key), None)
    if rec:
        rec['status'] = 'revoked'
        rec['revokedAt'] = now_iso()
        rec['revokedBy'] = auth_account
    else:
        st['keys'].append({
            'key': key, 'account': account, 'expiresAt': None, 'issuedAt': None,
            'status': 'revoked', 'revokedAt': now_iso(), 'revokedBy': auth_account, 'note': '外部吊销'})
    save_state(st)
    push_message(st, 'system', '密钥已吊销 · ' + account,
                 '账号 %s 的密钥 %s… 已被制造者吊销，该账号将无法登录' % (account, key[:6]))
    return (200, {"ok": True, "account": account, "key": key, "status": 'revoked'})


def keys_list(query, st):
    maker_key = (query.get('makerKey') or '').strip()
    maker_account = (query.get('makerAccount') or '').strip()
    seed = (query.get('seed') or '') or KEY_SEED
    av = key_verify(maker_key, maker_account, seed)
    if not av['ok'] or maker_account not in MAKER_ACCOUNTS:
        return (403, {"ok": False, "error": "无权限"})
    keys = [dict(k) for k in st['keys']]
    revoked = list(st.get('revokedKeys', []))
    return (200, {"ok": True, "keys": keys, "revokedKeys": revoked})


# ---------- 商品读取 ----------
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


# ---------- 业务处理 ----------
def listings(body, st):
    pid = body.get("productId")
    platforms = body.get("platforms") or ["xianyu"]
    price = body.get("price")
    handoff = body.get("handoff", False)
    p = product_by_id(pid)
    if not p:
        return (400, {"ok": False, "error": "商品不存在"})
    if price is None:
        price = p["suggestPrice"]
    existing = next((l for l in reversed(st["listings"]) if l["productId"] == pid), None)
    if existing:
        lid = existing["id"]
        if existing["status"] != "已发布":
            existing["status"] = "待闲鱼确认" if handoff else "已发布"
            existing["platforms"] = platforms
            existing["price"] = price
    else:
        lid = new_id(st, "L")
        st["listings"].append({
            "id": lid, "productId": pid, "platforms": platforms,
            "price": price, "status": ("待闲鱼确认" if handoff else "已发布"),
            "createdAt": now_iso()})
    save_state(st)
    if handoff:
        push_message(st, "publish", "已唤起闲鱼App · 待确认",
                     "《%s》已转交闲鱼App铺货，请在闲鱼内完成发布后点「确认已上架」" % p["title"])
    else:
        for pl in platforms:
            push_message(st, "publish", "铺货成功 · %s" % pl,
                         "《%s》已上架到 %s，建议价 ¥%.1f" % (p["title"], pl, price))
    return (200, {"ok": True, "listingId": lid, "handoff": bool(handoff), "platforms": platforms})


def listing_action(lid, action, st):
    l = next((x for x in st["listings"] if x["id"] == lid), None)
    if not l:
        return (404, {"ok": False, "error": "铺货记录不存在"})
    p = product_by_id(l["productId"]) or {}
    if action == "confirm":
        if l["status"] == "已发布":
            return (200, {"ok": True, "status": l["status"]})
        l["status"] = "已发布"
        save_state(st)
        push_message(st, "publish", "铺货成功 · 闲鱼",
                     "《%s》已在闲鱼App确认上架，建议价 ¥%.1f" % (p.get("title", "商品"), l["price"]))
        return (200, {"ok": True, "status": "已发布"})
    if action == "handoff":
        l["status"] = "待闲鱼确认"
        save_state(st)
        return (200, {"ok": True, "status": "待闲鱼确认"})
    return (400, {"ok": False, "error": "unsupported"})


def simulate_order(body, st):
    pid = body.get("productId")
    p = product_by_id(pid) if pid else None
    if not p:
        prods = build_products().get("products", [])
        p = random.choice(prods) if prods else None
    if not p:
        return (400, {"ok": False, "error": "暂无商品"})
    buyer, addr = pick_buyer()
    refund = body.get("refund", False)
    status = "退款中" if refund else "待采购"
    oid = new_id(st, "O")
    cost = p["consignPrice"]
    profit = round(p["suggestPrice"] - cost - 2, 1)
    st["orders"].append({
        "id": oid, "productId": pid, "title": p["title"],
        "buyer": buyer, "addr": addr,
        "spec": "默认规格 · 1件", "price": p["suggestPrice"],
        "profit": profit, "cost": cost, "status": status,
        "purchaseId": None, "createdAt": now_iso(), "refund": refund})
    save_state(st)
    if refund:
        push_message(st, "aftersale", "退款申请 · %s" % p["title"],
                     "买家 %s 申请仅退款 ¥%.1f，待你一键售后处理" % (buyer, p["suggestPrice"]))
    else:
        push_message(st, "order", "新订单 · %s" % p["title"],
                     "买家 %s 已付款 ¥%.1f，待你一键采购代发" % (buyer, p["suggestPrice"]))
    return (200, {"ok": True, "orderId": oid, "status": status})


def order_action(oid, action, st):
    o = next((x for x in st["orders"] if x["id"] == oid), None)
    if not o:
        return (404, {"ok": False, "error": "订单不存在"})
    p = product_by_id(o["productId"]) or {}
    if action == "purchase":
        if o["status"] not in ("待采购",):
            return (400, {"ok": False, "error": "当前状态不可采购(%s)" % o["status"]})
        o["status"] = "待发货"
        pid_ = new_id(st, "P")
        st["purchases"].append({
            "id": pid_, "orderId": oid, "productId": o["productId"],
            "supplier": p.get("supplier", o.get("supplier", "—")),
            "cost": o["cost"], "link": p.get("link", ""),
            "status": "已下单", "trackingNo": None, "createdAt": now_iso()})
        o["purchaseId"] = pid_
        save_state(st)
        push_message(st, "purchase", "采购完成 · %s" % o["title"],
                     "已向 1688 %s 代付 ¥%.1f，等待厂家发货" % (p.get("supplier", "供应商"), o["cost"]))
        return (200, {"ok": True, "purchaseId": pid_, "orderStatus": o["status"]})
    if action == "ship":
        if o["status"] not in ("待发货",):
            return (400, {"ok": False, "error": "当前状态不可发货(%s)" % o["status"]})
        pur = next((x for x in st["purchases"] if x["id"] == o["purchaseId"]), None)
        if pur:
            pur["status"] = "已发货"
            pur["trackingNo"] = gen_tracking()
        o["status"] = "待收货"
        save_state(st)
        push_message(st, "logistics", "物流已发出 · %s" % o["title"],
                     "运单号 %s 已回传闲鱼，买家可查收" % (pur["trackingNo"] if pur else "—"))
        return (200, {"ok": True, "trackingNo": pur["trackingNo"] if pur else None, "orderStatus": o["status"]})
    if action == "request-refund":
        if o["status"] in ("待收货", "待发货", "待采购"):
            o["status"] = "退款中"; o["refund"] = True
            save_state(st)
            push_message(st, "aftersale", "退款申请 · %s" % o["title"],
                         "买家 %s 申请仅退款 ¥%.1f" % (o["buyer"], o["price"]))
            return (200, {"ok": True, "orderStatus": o["status"]})
        return (400, {"ok": False, "error": "当前状态不可申请退款(%s)" % o["status"]})
    if action == "aftersale":
        if o["status"] != "退款中":
            return (400, {"ok": False, "error": "订单非退款中，无需售后"})
        o["status"] = "已退款"
        o["refund"] = "done"
        save_state(st)
        push_message(st, "aftersale", "售后完成 · %s" % o["title"],
                     "已自动向 1688 厂商同步退款，¥%.1f 退回买家" % o["price"])
        return (200, {"ok": True, "orderStatus": o["status"]})
    return (400, {"ok": False, "error": "unsupported"})


def aftersales_set(body, st):
    with LOCK:
        if "auto" in body: st["aftersales"]["auto"] = bool(body["auto"])
        if "fast" in body: st["aftersales"]["fast"] = bool(body["fast"])
        if "manual" in body: st["aftersales"]["manual"] = bool(body["manual"])
        save_state(st)
    return (200, {"ok": True, "aftersales": st["aftersales"]})


def select_refresh(st):
    py = os.path.join(WS, "daily_pipeline.py")
    if not os.path.exists(py):
        return (400, {"ok": False, "error": "未找到 daily_pipeline.py"})
    try:
        env = dict(os.environ)
        env.setdefault("LINKFOX_AGENT_API_KEY", LINKFOX_KEY)
        r = subprocess.run([PYTHON, py, WS], capture_output=True, text=True, timeout=180, env=env)
        if r.returncode != 0:
            return (500, {"ok": False, "error": (r.stderr or "pipeline failed")[:300]})
    except Exception as e:
        return (500, {"ok": False, "error": str(e)[:200]})
    return (200, build_products())


def reset_state(st):
    global STATE
    STATE = default_state()
    save_state(STATE)
    push_message(STATE, "system", "演示数据已重置", "已清空铺货/订单/消息，可重新体验全流程")
    return (200, {"ok": True})


# ---------- 统一入口 ----------
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# 部署自标识：每次修改后端后递增，便于线上核实生效版本
APP_VERSION = "v2026.08.13.2"


def app_dispatch(method, path, query, headers, raw_body):
    method = (method or "GET").upper()
    path = (path or "").split("?")[0]
    if method == "OPTIONS":
        return (204, {}, dict(CORS))

    # 统一载入最新状态（Vercel 每次调用重新载入；本地进程内全局复用）
    global STATE
    STATE = load_state()
    st = STATE

    def jresp(code, payload):
        return (code, payload, dict(CORS))

    if method == "GET":
        if path == "/api/products":
            return jresp(200, build_products())
        if path == "/api/health":
            return jresp(200, {"ok": True,
                               "version": APP_VERSION,
                               "storage": STORAGE_MODE,
                               "latest": (latest_top10_path() or "").replace(WS, ""),
                               "orders": len(st["orders"]),
                               "listings": len(st["listings"]),
                               "keySeedFingerprint": key_fingerprint(KEY_SEED)})
        if path == "/api/state":
            return jresp(200, {"listings": st["listings"], "orders": st["orders"],
                               "purchases": st["purchases"], "messages": st["messages"],
                               "aftersales": st["aftersales"]})
        if path == "/api/keys":
            return jresp(*keys_list(query, st))
        return jresp(404, {"ok": False, "error": "unknown endpoint"})

    if method == "POST":
        body = {}
        if raw_body:
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except Exception:
                body = {}
        m = re.match(r"^/api/orders/([^/]+)/(purchase|ship|request-refund|aftersale)$", path)
        if m:
            return jresp(*order_action(m.group(1), m.group(2), st))
        if path == "/api/listings":
            return jresp(*listings(body, st))
        m = re.match(r"^/api/listings/([^/]+)/(handoff|confirm)$", path)
        if m:
            return jresp(*listing_action(m.group(1), m.group(2), st))
        if path == "/api/orders/simulate":
            return jresp(*simulate_order(body, st))
        if path == "/api/aftersales":
            return jresp(*aftersales_set(body, st))
        if path == "/api/keys/register":
            return jresp(*keys_register(body, st))
        if path == "/api/keys/verify":
            return jresp(*keys_verify(body, st))
        if path == "/api/keys/revoke":
            return jresp(*keys_revoke(body, st))
        if path == "/api/select/refresh":
            return jresp(*select_refresh(st))
        if path == "/api/reset":
            return jresp(*reset_state(st))
        return jresp(404, {"ok": False, "error": "unknown endpoint"})

    return jresp(405, {"ok": False, "error": "method not allowed"})
