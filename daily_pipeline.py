# -*- coding: utf-8 -*-
"""每日 8:00 选品流水线（供自动化调用）
自动: 拉取 1688 最新上架 + 热销榜 → 评分选 Top10 → 输出 HTML + JSON 到工作目录。
依赖环境变量 LINKFOX_AGENT_API_KEY。
用法: python daily_pipeline.py <workspace_dir>
"""
import os, re, sys, subprocess, datetime

SKILL = r"C:\Users\a\.workbuddy\skills\linkfox-1688-sourcing\scripts"
SELF_DIR = os.path.dirname(os.path.abspath(__file__))

SEARCH_PARAMS = '{"keyWord":"二次元","cycle":"30","sortField":"offerCreateTime","sortType":"desc","pageSize":20}'
# 热销榜 date 取「上一个已完结周」的周日，避免本周刚开始时榜单数据过薄
def _week_sunday(d):
    # weekday(): Monday=0..Sunday=6 -> 上一周日 = 今天 - (weekday+1) 天
    return (d - datetime.timedelta(days=(d.weekday() + 1))).strftime("%Y-%m-%d")

def _run(script, params_json):
    env = os.environ.copy()
    key = env.get("LINKFOX_AGENT_API_KEY")
    if not key:
        print("ERROR: LINKFOX_AGENT_API_KEY 未注入环境变量", file=sys.stderr)
        sys.exit(2)
    p = subprocess.run([sys.executable, os.path.join(SKILL, script), params_json],
                       capture_output=True, text=True, env=env, cwd=SELF_DIR)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"Saved full response:\s*(\S+?)\s*\(", out)
    if not m:
        print("ERROR: 未能从脚本输出解析保存路径。输出:\n", out[-1500:], file=sys.stderr)
        sys.exit(3)
    return m.group(1)

def main():
    if len(sys.argv) < 2:
        print("usage: daily_pipeline.py <workspace_dir>"); sys.exit(1)
    ws = sys.argv[1]
    today = datetime.date.today()
    billboard_date = _week_sunday(today)
    billboard_params = ('{"keyWord":"二次元","pageType":2,"date":"%s",'
                        '"sortField":"orderCount","sortType":"desc","pageSize":20}' % billboard_date)

    print(f"[{datetime.datetime.now():%H:%M:%S}] 拉取最新上架 ...")
    search_path = _run("dld_product_search.py", SEARCH_PARAMS)
    print(f"   -> {search_path}")
    print(f"[{datetime.datetime.now():%H:%M:%S}] 拉取热销周榜 (date={billboard_date}) ...")
    billboard_path = _run("dld_product_billboard.py", billboard_params)
    print(f"   -> {billboard_path}")

    print(f"[{datetime.datetime.now():%H:%M:%S}] 评分选 Top10 ...")
    r = subprocess.run([sys.executable, os.path.join(SELF_DIR, "select_top10.py"),
                        search_path, billboard_path, ws],
                       capture_output=True, text=True, env=os.environ.copy(), cwd=SELF_DIR)
    print(r.stdout)
    if r.returncode != 0:
        print("select_top10 失败:", r.stderr, file=sys.stderr); sys.exit(4)
    # 同步生成 app/products.json(供静态部署版 App 取数, 重部署即刷新)
    rg = subprocess.run([sys.executable, os.path.join(SELF_DIR, "gen_products_json.py")],
                        capture_output=True, text=True, env=os.environ.copy(), cwd=SELF_DIR)
    print(rg.stdout.strip())
    print("DONE")

if __name__ == "__main__":
    main()
