// ===== 灵钥 App —— 后端连接 =====
// 与灵鱼共用同一后端；API.base() 读取 localStorage 'lingyu_api_base'。
// ★ 默认后端地址（部署后把 Render 地址写死在这里，用户无需手动填）
//   留空 '' = 同源。例如填： 'https://lingyu-backend.onrender.com'
//   优先级：用户手动填 > 此处 DEFAULT_BACKEND > 同源
const DEFAULT_BACKEND = '';

window.API = {
  base() {
    return (localStorage.getItem('lingyu_api_base') || DEFAULT_BACKEND || '').replace(/\/+$/, '');
  },
  url(path) {
    const b = this.base();
    return b ? (b + path) : path;
  },
  async get(path) {
    const r = await fetch(this.url(path), { cache: 'no-store' });
    if (!r.ok) throw new Error('http ' + r.status);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(this.url(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
    try { return await r.json(); } catch (e) { return { ok: r.ok }; }
  },
  stream() { return this.url('/api/stream'); }
};
