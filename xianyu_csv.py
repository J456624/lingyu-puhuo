# -*- coding: utf-8 -*-
"""把 8:00 生成的 Top10 JSON 转成「闲鱼商家后台/千牛批量发布」CSV
用法: python xianyu_csv.py <top10.json> <outdir>
输出: <outdir>/闲鱼上架包_<date>.csv  (UTF-8 BOM, Excel/千牛可直接打开)
注意: 闲鱼/千牛批量发布图片通常需先上传到图片空间; 这里先放 1688 图链作占位,
      若平台拒绝外链, 请先把图片下载到本地再上传图片空间后替换本列。
"""
import json, csv, sys, os, datetime

def main():
    if len(sys.argv) < 3:
        print("usage: xianyu_csv.py <top10.json> <outdir>")
        sys.exit(1)
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    date = data.get("date") or datetime.date.today().strftime("%Y-%m-%d")

    cols = ["标题","宝贝描述","价格(元)","运费(元)","库存","类目","成色","发货地","图片链接","1688货源链接","代发价(元)","预估利润(元)"]
    rows = []
    for p in data["products"]:
        rows.append({
            "标题": p["xianyu_title"],
            "宝贝描述": p["xianyu_body"],
            "价格(元)": p["suggest_price"],
            "运费(元)": 0,
            "库存": 10,
            "类目": p.get("levelName",""),
            "成色": "全新",
            "发货地": "浙江",
            "图片链接": p.get("imageUrl",""),
            "1688货源链接": p.get("asinUrl",""),
            "代发价(元)": p["consignPrice"],
            "预估利润(元)": p["profit"],
        })

    csv_path = os.path.join(outdir, f"闲鱼上架包_{date}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("CSV 已生成:", csv_path)
    print(f"共 {len(rows)} 条，列: {cols}")

if __name__ == "__main__":
    main()
