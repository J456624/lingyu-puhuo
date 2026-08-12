# -*- coding: utf-8 -*-
"""下载 Top10 商品的 1688 主图并打包，供用户上传到闲鱼图片空间（解决上架包图片外链被拒问题）。
输入：二次元闲鱼选品_Top10_<date>.json
输出：
  images/<date>/<rank>_<offerId>.<ext>   10 张图
  images/闲鱼商品图_<date>.zip            打包
  images/闲鱼商品图清单_<date>.csv        清单(#, 闲鱼标题, 本地文件, 本地路径, 1688原图)
依赖：requests（linkfox venv 已装）
"""
import json, sys, os, csv, zipfile, re

def main():
    json_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)
    import requests

    d = json.load(open(json_path, encoding="utf-8"))
    date = d["date"]
    img_dir = os.path.join(out_dir, "images", date)
    os.makedirs(img_dir, exist_ok=True)

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    manifest = []
    ok = 0
    for p in d["products"]:
        url = p.get("imageUrl")
        rank = p["rank"]
        oid = p["offerId"]
        fname = f"{rank:02d}_{oid}"
        if not url:
            manifest.append([rank, p.get("xianyu_title", ""), "(无图链)", "", ""])
            continue
        try:
            r = sess.get(url, timeout=20)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "")
            ext = "jpg"
            if "webp" in ct: ext = "webp"
            elif "png" in ct: ext = "png"
            elif "jpeg" in ct or "jpg" in ct: ext = "jpg"
            else:
                m = re.search(r"\.(\w{3,4})(?:\?|$)", url)
                if m: ext = m.group(1).lower()[:4]
            fpath = os.path.join(img_dir, f"{fname}.{ext}")
            with open(fpath, "wb") as f:
                f.write(r.content)
            rel = os.path.relpath(fpath, out_dir)
            manifest.append([rank, p.get("xianyu_title", ""), os.path.basename(fpath), rel, url])
            ok += 1
        except Exception as e:
            manifest.append([rank, p.get("xianyu_title", ""), f"(下载失败:{e})", "", url])

    # 打包 zip
    zip_path = os.path.join(out_dir, "images", f"闲鱼商品图_{date}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for _, _, bn, rel, _ in manifest:
            if bn and not bn.startswith("("):
                fp = os.path.join(out_dir, rel)
                if os.path.exists(fp):
                    z.write(fp, arcname=os.path.basename(fp))

    # 清单 CSV (UTF-8 BOM)
    man_path = os.path.join(out_dir, "images", f"闲鱼商品图清单_{date}.csv")
    with open(man_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#", "闲鱼标题", "本地图片文件", "本地路径(上传闲鱼图片空间用)", "1688原图链接"])
        for row in manifest:
            w.writerow(row)

    print(f"下载成功 {ok}/{len(d['products'])} 张")
    print("图片目录:", img_dir)
    print("ZIP:", zip_path)
    print("清单:", man_path)

if __name__ == "__main__":
    main()
