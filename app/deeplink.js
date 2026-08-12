// ===== 灵鱼 App —— 后端连接 & 原生App唤起 =====
// API: 可配置后端地址（同源 / 自托管公网实时后端）
// DEEPLINK: 调用手机内已登录的闲鱼 / 1688 App，绕开网页登录态

// ★ 默认后端地址（部署后把 Render 地址写死在这里，用户无需手动填）
//   留空 '' = 同源（即托管后端，server.py 同源服务前端+API）。
//   例如填： 'https://lingyu-backend.onrender.com'
//   优先级：用户「后端设置」手动填 > 此处 DEFAULT_BACKEND > 同源
const DEFAULT_BACKEND = '';

window.API = {
  // 后端基地址：localStorage 中可配置公网后端；否则用写死的默认后端；再否则同源
  base() {
    return (localStorage.getItem('lingyu_api_base') || DEFAULT_BACKEND || '').replace(/\/+$/, '');
  },
  url(path) {
    const b = this.base();
    return b ? (b + path) : path;   // 空则相对同源
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

window.DEEPLINK = {
  // 唤起闲鱼App：优先 fleamarket:// 深链，外层兜底到 goofish.com Universal Link
  xianyuHome() { return 'https://www.goofish.com/'; },
  xianyuPublish(p) {
    try {
      const u = new URLSearchParams({
        title: (p.title || p.srcTitle || '').slice(0, 60),
        desc: (p.body || '').slice(0, 2000),
        price: String(Math.round(p.suggestPrice || 0))
      });
      return 'fleamarket://publish?' + u.toString();
    } catch (e) { return 'fleamarket://home'; }
  },
  // 唤起1688App：用商品详情 Universal Link，手机端自动打开已登录的1688
  open1688(url) {
    if (!url) return;
    try { window.location.href = url; } catch (e) {}
  },
  // 复制文本（兼容不支持 clipboard API 的环境）
  async copy(text) {
    try { await navigator.clipboard.writeText(text); return; } catch (e) {}
    try {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); ta.remove();
    } catch (e) {}
  },
  // 保存/下载图片到本机（便于在闲鱼App内上传）
  saveImage(url) {
    if (!url) return;
    const a = document.createElement('a');
    a.href = url; a.download = ''; a.target = '_blank';
    document.body.appendChild(a); a.click(); a.remove();
  }
};
