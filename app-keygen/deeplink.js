// ===== 灵钥 App —— 后端连接 =====
// 与灵鱼共用同一后端；API.base() 读取 localStorage 'lingyu_api_base'。
window.API = {
  base() {
    return (localStorage.getItem('lingyu_api_base') || '').replace(/\/+$/, '');
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
