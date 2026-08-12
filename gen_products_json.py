#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取最新 Top10 JSON，生成 app/products.json(供静态部署版 App 取数)。"""
import json, glob, os, re

WS = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(WS, "app")
GLOB = os.path.join(WS, "二次元闲鱼选品_Top10_*.json")


def main():
    files = glob.glob(GLOB)
    if not files:
        print("未找到 Top10 JSON"); return
    path = max(files, key=os.path.getmtime)
    data = json.load(open(path, encoding="utf-8"))
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    date_str = dm.group(1) if dm else ""
    out = {"updated": date_str, "source": os.path.basename(path), "products": []}
    for p in data.get("products", []):
        out["products"].append({
            "id": p.get("offerId", ""),
            "rank": p.get("rank", 0),
            "title": p.get("xianyu_title") or p.get("title", ""),
            "srcTitle": p.get("title", ""),
            "image": p.get("imageUrl") or "",
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
            "leadTime": p.get("deliveryTime", "—"),
            "body": p.get("xianyu_body", ""),
            "tags": p.get("tags", []),
        })
    os.makedirs(APP, exist_ok=True)
    with open(os.path.join(APP, "products.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("已生成 app/products.json : %d 款, updated=%s" % (len(out["products"]), date_str))


if __name__ == "__main__":
    main()
