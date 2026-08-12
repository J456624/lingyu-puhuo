# -*- coding: utf-8 -*-
"""二次元闲鱼选品 Top10 生成器（可复用版）
用法: python select_top10.py <search.json> <billboard.json> <outdir>
输出: <outdir>/二次元闲鱼选品_Top10_<date>.html
      <outdir>/二次元闲鱼选品_Top10_<date>.json   (供 8:30 上架包脚本消费)
"""
import json, math, os, re, sys, datetime

def suggest_price(c):
    if c <= 0:
        return 0.0
    raw = c * 2.2
    base = int(raw)
    cents = raw - base
    tail = 0.8 if cents < 0.45 else 0.9
    return round(base + tail, 1)

def is_cosapparel(t):
    return "cos" in t.lower() or "cosplay" in t.lower() or "角色扮演" in t

def extract_ip(title):
    ips = ["魔道祖师","胖虎","盗墓笔记","七龙珠","龙珠","火影","佩恩","鬼灭之刃","鬼灭","初音","爱莉希雅","胡桃","甘雨","可莉","崩坏","星穹铁道","流萤","间谍过家家","阿尼亚","明日方舟","蔚蓝档案","电锯人","蕾塞","魔女之旅","伊蕾娜","尘白禁区","棉花娃娃","努努","洋娃娃"]
    for k in ips:
        if k in title:
            return k
    return ""

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def score(p):
    c = p.get("consignPrice") or 0
    sp = suggest_price(c)
    profit = round(sp - c - 2, 1)
    margin = (profit / sp) if sp > 0 else -1
    sales = p.get("salesQuantity",0) or 0
    is_new = p["_src"] == "最新上架"
    is_hot = "热销" in p["_src"]
    title = p["title"]

    # 需求确定性 45%：已验证热销按销量给 60~100；未验证新货给基础分(明显低于已验证)
    if is_hot and sales > 0:
        d = min(math.log10(sales + 1) / math.log10(300), 1.0)
        s_demand = 60 + d * 40
        demand_label = f"热销验证(月销{sales}件)"
    elif is_new:
        ip = extract_ip(title)
        if ip or c < 10:
            s_demand = 50
        elif c < 30:
            s_demand = 45
        else:
            s_demand = 40
        demand_label = "新奇特·抢先上架"
    else:
        s_demand = 40
        demand_label = "常规"

    # 利润质量 25%：毛利率为主 + 绝对利润(封顶¥20，避免高客单独占)
    margin_norm = min(max(margin, 0) / 0.50, 1.0)
    abs_norm = min(profit / 20.0, 1.0)
    s_profit = (margin_norm * 0.6 + abs_norm * 0.4) * 100

    # 转售友好 30%：轻小/包邮友好 + 低售后/低压货风险
    light = 1 - min(c / 60.0, 1.0)
    moq = 1.0 if (p.get("quantityBegin",99) or 99) <= 1 else 0.4
    risk = 1.0
    if is_cosapparel(title):
        risk *= 0.4
    if c > 100:
        risk *= 0.6                      # 压货 / 慢周转
    if ("盲" in title) and not is_hot:
        risk *= 0.6                      # 未验证盲盒难出
    s_resale = (light * 0.5 + moq * 0.3 + risk * 0.2) * 100

    total = s_demand * 0.45 + s_profit * 0.25 + s_resale * 0.30
    return dict(total=round(total,1), s_profit=round(s_profit,1), s_demand=round(s_demand,1),
                s_light=round(s_resale,1), sp=sp, profit=profit, margin=round(margin*100,1),
                demand_label=demand_label)

def xianyu_title(p):
    ip = extract_ip(p["title"])
    t = p["title"]
    core = t
    for junk in ["二次元","动漫周边","周边","谷子","批发","跨境","新品","现货","代发","礼物","摆件","送男生","送女生","女生","男生"]:
        core = core.replace(junk,"")
    core = re.sub(r"[，,。\.].*$", "", core).strip()
    cat = ""
    if "手办" in t: cat = "手办模型"
    elif "吧唧" in t or "徽章" in t: cat = "吧唧徽章"
    elif "毛绒" in t or "玩偶" in t or "娃娃" in t: cat = "毛绒玩偶"
    elif "发夹" in t or "发饰" in t: cat = "二次元发饰"
    elif "立牌" in t or "亚克力" in t: cat = "亚克力立牌"
    elif "cos" in t.lower(): cat = "cos服"
    else: cat = "二次元周边"
    prefix = ip if ip else core[:6]
    return f"【{prefix}】{cat} 正版授权 包邮 送闺蜜送男友 自留绝美"

def xianyu_body(p):
    c = p.get("consignPrice") or 0
    sp = p["sp"]; profit = p["profit"]
    lines = []
    ip = extract_ip(p["title"])
    if is_cosapparel(p["title"]):
        lines.append("🔥 还原度高，出片神器，漫展/约会/拍照一条搞定")
        lines.append("✅ 面料舒适不易皱，尺码齐全，按身高体重报我给你推荐")
        lines.append("📦 现货速发，48h内揽收，支持退换（非人为损坏）")
    elif c < 3:
        lines.append("💰 个位数白菜价！包邮走量，闲鱼捡漏价，多拍更划算")
        lines.append("✅ 轻小件不易碎，随手送朋友、凑单、摆桌面都合适")
        lines.append("📦 现货秒发，拍下当天发，偏远补运费")
    elif c < 30:
        lines.append("🔥 热门IP正版感周边，细节在线，自留送礼都有面儿")
        lines.append("✅ 高性价比，比线下谷子店便宜一大截，学生党也hold住")
        lines.append("📦 仓库现货，48h内发货，全国包邮（偏远除外）")
    else:
        lines.append("🎨 精工摆件/收藏级，造型还原，关节/涂装细节耐看")
        lines.append("✅ 送男生送女友都拿得出手，桌面C位就它了")
        lines.append("📦 泡沫加固发货，防摔；贵重件建议录开箱视频")
    if ip:
        lines.insert(0, f"🌟 {ip} 同款，圈内人一眼懂，话题度高好出")
    lines.append(f"💡 闲鱼价 ¥{sp}（代发成本¥{c}左右，单件利润约¥{profit}）")
    return "\n".join(lines)

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def main():
    if len(sys.argv) < 4:
        print("usage: select_top10.py <search.json> <billboard.json> <outdir>")
        sys.exit(1)
    new = load(sys.argv[1]); hot = load(sys.argv[2]); outdir = sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    date = datetime.date.today().strftime("%Y-%m-%d")

    merged = {}
    for p in new["products"]:
        p = dict(p); p["_src"] = "最新上架"; merged[p["offerId"]] = p
    for p in hot["products"]:
        p = dict(p); p["_src"] = "热销榜"
        if p["offerId"] in merged:
            merged[p["offerId"]]["_src"] = "热销+最新"
        else:
            merged[p["offerId"]] = p

    items = list(merged.values())
    for p in items:
        p.update(score(p))

    items.sort(key=lambda x: x["total"], reverse=True)
    # 组合约束：保底≥4款已验证热销；高客单(>¥30)≤3；未验证盲盒≤2；其余按总分
    top, top_ids = [], set()
    hot_n = high_n = blind_n = 0
    def is_high(p): return (p.get("consignPrice") or 0) > 30
    def is_blind_unproven(p): return ("盲" in p["title"]) and ("热销" not in p["_src"])
    for p in items:
        if len(top) >= 10: break
        if p["offerId"] in top_ids: continue
        is_hot = "热销" in p["_src"]
        if is_hot and hot_n >= 7: continue
        if is_high(p) and high_n >= 3: continue
        if is_blind_unproven(p) and blind_n >= 2: continue
        top.append(p); top_ids.add(p["offerId"])
        if is_hot: hot_n += 1
        if is_high(p): high_n += 1
        if is_blind_unproven(p): blind_n += 1
    # 若约束导致未满 10，用剩余最高分补齐
    for p in items:
        if len(top) >= 10: break
        if p["offerId"] not in top_ids:
            top.append(p); top_ids.add(p["offerId"])
    top.sort(key=lambda x: x["total"], reverse=True)

    # 生成 闲鱼文案
    out_products = []
    for i, p in enumerate(top, 1):
        c = p.get("consignPrice") or 0
        tier = "引流款" if c < 3 else ("利润款" if c < 30 else "高客单款")
        rec = {
            "rank": i, "offerId": p["offerId"], "title": p["title"],
            "imageUrl": p.get("imageUrl",""), "asinUrl": p.get("asinUrl","#"),
            "company": p.get("company","—"), "consignPrice": c, "price": p.get("price") or c,
            "quantityBegin": p.get("quantityBegin",1) or 1, "deliveryTime": p.get("deliveryTime") or "—",
            "levelName": p.get("levelName",""), "src": p["_src"], "tier": tier,
            "score": p["total"], "demand_label": p["demand_label"],
            "suggest_price": p["sp"], "profit": p["profit"], "margin": p["margin"],
            "xianyu_title": xianyu_title(p), "xianyu_body": xianyu_body(p),
        }
        out_products.append(rec)

    # ---- HTML ----
    rows = []
    for r in out_products:
        rows.append(f"""
    <div class="card">
      <div class="rank">#{r['rank']}</div>
      <img class="thumb" src="{esc(r['imageUrl'])}" alt=""/>
      <div class="body">
        <div class="tags">
          <span class="tag src">{esc(r['src'])}</span>
          <span class="tag tier">{esc(r['tier'])}</span>
          <span class="tag score">转售分 {r['score']}</span>
          <span class="tag demand">{esc(r['demand_label'])}</span>
        </div>
        <h3>{esc(r['title'])}</h3>
        <div class="meta">1688批发价 ¥{r['price']} ｜ 代发价 <b>¥{r['consignPrice']}</b> ｜ 起批 {r['quantityBegin']} ｜ 发货 {r['deliveryTime']}h ｜ {esc(r['company'])}</div>
        <a class="src" href="{esc(r['asinUrl'])}" target="_blank">🔗 1688商品链接</a>
        <div class="xy">
          <div class="xy-title">📣 闲鱼标题：{esc(r['xianyu_title'])}</div>
          <div class="xy-body">{esc(r['xianyu_body']).replace(chr(10),'<br/>')}</div>
          <table class="price">
            <tr><th>代发价</th><th>建议闲鱼价</th><th>预估单件利润</th><th>毛利率</th></tr>
            <tr><td>¥{r['consignPrice']}</td><td>¥{r['suggest_price']}</td><td>¥{r['profit']}</td><td>{r['margin']}%</td></tr>
          </table>
        </div>
      </div>
    </div>""")
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/><title>二次元闲鱼选品 Top10 · {date}</title>
<style>
*{{box-sizing:border-box}}body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6fa;margin:0;color:#222;padding:24px}}
.header{{background:linear-gradient(135deg,#6a5acd,#8e7bef);color:#fff;padding:22px 26px;border-radius:14px;margin-bottom:18px}}
.header h1{{margin:0 0 6px;font-size:22px}}.header p{{margin:0;opacity:.9;font-size:13px}}
.wrap{{max-width:1100px;margin:0 auto}}
.card{{display:flex;gap:16px;background:#fff;border-radius:12px;padding:16px;margin-bottom:14px;box-shadow:0 2px 10px rgba(0,0,0,.05);position:relative}}
.rank{{position:absolute;top:-8px;left:-8px;background:#ff6b6b;color:#fff;font-weight:700;width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(255,107,107,.5)}}
.thumb{{width:120px;height:120px;object-fit:cover;border-radius:10px;background:#eee;flex-shrink:0}}
.body{{flex:1;min-width:0}}.tags{{margin-bottom:6px}}
.tag{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;margin-right:6px;margin-bottom:4px}}
.tag.src{{background:#eef2ff;color:#5b50e0}}.tag.tier{{background:#fff3e0;color:#e08a00}}.tag.score{{background:#e8f5e9;color:#2e7d32}}.tag.demand{{background:#fce4ec;color:#c2185b}}
h3{{margin:4px 0 6px;font-size:15px;line-height:1.35}}.meta{{font-size:12px;color:#666;margin-bottom:4px}}
.src{{font-size:12px;color:#5b50e0;text-decoration:none}}
.xy{{margin-top:10px;background:#fafbff;border:1px solid #eef;border-radius:10px;padding:12px}}
.xy-title{{font-weight:700;color:#3a2fb0;font-size:14px;margin-bottom:6px}}
.xy-body{{font-size:13px;line-height:1.7;color:#333;margin-bottom:10px}}
table.price{{width:100%;border-collapse:collapse;font-size:12px}}
table.price th{{background:#6a5acd;color:#fff;padding:6px}}table.price td{{border:1px solid #eee;padding:6px;text-align:center;font-weight:700;color:#c0392b}}
.foot{{text-align:center;color:#999;font-size:12px;margin-top:20px}}
</style></head><body><div class="wrap">
<div class="header"><h1>🎯 二次元闲鱼选品 · 今日最优 Top 10</h1>
<p>数据源：店雷达 1688 选品库 ｜ 热销榜 + 最新上架合并去重 ｜ 评分：利润空间40%·热销/新奇特30%·轻小包邮/售后低30% ｜ 生成 {date}</p></div>
{''.join(rows)}
<div class="foot">利润口径：建议闲鱼价 = 代发价×2.2 取整到 .9/.8；预估利润 = 建议价 − 代发价 − 2元包邮。</div></div></body></html>"""

    html_path = os.path.join(outdir, f"二次元闲鱼选品_Top10_{date}.html")
    json_path = os.path.join(outdir, f"二次元闲鱼选品_Top10_{date}.json")
    with open(html_path, "w", encoding="utf-8") as f: f.write(html)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"date": date, "products": out_products}, f, ensure_ascii=False, indent=2)
    print("HTML:", html_path)
    print("JSON:", json_path)
    print("-"*70)
    for r in out_products:
        print(f"{r['rank']:>2}. [{r['src']:8}] 分{r['score']:>5}  代发¥{r['consignPrice']} 建议¥{r['suggest_price']} 利润¥{r['profit']}  {r['title'][:30]}")

if __name__ == "__main__":
    main()
