# 灵鱼·商品铺货助手 —— 公网实时后端部署指南（Vercel + Upstash）

架构已重构为 **Serverless 友好**：
- `core.py`：共享后端内核（所有路由 / 密钥算法 / 状态），本地与 Vercel 共用；
- `server_local.py`：本地常驻进程（开发 / 内网），同源托管 `app/` 与 `/images/`；
- `api/[...path].py`：Vercel Python 函数，转发到 `core.app_dispatch`；
- `vercel.json`：前端静态资源同源托管于 `/app/`，`/api/*` 走函数；
- `store.py`：状态持久化走 **Upstash Redis**（零依赖 REST），未配置则回退本地 `app_state.json`；
- 实时消息改为**前端每 5 秒轮询** `/api/state`（Serverless 标准做法，体验同 SSE）。

Vercel 部署后，应用与接口**同域名**，安装即实时，无需手动填后端地址。

---

## 一、准备 Upstash Redis（免费，状态持久化必需）

Vercel 运行时文件系统只读，密钥登记表 / 订单不能存本地文件，需一个 KV 存储：
1. 打开 https://upstash.com → 注册 → **Create database**（选任意区域，免费版够用）。
2. 进入数据库 → **REST API** 页，复制：
   - `UPSTASH_REST_URL`（形如 `https://xxx.upstash.io`）
   - `UPSTASH_REST_TOKEN`（形如 `Axxx...`）
3. 这两个值稍后填入 Vercel 环境变量。

> 不配置 Upstash 也能跑：状态会回退到 Vercel 实例的临时内存/本地文件，但**重启/扩容后丢失**，仅适合体验。生产务必配 Upstash。

---

## 二、部署到 Vercel（免费）

前置：第 1 步已将本目录推到你的 GitHub 仓库。

1. 打开 https://vercel.com → **Add New → Project** → 导入你的 GitHub 仓库。
2. Framework Preset 选 **Other**，无需构建命令（纯静态 + Python 函数）。
3. **Environment Variables** 添加（Settings → Environment Variables）：
   | Key | Value | 说明 |
   | --- | --- | --- |
   | `LINKFOX_AGENT_API_KEY` | 你的 LinkFox 货源密钥 | 每日更新选品用（可选） |
   | `KEY_SEED` | `LINGYU@MAKE#2026*SEED` | 与灵钥/灵鱼一致的签名种子（若改过私有种子则填私有值） |
   | `MAKER_ACCOUNTS` | `maker` | 拥有吊销/查询权限的账号，逗号分隔 |
   | `UPSTASH_REST_URL` | 上面复制的 URL | 状态持久化 |
   | `UPSTASH_REST_TOKEN` | 上面复制的 Token | 状态持久化 |
4. 点 **Deploy**。完成后得到地址，如 `https://lingyu-puhuo.vercel.app`。
5. 打开该地址即为**完整可安装 PWA + 实时后端**（同域名，无需填地址）。

### 让公网版「每日自动更新选品」
Vercel 无内置定时，用外部定时服务（如 https://cron-job.org ）每天 08:00 触发：
```
GET https://<你的Vercel地址>/api/select/refresh
```
> 注意：`/api/select/refresh` 依赖 `daily_pipeline.py` + LinkFox 环境，在 Vercel 函数内可能受限；
> 若失败，可改为在本地/定时机跑 `python daily_pipeline.py` 生成 JSON 并 `git push`（Vercel 重新部署即更新）。

---

## 三、密钥登记表（注册 / 校验 / 吊销）

主软件（灵鱼）的「密钥登录」由后端集中管控：制造者用**灵钥**生成密钥并「登记到后端」，
灵鱼登录时后端集中校验，**制造者可随时吊销**某个账号的密钥。吊销状态持久化在 Upstash，重启/重部署均保留。

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

> 后端不可达时，灵鱼回退为本地离线校验（仍可被吊销拦截，前提是此前已登记过该密钥的吊销记录）。

---

## 四、把 Vercel 地址写死进 App（可选，给静态版用）

- **Vercel 部署版**：默认后端即同源，开箱实时，无需任何配置。
- **CloudStudio / 其它静态托管版**：在 `app/deeplink.js` 与 `app-keygen/deeplink.js` 顶部把
  `const DEFAULT_BACKEND = '';` 改为你的 Vercel 地址，如
  `const DEFAULT_BACKEND = 'https://lingyu-puhuo.vercel.app';`，重新发布即可。

---

## 五、本地运行（开发 / 预览）

```bash
python server_local.py            # 默认端口 8080
PORT=8090 python server_local.py  # 指定端口
```
浏览器打开 `http://127.0.0.1:8090/` 即为完整可安装 PWA；手机同局域网访问该地址体验唤起原生 App。
本地状态存于 `app_state.json`，与 Upstash 互不干扰。

---

## 附：仍想用 Render / Railway（可选）
- `render.yaml` / `Procfile` 仍在，可用 Render Blueprint 部署（长驻进程，SSE 可用）。
- Railway：`railway up` 自动识别 `Procfile`（`web: python server_local.py`）。
- 这两种方案用常驻进程，状态存 `app_state.json`（挂载持久卷即可），无需 Upstash。
