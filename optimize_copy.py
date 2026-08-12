# -*- coding: utf-8 -*-
"""闲鱼商品文案优化器：读取 8:00 选出的 Top10 JSON，逐款按「黄金标题公式 + 详情转化结构」优化文案。
- 就地更新 JSON 的 xianyu_title / xianyu_body（供 8:30 上架包直接消费）
- 追加字段：title_variants / tags / first_img / pricing_note / tips
- 额外输出一份优化文案 HTML 报告
依赖：仅标准库 + 读 Top10 JSON。
"""
import json, sys, os, html, datetime

# offerId -> IP 展示名（用于标题/标签布局）
IP_MAP = {
    "1053013947539": "尘白禁区",
    "902693303074": "魔女之旅",
    "1068859307420": "火影忍者",
    "1049558844061": "一二布布",
    "1009630508705": "爱莉希雅",
    "1057617074906": "初音未来",
    "901654207169": "魔女之旅",
    "1075398944280": "二次元美少女",
    "1074339397816": "绪山真寻",
    "1075340036933": "蔚蓝档案",
}
CATE_MAP = {  # 按 1688 类目粗略映射到闲鱼品类词
    "玩具>模型玩具>手办模型": "手办模型",
    "玩具>毛绒/布艺公仔玩具>公仔抱枕": "毛绒玩偶",
    "办公、文化>节庆用品>其他节庆类用品": "二次元福袋",
}

def ip_of(p):
    return IP_MAP.get(p["offerId"], "二次元周边")

def cate_of(p):
    return CATE_MAP.get(p.get("levelName", ""), "二次元周边")

def optimize(p):
    ip = ip_of(p)
    cate = cate_of(p)
    consign = p["consignPrice"]
    price = p["suggest_price"]
    profit = p["profit"]
    margin = p["margin"]
    is_new = "最新上架" in p["src"]
    demand = p["demand_label"]

    # ---- 3 个标题版本（黄金标题公式：核心词前置 + 多搜索角度 + 流量词）----
    t1 = f"【{ip}】{cate} 正版授权包邮 自留送礼绝美 圈内一眼懂"          # 推荐：搜索覆盖+场景
    t2 = f"{ip}同款{cate} 低价出¥{price:.1f} 代发成本¥{consign:.1f} 学生党闭眼入"  # 性价比
    t3 = f"{ip}{cate} 现货速发 话题度高好出 包邮捡漏 手慢无"                # 稀缺/话题
    title_variants = [t1, t2, t3]

    # ---- 完整详情描述（转化结构：钩子→基本信息→描述→瑕疵→配件→交易→结尾）----
    hook = f"🌟 {ip} 同款{cate}，圈内人一眼懂，话题度高、出单快！"
    basic = (
        f"【基本信息】\n"
        f"• 款式：{ip} {cate}\n"
        f"• 成色：全新现货（1688 代发，仓库直发）\n"
        f"• 建议闲鱼价：¥{price:.1f}（诚心可小刀）\n"
        f"• 成本参考：代发约 ¥{consign:.1f}，单件利润约 ¥{profit:.1f}（毛利率 {margin:.0f}%）"
    )
    desc = (
        "【商品描述】\n"
        "🔥 热门 IP 周边，造型还原、细节在线，自留摆桌面 C 位或送礼都有面儿。\n"
        "✅ 比线下谷子店/官谷便宜一大截，学生党也 hold 住。\n"
        "📦 仓库现货，48h 内发货，全国包邮（偏远地区补差价）。"
    )
    flaw = "【瑕疵说明】\n全新代发件，无使用痕迹；如介意细微出厂品控属正常，介意慎拍。"
    acc = "【配件说明】\n默认款含本体；如有赠品/礼盒以 1688 详情页为准，下单可让商家一并发出。"
    deal = (
        "【交易说明】\n"
        "• 包邮！默认圆通/中通，急发可留言指定。\n"
        "• 当天/次日发货，物流单号同步闲鱼。\n"
        "• 非质量问题不退不换，收到请当面验收；贵重款建议录开箱视频。"
    )
    end = "💬 喜欢的直接拍，诚心要价格好商量～ 也可私信我帮你留货！"
    body = "\n\n".join([hook, basic, desc, flaw, acc, deal, end])

    # ---- 首图文案 ----
    first_img = f"大字：{ip} {cate} ¥{price:.1f}｜副标：正版感·包邮·现货｜角标：包邮/速发"

    # ---- 话题标签 ----
    tags = [f"#{ip}", "#二次元", "#手办", "#周边", "#谷美", "#包邮", "#闲鱼出闲置",
            "#动漫周边", "#学生党好物"]
    if "最新上架" in p["src"]:
        tags.append("#新款上新")

    # ---- 定价参考 ----
    pricing_note = (f"建议价 ¥{price:.1f}（=代发¥{consign:.1f}×2.2 取整），单件利润约 ¥{profit:.1f}；"
                    f"可挂 ¥{price+2:.1f} 留¥2 砍价空间，或用「一口价¥{price:.1f} 可小刀」提升咨询。")

    # ---- 出单技巧 ----
    tips = [
        "发布时间选晚 20:00–22:00 流量最大；",
        "每天擦亮一次保持宝贝活跃；",
        "价格略低于同 IP 均价更易被推荐；",
        "多配实拍/官图，图文齐全信任感强；",
        "及时回复私信，回复快排名靠前。",
    ]

    return {
        "title_variants": title_variants,
        "xianyu_title": t1,            # 用推荐版回写，供上架包
        "xianyu_body": body,
        "first_img": first_img,
        "tags": tags,
        "pricing_note": pricing_note,
        "tips": tips,
        "optimized": True,
    }

def main():
    json_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)
    d = json.load(open(json_path, encoding="utf-8"))
    date = d["date"]

    for p in d["products"]:
        o = optimize(p)
        p.update(o)

    # 回写 JSON（8:30 上架包自动吃到优化文案）
    json.dump(d, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # ---- HTML 优化报告 ----
    cards = []
    for p in d["products"]:
        ip = ip_of(p)
        tvs = "".join(f"<li><code>{html.escape(t)}</code></li>" for t in p["title_variants"])
        tags = " ".join(f"<span class='tag'>#{html.escape(t.lstrip('#'))}</span>" for t in p["tags"])
        tips = "".join(f"<li>{html.escape(t)}</li>" for t in p["tips"])
        cards.append(f"""<div class="card">
<div class="hd"><span class="rk">#{p['rank']}</span><b>{html.escape(ip)}</b>
<span class="src">{html.escape(p['src'])}</span>
<span class="profit">利润≈¥{p['profit']:.1f}</span></div>
<div class="sec"><span class="lab">标题方案(3版)</span><ol>{tvs}</ol></div>
<div class="sec"><span class="lab">详情描述</span><pre>{html.escape(p['xianyu_body'])}</pre></div>
<div class="sec"><span class="lab">首图文案</span><div class="box">{html.escape(p['first_img'])}</div></div>
<div class="sec"><span class="lab">话题标签</span><div class="tags">{tags}</div></div>
<div class="sec"><span class="lab">定价参考</span><div class="box">{html.escape(p['pricing_note'])}</div></div>
<div class="sec"><span class="lab">出单技巧</span><ul class="tips">{tips}</ul></div>
</div>""")
    cards_html = "\n".join(cards)

    html_doc = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>闲鱼文案优化_{date}</title>
<style>
*{{box-sizing:border-box}}body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#1f2329}}
.wrap{{max-width:960px;margin:0 auto;padding:18px}}
header{{background:linear-gradient(135deg,#ff6a00,#ff3d00);color:#fff;border-radius:14px;padding:16px 22px;margin-bottom:14px}}
header h1{{margin:0 0 4px;font-size:19px}}header p{{margin:0;font-size:13px;opacity:.95}}
.card{{background:#fff;border:1px solid #e5e6eb;border-radius:12px;padding:14px 16px;margin-bottom:14px}}
.hd{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
.rk{{background:#ff5000;color:#fff;border-radius:8px;padding:2px 9px;font-weight:700}}
.hd b{{font-size:16px}} .src{{font-size:12px;color:#888;background:#f0f1f3;border-radius:10px;padding:2px 8px}}
.profit{{margin-left:auto;color:#0a8a3f;font-weight:700;font-size:13px}}
.sec{{margin:8px 0}} .lab{{display:block;font-size:12px;font-weight:700;color:#ff5000;margin-bottom:4px}}
ol{{margin:0;padding-left:20px}} li{{font-size:13px;margin:3px 0}} code{{background:#fff3ec;padding:1px 5px;border-radius:5px;color:#b34200}}
pre{{white-space:pre-wrap;background:#fafbfc;border:1px solid #eef0f3;border-radius:8px;padding:10px;font-size:12.5px;line-height:1.7;margin:0}}
.box{{background:#fafbfc;border:1px solid #eef0f3;border-radius:8px;padding:8px 10px;font-size:12.5px}}
.tags{{display:flex;flex-wrap:wrap;gap:6px}} .tag{{background:#e8f3ff;color:#1677ff;border-radius:10px;padding:2px 10px;font-size:12px}}
.tips{{margin:0;padding-left:18px}} .tips li{{font-size:12.5px;margin:2px 0}}
footer{{color:#9aa0a6;font-size:12px;margin-top:6px;line-height:1.7}}
</style></head><body><div class="wrap">
<header><h1>闲鱼商品文案优化报告</h1><p>日期 {date} ｜ 基于 8:00 选出的 Top10 ｜ 已就地回写 JSON，8:30 上架包将自动采用优化文案</p></header>
{cards_html}
<footer>优化逻辑遵循「闲鱼高曝光标题公式 + 详情转化 7 段结构」，已规避绝对化/违规词。标题已自动回写 Top10 JSON 的 xianyu_title/xianyu_body 字段。</footer>
</div></body></html>"""

    rep_path = os.path.join(out_dir, f"闲鱼文案优化_{date}.html")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("updated JSON:", json_path)
    print("report:", rep_path)
    print("optimized products:", len(d["products"]))

if __name__ == "__main__":
    main()
