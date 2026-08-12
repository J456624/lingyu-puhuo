# 灵鱼·商品铺货助手 —— 后端部署指南（公网实时版）

本目录 `server.py` 是**全栈服务**：同一个进程既托管手机 App（`app/` 前端，可安装 PWA），
又提供实时后端 API（商品每日更新、订单/采购/物流/售后状态机、SSE 实时消息）。

公网部署后，把得到后端地址填进 App 内「我的 → 后端设置」，即可实现：
- 商品数据每日自动更新，**无需重部署即可刷新**；
- 实时消息经 SSE 秒推；
- 一键铺货/采购/发货直接唤起手机内**已登录**的闲鱼 / 1688 App。

---

## 一键部署到 Render（免费，推荐）

1. 把本目录推送到一个 GitHub 仓库（需含 `server.py` / `app/` / `requirements.txt` / `Procfile`）。
2. 打开 https://render.com → New → Blueprint → 选择该仓库 → 用 `render.yaml` 自动建服务。
   - 或 New → Web Service，Runtime 选 Python，Build: `pip install -r requirements.txt`，Start: `python server.py`。
3. 在 Environment 里加 `LINKFOX_AGENT_API_KEY`（你的 LinkFox 货源密钥），PORT 默认 10000。
4. 部署完成后得到地址，如 `https://lingyu-backend.onrender.com`。

### 让公网版「每日自动更新选品」
Render 免费实例无内置定时任务，用外部定时服务（如 https://cron-job.org ）每天 08:00 触发：
```
GET https://<你的后端>/api/select/refresh
```
该接口会调用 LinkFox 重新拉取当日 1688 二次元 Top10 并写盘，前端下次刷新即生效。

> 免费套餐实例空闲后会休眠，首次访问需冷启动几秒，属正常现象。

---

## 密钥登记表（注册 / 校验 / 吊销）

主软件（灵鱼）的「密钥登录」可由后端集中管控：制造者用**灵钥**生成密钥并「登记到后端」，
灵鱼登录时后端做集中校验，**制造者可随时吊销**某个账号的密钥。

### 关键环境变量（可选）
- `KEY_SEED`：签名种子。若你在灵钥/灵鱼里改成了私有种子，**部署时务必把同一个种子填到 `KEY_SEED`**（或让 App 在请求里带上 seed，本服务端会优先采用请求中的 seed）。
- `MAKER_ACCOUNTS`：拥有吊销/查询权限的账号列表，逗号分隔，默认 `maker`。吊销时必须用该账号的有效密钥作管理凭证。

### 后端密钥接口
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/keys/register` | 灵钥生成后上报：`{account, key, seed?}`（签名须有效） |
| POST | `/api/keys/verify` | 灵鱼登录校验：`{account, key, seed?}` → `{ok, reason?}`（reason=`revoked` 表示已吊销） |
| POST | `/api/keys/revoke` | 吊销：`{account, key, authKey, authAccount, seed?}`（authAccount 须为 maker 或本人） |
| GET  | `/api/keys?makerKey=&makerAccount=maker&seed=` | 制造者拉取已登记密钥列表 |
| GET  | `/api/health` | 返回 `keySeedFingerprint`（种子指纹，用于核对两端是否同一种子） |

### 使用闭环
1. 在灵钥「密钥管理」填后端地址 → 生成「管理密钥」(account=maker) 保存。
2. 在灵钥「生成密钥」生成分发密钥 → 点「登记到后端」。
3. 使用者在灵鱼输入账号+密钥登录（后端校验）。
4. 要停用某人：灵钥「密钥管理」→ 拉取列表 → 点「吊销」。

> 吊销状态持久化在后端 `app_state.json`，重启/重部署均保留。后端不可达时，灵鱼回退为本地离线校验。

---

## 部署到 PythonAnywhere / Railway 同理
- PythonAnywhere：新建 Python Web app（Flask 方式选 Manual），WSGI 文件 `import server; application = server.app` 即可；
  或新建 Bash 控制台直接 `python server.py` 并用其提供的域名。
- Railway：`railway up` 后自动识别 `Procfile`（`web: python server.py`）。

---

## 在 App 内连接公网后端
1. 打开 App → 「我的」→「后端设置」。
2. 填入后端地址（含 http(s)://，不含末尾 `/`），如 `https://lingyu-backend.onrender.com`。
3. 点「保存并重连」→ 顶部状态条显示「联网·实时」，即连接成功。
4. 留空 = 使用同源后端（本机 `python server.py`，或部署时自带后端）。

---

## 本地运行（开发 / 预览）
```bash
# 安装依赖（仅标准库，venv 可选）
python server.py            # 默认端口 8080
PORT=8090 python server.py  # 指定端口
```
浏览器打开 `http://127.0.0.1:8090/` 即为完整可安装 PWA；手机同局域网访问该地址体验唤起原生 App。
