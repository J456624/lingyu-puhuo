# -*- coding: utf-8 -*-
"""生成手机端自包含闲鱼发布文档（单 HTML，图片 base64 内嵌，离线可看）。
含 10 款全部信息：图/标题/描述/价格/代发价/利润/标签/供应商/1688链接/发货 + 移动端发布步骤。
读 Top10 JSON（含优化文案）+ images/<date>/ 本地图（优先内嵌，缺失则回退1688外链）。
"""
import json, sys, os, base64, glob, html

def main():
    json_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)
    d = json.load(open(json_path, encoding="utf-8"))
    date = d["date"]
    img_dir = os.path.join(out_dir, "images", date)

    def local_img(rank, oid):
        cand = glob.glob(os.path.join(img_dir, f"{rank:02d}_{oid}.*"))
        if cand:
            return cand[0]
        c2 = glob.glob(os.path.join(img_dir, f"*_{oid}.*"))
        return c2[0] if c2 else None

    def img_src(p):
        fp = local_img(p["rank"], p["offerId"])
        if fp and os.path.exists(fp):
            ext = os.path.splitext(fp)[1].lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp"}.get(ext, "image/jpeg")
            b = base64.b64encode(open(fp, "rb").read()).decode()
            return f"data:{mime};base64,{b}", "local"
        return p.get("imageUrl", ""), "remote"

    cards = []
    for p in d["products"]:
        src, kind = img_src(p)
        title = p.get("xianyu_title", p["title"])
        body = p.get("xianyu_body", "")
        tags = " ".join(f"#{t.lstrip('#')}" for t in p.get("tags", []))
        price = p["suggest_price"]
        consign = p["consignPrice"]
        profit = p["profit"]
        supplier = p.get("company", "")
        link = p.get("asinUrl", "")
        lead = p.get("deliveryTime", "—")
        cards.append(f"""
<section class="card">
  <div class="top"><span class="rk">#{p['rank']}</span>
    <span class="src">{html.escape(p['src'])}</span>
    <span class="profit">利润≈¥{profit:.1f}</span></div>
  <img class="pic" src="{src}" alt="商品图" referrerpolicy="no-referrer">
  <div class="row"><span class="lab">标题</span>
    <button class="cp" data-c="{html.escape(title)}">复制</button></div>
  <div class="val" id="t{p['rank']}">{html.escape(title)}</div>
  <div class="row"><span class="lab">描述</span>
    <button class="cp" data-c="{html.escape(body)}">复制</button></div>
  <pre class="val">{html.escape(body)}</pre>
  <div class="meta">
    <span>💰 闲鱼价 <b>¥{price:.1f}</b></span>
    <span>📦 代发价 ¥{consign:.1f}</span>
    <span>⏱ 发货 {lead}h</span>
  </div>
  <div class="meta"><span>🏭 {html.escape(supplier)}</span></div>
  <div class="tags">{html.escape(tags)}</div>
  <div class="meta"><a href="{link}" target="_blank" rel="noopener">🔗 1688货源(代发用)</a></div>
</section>""")
    cards_html = "\n".join(cards)

    doc = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>闲鱼手机发布文档 {date}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#f2f3f5;color:#1f2329;
font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:520px;margin:0 auto;padding:12px}}
header{{background:linear-gradient(135deg,#ff6a00,#ff3d00);color:#fff;border-radius:14px;
padding:16px;margin-bottom:12px}}
header h1{{margin:0 0 6px;font-size:19px}} header p{{margin:0;font-size:12.5px;opacity:.95}}
.guide{{background:#fff;border:1px solid #e5e6eb;border-radius:12px;padding:12px 14px;margin-bottom:12px;font-size:13px;line-height:1.8}}
.guide b{{color:#ff5000}} .guide ol{{margin:6px 0 0;padding-left:20px}}
.card{{background:#fff;border:1px solid #e5e6eb;border-radius:12px;padding:12px;margin-bottom:12px}}
.top{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.rk{{background:#ff5000;color:#fff;border-radius:8px;padding:2px 9px;font-weight:700}}
.src{{font-size:12px;color:#888;background:#f0f1f3;border-radius:10px;padding:2px 8px}}
.profit{{margin-left:auto;color:#0a8a3f;font-weight:700;font-size:13px}}
.pic{{width:100%;border-radius:10px;display:block;background:#eee;margin-bottom:8px}}
.row{{display:flex;align-items:center;justify-content:space-between;margin:8px 0 3px}}
.lab{{font-size:12px;font-weight:700;color:#ff5000}} .cp{{border:none;background:#fff3ec;color:#d84300;
border-radius:8px;padding:3px 12px;font-size:12px;font-weight:700}}
.val{{font-size:13.5px;line-height:1.7;white-space:pre-wrap;word-break:break-word;
background:#fafbfc;border:1px solid #eef0f3;border-radius:8px;padding:8px}}
.meta{{font-size:12.5px;color:#444;margin:6px 0;display:flex;flex-wrap:wrap;gap:6px 14px}}
.meta b{{color:#ff5000}} .tags{{font-size:12px;color:#1677ff;margin-top:4px;line-height:1.8}}
.meta a{{color:#1677ff;text-decoration:none}}
footer{{color:#9aa0a6;font-size:12px;text-align:center;padding:10px 0 24px;line-height:1.7}}
</style></head><body><div class="wrap">
<header><h1>闲鱼·手机一键发布文档</h1><p>日期 {date} ｜ 10 款 ｜ 图片已内嵌，离线也能看</p></header>
<div class="guide"><b>📱 手机端发布步骤（每款照做）</b>
<ol>
<li>长按本卡「图片」→ 保存到相册（或用浏览器"图片另存"）</li>
<li>点「复制」按钮，复制标题 / 描述</li>
<li>打开<b>闲鱼 App</b> → 底部「+」→ 发闲置</li>
<li>从相册选刚存的图 → 粘贴标题、描述 → 填价格（见卡片）</li>
<li>选「包邮」、分类（手办/周边）→ 发布</li>
<li>接单后按代发表去 1688 填买家地址代发</li>
</ol></div>
{cards_html}
<footer>本文档由 WorkBuddy 自动生成（{date}）。图片内嵌便于手机离线浏览；发布请以闲鱼 App 实际页面为准。</footer>
</div>
<script>
document.querySelectorAll('.cp').forEach(b=>b.onclick=()=>{{
 navigator.clipboard.writeText(b.dataset.c).then(()=>{{
   const o=b.textContent;b.textContent='已复制✓';setTimeout(()=>b.textContent=o,1200);
 }}).catch(()=>alert('复制失败，请手动长按选择'));
}});
</script></body></html>"""
    out = os.path.join(out_dir, f"闲鱼手机发布文档_{date}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print("mobile doc:", out)
    print("size KB:", round(os.path.getsize(out)/1024, 1))

if __name__ == "__main__":
    main()
