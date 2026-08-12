# -*- coding: utf-8 -*-
"""由 Top10 JSON 生成 闲鱼->1688 一件代发对照表(HTML + CSV 追踪表)。
CSV 含空白回填列：买家收货信息 / 1688代发订单号 / 物流单号，供每笔订单填写。
"""
import json, sys, csv, os

def main():
    json_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)
    d = json.load(open(json_path, encoding="utf-8"))
    date = d["date"]
    ps = d["products"]

    # 规格备注：无明确规格数据时给通用代发提示
    def spec_note(p):
        if p["quantityBegin"] and p["quantityBegin"] > 1:
            return f"起批{p['quantityBegin']}件，代发默认1件需与客服确认"
        return "一件代发·默认款(无特别要求选混发/随机)"

    rows = []
    for p in ps:
        rows.append({
            "rank": p["rank"],
            "xy_title": p.get("xianyu_title") or p["title"],
            "link": p["asinUrl"],
            "company": p.get("company", ""),
            "consign": p["consignPrice"],
            "price": p["suggest_price"],
            "profit": p["profit"],
            "lead": p.get("deliveryTime", "—"),
            "spec": spec_note(p),
        })

    # ---------- HTML ----------
    trs = []
    for r in rows:
        trs.append(f"""<tr>
<td class="c">{r['rank']}</td>
<td class="t">{r['xy_title']}</td>
<td class="c"><a href="{r['link']}" target="_blank" rel="noopener">打开1688 ↗</a></td>
<td class="c small">{r['company']}</td>
<td class="num">¥{r['consign']:.1f}</td>
<td class="num">¥{r['price']:.1f}</td>
<td class="num pos">¥{r['profit']:.1f}</td>
<td class="c small">{r['lead']}h</td>
<td class="small">{r['spec']}</td>
<td class="fill"></td>
<td class="fill"></td>
<td class="fill"></td>
</tr>""")
    tr_html = "\n".join(trs)

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>闲鱼→1688代发对照表 {date}</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#1f2329}}
.wrap{{max-width:1180px;margin:0 auto;padding:20px}}
header{{background:linear-gradient(135deg,#ff6a00,#ff3d00);color:#fff;border-radius:14px;padding:18px 22px;margin-bottom:14px}}
header h1{{margin:0 0 6px;font-size:20px}}
header p{{margin:0;font-size:13px;opacity:.95}}
.flow{{display:flex;flex-wrap:wrap;gap:8px;background:#fff;border:1px solid #e5e6eb;border-radius:12px;padding:14px 16px;margin-bottom:14px;font-size:13px;align-items:center}}
.flow b{{color:#ff5000}}
.flow .step{{background:#fff3ec;color:#d84300;border-radius:20px;padding:4px 12px;font-weight:600}}
.note{{background:#fff8e6;border:1px solid #ffe08a;border-radius:10px;padding:10px 14px;font-size:12.5px;color:#7a5b00;margin-bottom:14px;line-height:1.7}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:12.5px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
th,td{{padding:9px 8px;text-align:left;border-bottom:1px solid #eef0f3;vertical-align:top}}
th{{background:#fff1ea;color:#7a3b00;font-weight:700;position:sticky;top:0}}
td.c{{text-align:center}} td.num{{text-align:right;font-variant-numeric:tabular-nums}}
td.t{{font-weight:600}} td.small{{font-size:11.5px;color:#6b7280}} td.pos{{color:#0a8a3f;font-weight:700}}
td a{{color:#1677ff;text-decoration:none}} td a:hover{{text-decoration:underline}}
td.fill{{background:#fafbfc}}
.bar{{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0;font-size:13px}}
.bar div{{background:#fff;border:1px solid #e5e6eb;border-radius:10px;padding:10px 16px;flex:1;min-width:150px}}
.bar b{{display:block;font-size:20px;color:#ff5000}}
footer{{color:#9aa0a6;font-size:12px;margin-top:14px;line-height:1.7}}
</style></head><body><div class="wrap">
<header><h1>闲鱼 → 1688 一件代发对照表</h1><p>日期 {date} ｜ Top10 商品 ｜ 有人在你闲鱼下单后，按右侧流程逐列回填即可</p></header>
<div class="flow">
<span class="step">① 闲鱼收到订单</span> → 复制买家收货信息 →
<span class="step">② 点开1688链接</span> → 一件代发下单、填买家地址 →
<span class="step">③ 回填代发订单号</span> → 复制物流单号 →
<span class="step">④ 回闲鱼点「一键发货」</span> 填单号
</div>
<div class="note">⚠️ <b>代发要点</b>：1688 下单时<b>收货人务必填闲鱼买家</b>，不要填你自己；卖家留言注明"一件代发/无好评卡/无货源单"。物流单号出来后回填本表最后一列，再到闲鱼订单点「一键发货」粘贴即可。贵重款（如空崎日奈 ¥48）建议让供应商发顺丰并录开箱视频防纠纷。</div>
<div class="bar">
<div>商品数<b>{len(rows)}</b></div>
<div>代发价区间<b>¥{min(r['consign'] for r in rows):.1f}–¥{max(r['consign'] for r in rows):.1f}</b></div>
<div>预估单件利润<b>¥{min(r['profit'] for r in rows):.1f}–¥{max(r['profit'] for r in rows):.1f}</b></div>
</div>
<table><thead><tr>
<th>#</th><th>闲鱼在售标题</th><th>1688货源</th><th>供应商</th>
<th>代发价</th><th>建议闲鱼价</th><th>单件利润</th><th>发货时效</th>
<th>下单规格备注</th><th>买家收货信息(待填)</th><th>1688代发订单号(待填)</th><th>物流单号(待填→回传闲鱼)</th>
</tr></thead><tbody>
{tr_html}
</tbody></table>
<footer>本表由 WorkBuddy 自动生成，数据来源：店雷达 1688 选品库（{date}）。代发下单请以 1688 实际页面价格/库存为准；利润已按「建议价−代发价−2元包邮」测算。最后一列填完物流单号后，回闲鱼卖家中心「已卖出的宝贝 → 一键发货」粘贴即可。</footer>
</div></body></html>"""

    html_path = os.path.join(out_dir, f"闲鱼代发对照表_{date}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # ---------- CSV 追踪表 (UTF-8 BOM) ----------
    csv_path = os.path.join(out_dir, f"闲鱼代发对照表_{date}.csv")
    header = ["#", "闲鱼在售标题", "1688货源链接", "1688供应商", "代发价(¥)",
              "建议闲鱼零售价(¥)", "预估单件利润(¥)", "发货时效(h)", "下单规格备注",
              "买家收货信息(从闲鱼订单复制)", "1688代发订单号(下单后回填)", "物流单号(回填→闲鱼一键发货)"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([r["rank"], r["xy_title"], r["link"], r["company"],
                        f"{r['consign']:.1f}", f"{r['price']:.1f}", f"{r['profit']:.1f}",
                        r["lead"], r["spec"], "", "", ""])

    print("HTML:", html_path)
    print("CSV :", csv_path)
    print("rows:", len(rows))

if __name__ == "__main__":
    main()
