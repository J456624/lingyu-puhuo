/* 灵鱼·商品铺货助手 Service Worker
 * - 预缓存 App 外壳(离线可用)
 * - /api/products 走 network-first：有网拉最新(每日自动更新)，无网用缓存
 */
const CACHE = 'lingyu-pwa-v4';
const SHELL = [
  './',
  'index.html',
  'style.css',
  'app.js',
  'deeplink.js',
  'keylib.js',
  'data.js',
  'products.js',
  'manifest.webmanifest',
  'icon.svg'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);

  // 商品数据 & 业务 API：network-first
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then(r => r || new Response(JSON.stringify({updated:null,source:'offline',products:[]}), {headers:{'Content-Type':'application/json'}})))
    );
    return;
  }

  // 其余：cache-first，回退网络
  if (req.method !== 'GET') return;
  e.respondWith(
    caches.match(req).then(r => r || fetch(req).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy));
      return res;
    }).catch(() => {
      if (req.headers.get('accept').includes('text/html')) return caches.match('index.html');
    }))
  );
});

// 后台消息：触发立即刷新
self.addEventListener('message', e => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});
