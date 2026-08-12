// ===== 灵鱼·商品铺货助手 App =====
const $ = (s, p=document) => p.querySelector(s);
const $$ = (s, p=document) => [...p.querySelectorAll(s)];

// ===== 全局状态 =====
const state = {
  route: 'home',
  selectedShops: ['xianyu'],
  selectedTool: 'bangzhangfu',
  selectedVersion: 'best',
  selectedProducts: [],   // 选品id列表
  publishStep: 0,         // 0=选店铺 1=选工具 2=授权 3=价格 4=完成
  publishProducts: [],    // 要铺货的商品id
  afterSalesOn: true,
  autoRefundOn: true,
  merchantRole: 'sell',
  selFilter: 'all',
  selSort: 'rank'
};

// ===== 数据来源 / 联网自动更新 =====
// 后端地址可配置(API.base)：同源(本地/部署后端) 或 自托管的公网实时后端。
// 取数优先级: /api/products(实时后端) → ./products.json(静态部署快照) → products.js(打包兜底)
let DATA_META = { updated: null, source: 'bundled', online: false };
async function fetchJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error('http ' + r.status);
  return r.json();
}
async function apiGet(path) { return API.get(path); }
async function apiPost(path, body) { return API.post(path, body); }
// 商品图片：本地 /images 需拼后端地址；远程 alicdn 直连
function imgUrl(p) {
  if (!p) return '';
  const im = p.image || p.imageRemote || '';
  if (im.startsWith('http')) return im;
  const b = API.base();
  return b ? (b + im) : im;
}
async function loadProducts(manual) {
  // 1) 本地/云端后端(实时)
  try {
    const d = await apiGet('./api/products');
    if (d && Array.isArray(d.products) && d.products.length) {
      window.PRODUCTS = d.products;
      DATA_META = { updated: d.updated, source: 'api', online: true };
      finishLoad(); return;
    }
  } catch (e) { /* 继续尝试静态源 */ }
  // 2) 同源静态数据(部署时最新，重部署即刷新)
  try {
    const d = await fetchJSON('./products.json');
    if (d && Array.isArray(d.products) && d.products.length) {
      window.PRODUCTS = d.products;
      DATA_META = { updated: d.updated, source: 'static', online: navigator.onLine };
      finishLoad(); return;
    }
  } catch (e) { /* 回退打包快照 */ }
  // 3) 打包快照(离线兜底)
  DATA_META = { updated: null, source: 'bundled', online: false };
  finishLoad();
}
function finishLoad() {
  const txt = document.getElementById('nettxt');
  if (txt) {
    const tag = { api: '联网·实时', static: '联网·部署快照', bundled: '离线·缓存' }[DATA_META.source] || '';
    txt.textContent = (tag + (DATA_META.updated ? ' ' + DATA_META.updated : '')).trim() || '就绪';
  }
  const dot = document.getElementById('netdot');
  if (dot) dot.className = 'dot ' + (DATA_META.source === 'bundled' ? 'off' : 'on');
  render();
}
function refreshData() { loadProducts(true); }

// ===== 业务状态(仿1688自动分销：铺货/订单/采购/物流/消息/售后) =====
const APP = { listings: [], orders: [], purchases: [], messages: [], aftersales: { auto: true, fast: true, manual: false } };
async function loadState() {
  try {
    const s = await apiGet('./api/state');
    Object.assign(APP, s);
    render();
  } catch (e) { /* 离线容忍 */ }
}
async function apiPost(url, body) {
  return API.post(url, body);
}
function listedIds() { return new Set(APP.listings.map(l => l.productId)); }
function imgOf(pid) { const p = (window.PRODUCTS || []).find(x => x.id === pid); return p ? imgUrl(p) : ''; }
function unreadMsgs() { return APP.messages.filter(m => !m.read).length; }
function timeAgo(ts) {
  const s = Math.floor((Date.now() - (ts || 0)) / 1000);
  if (s < 60) return '刚刚';
  if (s < 3600) return Math.floor(s / 60) + ' 分钟前';
  if (s < 86400) return Math.floor(s / 3600) + ' 小时前';
  return Math.floor(s / 86400) + ' 天前';
}

// 实时消息：SSE 推送
let ES = null;
function connectStream() {
  try {
    ES = new EventSource(API.stream());
    ES.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d.type === 'message' && d.payload) {
          APP.messages.push(d.payload);
          if (state.route === 'messages') render();
        }
      } catch (e) {}
    };
    ES.onerror = () => {};   // 断线自动重连
  } catch (e) {}
}

// ===== 业务动作 =====
// 一键铺货：后端记录"待闲鱼确认" + 唤起手机内已登录的闲鱼App（绕开登录态）
async function doListing(productId, platforms, price, handoff = true) {
  const p = (window.PRODUCTS || []).find(x => x.id === productId);
  if (!p) return;
  const r = await apiPost('./api/listings', {
    productId, platforms: platforms || ['xianyu'],
    price: (price != null ? price : p.suggestPrice), handoff
  });
  await loadState();
  if (handoff && r.ok) showHandoffSheet(p, r.listingId);
  return r;
}

// 唤起闲鱼App：优先 fleamarket:// 深链，失败回退 goofish.com Universal Link
function openXianyuApp(p) {
  const u = new URLSearchParams({
    title: (p.title || p.srcTitle || '').slice(0, 60),
    desc: (p.body || '').slice(0, 2000),
    price: String(Math.round(p.suggestPrice || 0))
  });
  try { window.location.href = 'fleamarket://publish?' + u.toString(); } catch (e) {}
}
function listingOf(pid) { return (APP.listings || []).filter(l => l.productId === pid).slice(-1)[0] || null; }
function listingStatus(pid) { const l = listingOf(pid); return l ? l.status : null; }

// 铺货交接弹层：复制文案 / 存图 / 打开闲鱼 / 确认已上架
function showHandoffSheet(p, listingId) {
  sheet(`
    <div class="hd-h">🚀 已唤起闲鱼App铺货</div>
    <p class="hd-p">本机闲鱼已登录。点「打开闲鱼App发布」跳到闲鱼发布页，粘贴文案+上传图片即可上架（无需再登录）。</p>
    <div class="hd-actions">
      <button class="btn p block" onclick="var pp=PRODUCTS.find(x=>x.id==='${p.id}');openXianyuApp(pp);toast('正在打开闲鱼…')">打开闲鱼App发布</button>
      <div class="gap"></div>
      <button class="btn ghost block" onclick="var pp=PRODUCTS.find(x=>x.id==='${p.id}');DEEPLINK.copy(pp.body||'');toast('已复制文案')">📋 复制闲鱼文案</button>
      <div class="gap"></div>
      <button class="btn ghost block" onclick="var pp=PRODUCTS.find(x=>x.id==='${p.id}');DEEPLINK.saveImage(pp.imageRemote||imgUrl(pp));toast('已开始保存主图')">🖼 保存主图到相册</button>
    </div>
    <div class="hd-foot">没自动跳转？<a onclick="window.open('https://www.goofish.com/','_blank')">点此手动打开闲鱼</a></div>
    <div class="gap"></div>
    <button class="btn p2 block" onclick="confirmListing('${listingId}','${p.id}')">✅ 我已在闲鱼发布，确认已上架</button>
  `);
}
async function confirmListing(listingId, productId) {
  if (!listingId) { const l = listingOf(productId); listingId = l && l.id; }
  if (!listingId) return;
  await apiPost('./api/listings/' + listingId + '/confirm', {});
  closeSheet();
  await loadState();
  toast('已确认上架');
}
async function simulateOrder(productId) {
  await apiPost('./api/orders/simulate', { productId });
  await loadState();
}
async function oneClickPurchase(oid) {
  const r = await apiPost('./api/orders/' + oid + '/purchase', {});
  const o = APP.orders.find(x => x.id === oid);
  const p = (window.PRODUCTS || []).find(x => x.id === (o && o.productId));
  if (p && p.link1688) DEEPLINK.open1688(p.link1688);   // 唤起手机内已登录的1688App完成真实支付
  if (!r.ok) alert(r.error || '操作失败'); else toast('已打开1688，请在App内完成支付');
  await loadState();
}
async function oneClickShip(oid) {
  const r = await apiPost('./api/orders/' + oid + '/ship', {});
  const o = APP.orders.find(x => x.id === oid);
  const p = (window.PRODUCTS || []).find(x => x.id === (o && o.productId));
  if (p && p.link1688) DEEPLINK.open1688(p.link1688);    // 在1688App查看/确认代发物流
  await loadState();
  toast('已标记发货，可在1688查看物流');
}
async function requestRefund(oid) {
  await apiPost('./api/orders/' + oid + '/request-refund', {});
  await loadState();
}
async function oneClickAftersale(oid) {
  await apiPost('./api/orders/' + oid + '/aftersale', {});
  await loadState();
}
async function startPublish() {
  const shops = state.selectedShops.length ? state.selectedShops : ['xianyu'];
  const ids = [];
  for (const pid of state.selectedProducts) {
    const p = (window.PRODUCTS || []).find(x => x.id === pid);
    if (p) { await apiPost('./api/listings', { productId: pid, platforms: shops, price: p.suggestPrice, handoff: true }); ids.push(pid); }
  }
  await loadState();
  showBatchHandoffSheet(ids);
}
function showBatchHandoffSheet(ids) {
  window.__batchIds = ids;
  const items = ids.map(id => { const p = (window.PRODUCTS||[]).find(x=>x.id===id); return p ? `<li>· ${p.title}</li>` : ''; }).join('');
  sheet(`
    <div class="hd-h">🚀 已批量唤起闲鱼App</div>
    <p class="hd-p">已为 ${ids.length} 款商品在闲鱼创建发布任务（本机已登录），点「打开闲鱼」逐条粘贴文案上架。</p>
    <ul class="hd-list">${items}</ul>
    <button class="btn p block" onclick="openXianyuApp(PRODUCTS[0]);toast('正在打开闲鱼…')">打开闲鱼App</button>
    <div class="gap"></div>
    <button class="btn ghost block" onclick="copyBatchText()">📋 复制全部文案</button>
    <div class="gap"></div>
    <button class="btn p2 block" onclick="closeSheet();nav('home')">完成</button>
  `);
}
function copyBatchText() {
  const ids = window.__batchIds || [];
  const t = ids.map(id => { const p = (window.PRODUCTS||[]).find(x=>x.id===id); return p ? (p.body||'') : ''; }).join('\n\n');
  DEEPLINK.copy(t); toast('已复制全部文案');
}
async function saveAftersales() {
  await apiPost('./api/aftersales', APP.aftersales);
  await loadState();
}

// ===== 工具栏 =====
const nav = (route, params={}) => {
  state.route = route;
  state.params = params;
  $$('#tab .t').forEach(t => t.classList.toggle('on', t.dataset.route === route));
  render();
  window.scrollTo(0, 0);
};

const goBack = () => {
  if (state.route === 'product-detail') nav('products');
  else if (state.route === 'publish' && state.publishStep > 0) { state.publishStep--; render(); }
  else if (state.route.startsWith('publish-')) nav('publish');
  else if (['pricing', 'authorize', 'store-select', 'tool-select', 'compare', 'features', 'cycle'].includes(state.route)) nav('home');
  else if (['orders', 'batch-pay', 'after-sales', 'messages'].includes(state.route)) nav('orders');
  else if (['merchant-join', 'merchant-status'].includes(state.route)) nav('merchant');
  else if (['distributor', 'distributor-list', 'distributor-detail'].includes(state.route)) nav('merchant');
  else if (state.route === 'settings') nav('me');
  else history.back();
};

const sheet = (html) => {
  $('#sheet').innerHTML = `<button class="close" onclick="closeSheet()">✕</button>${html}`;
  $('#mask').classList.add('on');
};
const closeSheet = () => $('#mask').classList.remove('on');
$('#mask').addEventListener('click', e => { if (e.target.id === 'mask') closeSheet(); });

function toast(msg) {
  let t = $('#toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('on');
  clearTimeout(t._tm); t._tm = setTimeout(() => t.classList.remove('on'), 1600);
}
function reconnectStream() { if (ES) { try { ES.close(); } catch (e) {} ES = null; } connectStream(); }

// ===== 主渲染 =====
function render() {
  const v = $('#view');
  switch (state.route) {
    case 'home': v.innerHTML = renderHome(); break;
    case 'products': v.innerHTML = renderProducts(); break;
    case 'product-detail': v.innerHTML = renderProductDetail(state.params.id); break;
    case 'publish': v.innerHTML = renderPublish(); break;
    case 'publish-shops': v.innerHTML = renderPublishShops(); break;
    case 'publish-tool': v.innerHTML = renderPublishTool(); break;
    case 'publish-authorize': v.innerHTML = renderAuthorize(); break;
    case 'publish-pricing': v.innerHTML = renderPricing(); break;
    case 'publish-compare': v.innerHTML = renderCompare(); break;
    case 'publish-features': v.innerHTML = renderFeatures(); break;
    case 'publish-cycle': v.innerHTML = renderCycle(); break;
    case 'publish-done': v.innerHTML = renderPublishDone(); break;
    case 'orders': v.innerHTML = renderOrders(); break;
    case 'order-detail': v.innerHTML = renderOrderDetail(state.params.id); break;
    case 'batch-pay': v.innerHTML = renderBatchPay(); break;
    case 'after-sales': v.innerHTML = renderAfterSales(); break;
    case 'messages': v.innerHTML = renderMessages(); break;
    case 'merchant': v.innerHTML = renderMerchant(); break;
    case 'merchant-join': v.innerHTML = renderMerchantJoin(); break;
    case 'merchant-status': v.innerHTML = renderMerchantStatus(); break;
    case 'distributor': v.innerHTML = renderDistributor(); break;
    case 'distributor-list': v.innerHTML = renderDistributorList(); break;
    case 'distributor-detail': v.innerHTML = renderDistributorDetail(state.params.id); break;
    case 'me': v.innerHTML = renderMe(); break;
    case 'settings': v.innerHTML = renderSettings(); break;
  }
  bindRouteLinks();
}

// ===== 页面：工作台 =====
function renderHome() {
  const today = new Date().toISOString().slice(0,10);
  const orders = APP.orders;
  const nWaitPay = orders.filter(o => o.status === '待采购').length;
  const nWaitShip = orders.filter(o => o.status === '待发货').length;
  const nRefund = orders.filter(o => o.status === '退款中').length;
  const listed = listedIds().size;
  const totalProfit = PRODUCTS.reduce((a,p)=>a+p.profit,0);
  return `
  <div class="hero">
    <h1>灵鱼·铺货助手</h1>
    <p>${today} · 自动分销·全流程自动化 ${DATA_META.updated && DATA_META.online ? '· 已同步 '+DATA_META.updated : ''}</p>
    <div class="stats">
      <div class="stat"><b>${PRODUCTS.length}</b><span>今日候选</span></div>
      <div class="stat"><b>${listed || '—'}</b><span>已铺货</span></div>
      <div class="stat"><b>¥${totalProfit.toFixed(0)}</b><span>预估总利</span></div>
    </div>
  </div>

  <div class="grid6">
    <div class="g" onclick="nav('publish')"><div class="ic">🚀</div><div class="tt">一键铺货</div><div class="bd">${listed} 款已铺</div></div>
    <div class="g" onclick="nav('products')"><div class="ic">📦</div><div class="tt">智能选品</div><div class="bd">实时同步</div></div>
    <div class="g" onclick="nav('orders')"><div class="ic">🛒</div><div class="tt">一键采购</div><div class="bd">${nWaitPay} 待采购</div></div>
    <div class="g" onclick="nav('orders')"><div class="ic">📤</div><div class="tt">一键发货</div><div class="bd">${nWaitShip} 待发货</div></div>
    <div class="g" onclick="nav('after-sales')"><div class="ic">🛡️</div><div class="tt">一键售后</div><div class="bd">${nRefund} 待处理</div></div>
    <div class="g" onclick="nav('messages')"><div class="ic">💬</div><div class="tt">实时消息</div><div class="bd">${unreadMsgs()} 条新</div></div>
  </div>

  <div class="banner"><span>⭐</span><div>已接入<b> Linkfox 1688 货源</b>，每天 8:00 自动同步最新+热销，AI 优化文案，10 款最优推送到你的手机</div></div>

  <div class="h-tt"><b>⚡ 今日待办</b><a onclick="nav('orders')" style="color:var(--p)">查看全部 ›</a></div>
  <div class="card">
    <div class="row" style="justify-content:space-between">
      <div><span class="tag y">待采购</span><b style="margin-left:6px">${nWaitPay} 笔</b><span style="color:#888;margin-left:6px;font-size:12px">需去 1688 代发下单</span></div>
      <button class="btn p sm" onclick="nav('batch-pay')">批量支付</button>
    </div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between">
      <div><span class="tag p">待发货</span><b style="margin-left:6px">${nWaitShip} 笔</b><span style="color:#888;margin-left:6px;font-size:12px">需回传物流单号</span></div>
      <button class="btn p2 sm" onclick="nav('orders')">查看</button>
    </div>
    ${nRefund ? `<div class="gap"></div><div class="row" style="justify-content:space-between">
      <div><span class="tag warn">退款中</span><b style="margin-left:6px">${nRefund} 笔</b><span style="color:#888;margin-left:6px;font-size:12px">待一键售后</span></div>
      <button class="btn ghost sm" onclick="nav('orders')">去处理</button></div>` : ''}
  </div>

  <div class="h-tt"><b>🔥 今日 Top 3 候选</b><a onclick="nav('products')" style="color:var(--p)">全部 10 款 ›</a></div>
  ${PRODUCTS.slice(0,3).map(p => prodCard(p)).join('')}

  <div class="h-tt"><b>🤝 分销中心</b><a onclick="nav('merchant')" style="color:var(--p)">进入 ›</a></div>
  <div class="dual">
    <div class="d supply" onclick="nav('merchant-join')">
      <div class="em">🏭</div><h3>商家入驻</h3>
      <p>供货商 / 分销商家 快速入驻，开通铺货与结算</p>
      <span class="go">去入驻 ›</span>
    </div>
    <div class="d dist" onclick="nav('distributor')">
      <div class="em">📣</div><h3>分销员招募</h3>
      <p>生成专属邀请，下级出单你拿佣金分成</p>
      <span class="go">去招募 ›</span>
    </div>
  </div>
  `;
}

// ===== 页面：智能选品 =====
function smartFiltered() {
  let list = PRODUCTS.slice();
  const f = state.selFilter || 'all';
  if (f === 'hot') list = list.filter(p => p.src !== '最新上架');
  else if (f === 'new') list = list.filter(p => p.src === '最新上架');
  else if (f === 'profit') list = list.filter(p => p.profit >= 15);
  else if (f === 'lead') list = list.filter(p => p.consignPrice <= 5);
  const s = state.selSort || 'rank';
  list.sort((a, b) => {
    if (s === 'profit') return b.profit - a.profit;
    if (s === 'margin') return b.margin - a.margin;
    if (s === 'price') return a.suggestPrice - b.suggestPrice;
    return a.rank - b.rank;
  });
  return list;
}
async function refreshSelection() {
  const btn = $('#rfbtn'); if (btn) { btn.textContent = '重拉中…'; btn.disabled = true; }
  try {
    const d = await apiGet('./api/select/refresh');
    if (d && Array.isArray(d.products) && d.products.length) {
      window.PRODUCTS = d.products;
      DATA_META = { updated: d.updated, source: 'api', online: true };
      alert('已从 1688 实时重拉 '+d.products.length+' 款最新候选');
    } else {
      alert('重拉失败：'+(d && d.error || '无数据'));
    }
  } catch (e) { alert('重拉失败：网络或密钥异常'); }
  if (btn) { btn.textContent = '↻'; btn.disabled = false; }
  render();
}
function renderProducts() {
  const list = smartFiltered();
  const f = state.selFilter || 'all';
  const s = state.selSort || 'rank';
  const chips = [['all','全部'],['hot','热销'],['new','新款'],['profit','高利润'],['lead','引流款']];
  const sorts = [['rank','综合'],['profit','利润'],['margin','毛利率'],['price','低价']];
  return `
  <div class="nav">
    <div class="left"></div>
    <div class="title">智能选品 · 二次元</div>
    <div class="right"><button id="rfbtn" class="more" onclick="refreshSelection()">↻</button></div>
  </div>
  <div class="card flat" style="margin-top:8px">
    <div class="row" style="justify-content:space-between">
      <div><span style="font-size:12px;color:#888">来源</span>
        <span class="tag p" style="margin-left:6px">Linkfox·1688</span>
        <span class="tag" style="margin-left:4px">最新+热销</span>
      </div>
      <span style="font-size:12px;color:#888">${list.length} / ${PRODUCTS.length} 款</span>
    </div>
  </div>
  <div class="chips" style="display:flex;gap:8px;overflow-x:auto;padding:10px 14px">
    ${chips.map(c=>`<span class="chip ${f===c[0]?'on':''}" onclick="state.selFilter='${c[0]}';render()">${c[1]}</span>`).join('')}
  </div>
  <div class="chips" style="display:flex;gap:8px;overflow-x:auto;padding:0 14px 6px">
    <span style="font-size:12px;color:#999;align-self:center;margin-right:4px">排序</span>
    ${sorts.map(c=>`<span class="chip sm ${s===c[0]?'on':''}" onclick="state.selSort='${c[0]}';render()">${c[1]}</span>`).join('')}
  </div>
  ${list.map(p => prodCard(p)).join('')}
  <div class="btn-row" style="position:sticky;bottom:0;background:#fff;border-top:1px solid var(--bd)">
    <button class="btn ghost" onclick="state.selectedProducts=PRODUCTS.map(p=>p.id);render()">全选</button>
    <button class="btn p block" style="flex:2" onclick="publishSelected()">
      立即铺货 (<span id="cnt">${state.selectedProducts.length||0}</span>)
    </button>
  </div>`;
}

function prodCard(p) {
  const sel = state.selectedProducts.includes(p.id);
  const lst = listingOf(p.id);
  const listed = lst && lst.status === '已发布';
  const pending = lst && lst.status === '待闲鱼确认';
  return `
  <div class="prod" onclick="toggleSel('${p.id}')">
    <img src="${imgUrl(p)}" onerror="this.src='${p.imageRemote}';this.onerror=null">
    <div class="info">
      <h4>${p.title}</h4>
      <div class="row" style="gap:4px">
        <span class="tag ${p.src==='最新上架'?'y':'p'}">${p.src}</span>
        <span class="tag" style="background:#e8f5ee;color:#0a8a3f">${p.sales}</span>
        ${listed ? '<span class="tag" style="background:#fff0e6;color:#ff5000">已铺货</span>' : ''}
        ${pending ? '<span class="tag" style="background:#fff8e6;color:#a06600">待闲鱼确认</span>' : ''}
      </div>
      <div style="margin-top:5px"><span class="price">¥${p.suggestPrice.toFixed(1)}</span>
        <span class="cost">¥${p.consignPrice.toFixed(1)}</span></div>
      <div class="profit">预估利润 ¥${p.profit.toFixed(1)} · 毛利率 ${p.margin.toFixed(0)}%</div>
      <div class="meta">🏭 ${p.supplier.slice(0,12)}</div>
    </div>
    <div style="text-align:center;flex-shrink:0">
      ${listed
        ? '<button class="btn ghost sm" onclick="event.stopPropagation()">已铺</button>'
        : pending
          ? `<button class="btn p2 sm" onclick="event.stopPropagation();confirmListing('${lst.id}','${p.id}')">确认上架</button>`
          : `<button class="btn ${sel?'p':'ghost'} sm" onclick="event.stopPropagation();doListing('${p.id}')">铺货</button>`}
    </div>
  </div>`;
}

function toggleSel(id) {
  // 手机端单点选 + 进详情
  if (window.innerWidth < 480) {
    const i = state.selectedProducts.indexOf(id);
    if (i >= 0) state.selectedProducts.splice(i, 1);
    else state.selectedProducts.push(id);
    const c = $('#cnt'); if (c) c.textContent = state.selectedProducts.length;
    render();
  }
}

// ===== 页面：商品详情 =====
function renderProductDetail(id) {
  const p = PRODUCTS.find(x => x.id === id);
  if (!p) return '<div class="empty">商品不存在</div>';
  return `
  <div class="nav">
    <button class="back" onclick="goBack()">‹</button>
    <div class="title">商品详情</div>
    <button class="more" onclick="shareProduct('${p.id}')">⋯</button>
  </div>
  <div class="pd-img"><img src="${imgUrl(p)}" onerror="this.src='${p.imageRemote}';this.onerror=null"></div>
  <div class="pd-thumbs">
    ${[1,2,3,4,5].map(i=>`<div class="th ${i===1?'on':''}" style="background-image:url('${imgUrl(p)}')"></div>`).join('')}
  </div>
  <div class="pd-price">
    <span class="now">¥${p.suggestPrice.toFixed(1)}</span>
    <span class="old">¥${(p.suggestPrice*1.4).toFixed(1)}</span>
    <span class="tag">${p.tier}</span>
    <span style="margin-left:auto;color:#888;font-size:12px">已售 ${Math.floor(Math.random()*200+50)}</span>
  </div>
  <div class="pd-trust">
    <span>🏪 店铺回头率 <b class="p">47.2%</b></span>
    <span style="color:#ddd">|</span>
    <span>好评率 <b class="p">93.6%</b></span>
    <span style="margin-left:auto"><span class="tag p">包邮</span></span>
  </div>
  <div class="pd-h1">${p.srcTitle}</div>
  <div class="pd-tabs">
    <div class="t on">商品</div><div class="t">详情</div><div class="t">评价</div><div class="t">推荐</div>
  </div>

  <div class="pd-meta-row"><span class="l">产品规格</span><span class="v">高:23.5CM · 材质:PVC · 已涂装完成品</span></div>
  <div class="pd-meta-row"><span class="l">包装方式</span><span class="v">塑胶+彩盒 · 真空包装</span></div>
  <div class="pd-meta-row"><span class="l">彩盒规格</span><span class="v">12×12×25.7cm</span></div>
  <div class="pd-meta-row"><span class="l">装箱规格</span><span class="v">71×48×52cm · 48 盒/箱</span></div>
  <div class="pd-meta-row"><span class="l">供应商</span><span class="v">${p.supplier} · 入驻 3 年</span></div>
  <div class="pd-meta-row"><span class="l">发货地</span><span class="v">广东广州 · 运费 5 元起</span></div>

  <div class="pd-spec">
    <div class="pd-ship"><span class="ic">✓</span> 承诺 45 天发货 &nbsp; <span class="ic">✓</span> 延期必赔 · 品质保障 · 破损包赔</div>
    <div style="margin-top:6px">先采后付 0 元下单，货到满意再付款</div>
  </div>

  <div class="card">
    <div class="row" style="justify-content:space-between;align-items:center">
      <b style="font-size:14px">分销代发</b>
      <span class="tag g">代发专享价 ¥${p.consignPrice.toFixed(1)}</span>
    </div>
    <div class="gap"></div>
    <div class="row" style="gap:8px">
      <button class="btn p block" style="flex:1" onclick="publishOne('${p.id}')">立即铺货</button>
      <button class="btn ghost" style="flex:1" onclick="daifaOne('${p.id}')">代发下单</button>
    </div>
  </div>

  <div class="card">
    <b style="font-size:14px">📝 AI 优化文案</b>
    <div class="gap"></div>
    <div style="font-size:13px;line-height:1.7;white-space:pre-wrap;color:#444">${p.body}</div>
    <div class="gap"></div>
    <div style="font-size:12px;color:#1677ff">${p.tags.join(' ')}</div>
  </div>

  <div class="pd-cta" style="position:sticky;bottom:0">
    <button class="btn ghost" onclick="alert('已加入收藏')">★ 收藏</button>
    <button class="btn p" onclick="publishOne('${p.id}')">立即铺货</button>
  </div>`;
}

function shareProduct(id) { alert('分享链接已复制，粘贴到微信即可'); }
function publishOne(id) { doListing(id, ['xianyu'], null, true); }
function daifaOne(id) { const p = (window.PRODUCTS||[]).find(x=>x.id===id); if (p && p.link1688) DEEPLINK.open1688(p.link1688); toast('已打开1688代发下单'); }

// ===== 页面：发布流程入口(默认进入选店铺) =====
function renderPublish() {
  if (!state.selectedProducts.length) {
    return `
    <div class="nav"><div></div><div class="title">一键铺货</div><div></div></div>
    <div class="card" style="text-align:center;padding:40px 20px">
      <div style="font-size:46px">🚀</div>
      <h3 style="margin:12px 0 6px">先选要铺货的商品</h3>
      <p style="color:#888;font-size:13px">去「选品」勾选商品，再回到这里一键铺到多个店铺</p>
      <button class="btn p" style="margin-top:10px" onclick="nav('products')">去选品</button>
    </div>`;
  }
  return renderPublishShops();
}

// ===== 页面：发布流程 - 选店铺 =====
function renderPublishShops() {
  return `
  <div class="nav">
    <button class="back" onclick="goBack()">‹</button>
    <div class="title">选择我的店铺</div>
    <button class="back" onclick="alert('已阅读并同意《1688用户授权协议》')" style="font-size:12px">协议</button>
  </div>
  <div style="padding:10px 14px;background:#fff;font-size:12.5px;color:#888">
    已选 ${state.selectedShops.length} 个店铺，将要铺货 ${state.selectedProducts.length} 款
  </div>
  <div class="shops">
    ${SHOPS.map(s => `
      <div class="shop ${state.selectedShops.includes(s.id)?'on':''}" onclick="toggleShop('${s.id}')">
        <div class="logo" style="background:${s.color}">${s.icon}</div>
        <div class="nm">${s.name}</div>
        <div class="check">✓</div>
      </div>`).join('')}
  </div>
  <div class="notice">⚠️ 勾选店铺需先完成<b>工具授权</b>，未授权的店铺会被引导到授权页</div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">下一步</button>
  </div>`;
}

function toggleShop(id) {
  const i = state.selectedShops.indexOf(id);
  if (i >= 0) state.selectedShops.splice(i, 1);
  else state.selectedShops.push(id);
  render();
}

// ===== 页面：发布流程 - 选工具 =====
function renderPublishTool() {
  const tools = [
    { id: "bangzhangfu", ic: "帮", color: "#5b3aa6", name: "自动分销", desc: "销量领先，AI 赋能多渠道铺货，爆款光投", badge: "推荐", price: 4.89, purchased: true }
  ];
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">换工具</div><div></div></div>
  <div style="padding:10px 14px;background:#fff;font-size:12.5px;color:#888;border-bottom:1px solid #f0f1f3">
    因跨平台接口限制，需先购买并完成工具授权
  </div>
  ${tools.map(t => `
    <div class="tool ${state.selectedTool===t.id?'on':''}" onclick="state.selectedTool='${t.id}';render()">
      <div class="ic">${t.ic}</div>
      <div style="flex:1;min-width:0">
        <div class="nm">${t.name} <span class="badge">${t.badge}</span> <span style="color:#ff5000">★${t.price}</span></div>
        <div class="desc">${t.desc}</div>
        <div class="desc">1千万+订购用户 · 支持渠道：拼多多/抖音/淘宝/闲鱼/小红书/...</div>
      </div>
      ${t.purchased?'<span class="purchased">已订购</span>':'<div class="check">✓</div>'}
    </div>`).join('')}
  <div class="btn-row"><button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">下一步</button></div>`;
}

// ===== 页面：4步授权 =====
function renderAuthorize() {
  const steps = [
    { n: 1, ic: "帮", name: "订购 1688 自动分销插件", desc: "为解锁铺货、订单采购等核心能力，需先完成订购", btn: "第1步, 立即订购" },
    { n: 2, ic: "帮", name: "授权 1688 自动分销插件", desc: "授权后获取 1688 铺货、订单采购权限", btn: "点此授权" },
    { n: 3, ic: "闲", name: "登录并授权闲鱼管家", desc: "用于获取您的闲鱼店铺信息完成绑店", btn: "第2步, 立即授权" },
    { n: 4, ic: "🔗", name: "绑定其他渠道(可选)", desc: "支持拼多多/小红书/抖音/淘宝/快手/京东/饿了么", btn: "去绑定" }
  ];
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">店铺授权引导</div><div></div></div>
  <div style="padding:10px 14px;background:#fff8e6;color:#a06600;font-size:12px;border-bottom:1px solid #f0f1f3">
    因跨平台接口限制，需完成工具授权完成绑店
  </div>
  ${steps.map(s => `
    <div class="step">
      <div class="num">${s.n}</div>
      <div class="ic">${s.ic}</div>
      <div class="info">
        <h5>${s.name}</h5>
        <p>${s.desc}</p>
        <button class="btn p sm" onclick="alert('演示：${s.name} 授权已通过')">${s.btn}</button>
      </div>
    </div>`).join('')}
  <div class="card">
    <b style="font-size:13.5px">绑定其他</b>
    <div class="gap"></div>
    <div class="row" style="gap:14px;flex-wrap:wrap">
      ${['拼多多','小红书','抖音','淘宝','快手','京东','饿了么'].map(x=>`<span class="tag">${x}</span>`).join('')}
    </div>
  </div>
  <div class="card">
    <button class="btn p2 block" onclick="alert('演示：已切换到人工代铺店')">🧑‍💼 人工代铺店</button>
  </div>
  <div class="btn-row"><button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">下一步</button></div>`;
}

// ===== 页面：价格 =====
function renderPricing() {
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">服务详情</div><div class="more">⋯</div></div>
  <div class="card">
    <div class="row" style="gap:10px">
      <div class="tool" style="margin:0;flex:1;border:none;padding:0;background:transparent">
        <div class="ic" style="background:#5b3aa6">帮</div>
        <div style="flex:1">
          <div class="nm">自动分销</div>
          <div class="desc">哈尔滨灵鱼科技有限公司</div>
        </div>
      </div>
    </div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between">
      <b style="color:#ff5000;font-size:22px">¥50-420</b>
      <span class="tag p" style="background:#fff3ec">满135元减27元</span>
    </div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between;font-size:12.5px">
      <span style="color:#888">累计销售 300 套以上 · 评分 5.0</span>
      <span style="color:#ff5000">联系客服 ›</span>
    </div>
  </div>
  <div class="notice">⚠️ 友信提示：服务商不得向买家收取应用信息页面展示的服务价格外的费用。如服务商另行收取接口等费用，请注意消费损失风险。</div>
  <div class="pd-tabs" style="background:#fff;border-radius:12px 12px 0 0;overflow:hidden">
    <div class="t on">服务详情</div><div class="t">用户评价</div>
  </div>
  <div class="card flat" style="margin:0 12px;border-radius:0;border-left:0;border-right:0">
    <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 240'><rect width='320' height='240' fill='%23291a3a'/><text x='160' y='100' text-anchor='middle' fill='%23ff5000' font-size='20' font-weight='bold' font-family='sans-serif'>0 国货电商必备</text><text x='160' y='140' text-anchor='middle' fill='%23fff' font-size='14' font-family='sans-serif'>1688 货源一键搬运</text><text x='160' y='170' text-anchor='middle' fill='%23ffd700' font-size='12' font-family='sans-serif'>拼多多 抖音 闲鱼 小红书 淘宝 视频号</text><circle cx='160' cy='60' r='30' fill='%23ff5000'/><text x='160' y='65' text-anchor='middle' fill='%23fff' font-size='16' font-weight='bold' font-family='sans-serif'>1688</text></svg>" style="width:100%;border-radius:8px">
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">下一步</button></div>`;
}

// ===== 页面：版本对比 =====
function renderCompare() {
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">服务详情</div><div class="more">⋯</div></div>
  <div class="card" style="text-align:center;background:linear-gradient(180deg,#fff,#fafbfc)">
    <span class="tag p">出单宝版 / 高级版</span>
    <div style="margin-top:6px"><b style="color:#a300b3;font-size:16px">效率高于人工</b>
      <b style="color:#ff5000;font-size:36px;margin:0 4px">90</b><b style="color:#ff5000;font-size:18px">%</b></div>
    <div style="font-size:11.5px;color:#888;margin-top:4px">因跨平台铺货，需同时订购多个软件(自动分销、对应平台的铺货软件)实现铺货回流</div>
  </div>
  ${PRICING.features.map(grp => `
    <div style="padding:8px 14px 4px;background:#f7f8fa;font-size:12.5px;color:#666;font-weight:600">${grp.cat}</div>
    <div class="compare" style="margin:0 12px 6px">
      <table>
        <thead><tr><th>环节</th>
          ${PRICING.versions.map(v => `<th class="${v.hot?'ver-h hot':''}">${v.name}</th>`).join('')}
        </tr></thead>
        <tbody>${grp.rows.map(r => `
          <tr>
            <td><span class="l">${r.name}${r.d?`<span class="d">${r.d}</span>`:''}</span></td>
            ${PRICING.versions.map(v => `<td>${r.v[v.id]?'<span class="ok">✓</span>':'<span class="no">×</span>'}</td>`).join('')}
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`).join('')}
  <div class="btn-row">
    <button class="btn ghost" onclick="nav('publish-compare')">↻ 重新对比</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">立即购买出单宝版</button></div>`;
}

// ===== 页面：特性图 =====
function renderFeatures() {
  const fs = [
    { ic: "🚚", tt: "一键搬家", dd: "选好品·一键铺 商品详情极速搬" },
    { ic: "🛒", tt: "一键采购", dd: "无需人工·自动同步厂家·一键支付采购" },
    { ic: "📤", tt: "一键发货", dd: "无需人工·小店订单自动同步发货信息" },
    { ic: "🛡️", tt: "一键售后", dd: "系统自动向供应商同步退款/退货信息" },
    { ic: "💬", tt: "实时消息", dd: "商品消息变动·通过专属消息实时接收" },
    { ic: "💰", tt: "收货提现", dd: "铺货店铺自动加价售卖 买家收货小店提现" }
  ];
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">服务详情</div><div class="more">⋯</div></div>
  <div class="card" style="text-align:center;background:linear-gradient(180deg,#fff7f0,#fff)">
    <b style="color:#ff5000">店家必看!!!</b>
    <div style="margin-top:4px"><b style="font-size:18px">如何帮我高效轻松赚钱?</b></div>
    <span class="tag p" style="margin-top:6px">提升效率 + 减少人工</span>
  </div>
  <div class="flow">
    <div class="row2">${fs.map(f => `<div class="b"><div class="ic">${f.ic}</div><div class="tt">${f.tt}</div><div class="dd">${f.dd}</div></div>`).join('')}</div>
    <div style="text-align:center;margin:14px 0"><b style="color:#a300b3;font-size:18px">代发卖货 - 全流程自动化</b><br><span class="tag" style="margin-top:6px">电脑 / 手机双端共用</span></div>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="nextPublishStep()">下一步</button></div>`;
}

// ===== 页面：代发闭环 =====
function renderCycle() {
  const cyc = [
    { tt: "自动铺货", dd: "免手动上架商品" },
    { tt: "自动采购", dd: "免手动导表采购" },
    { tt: "自动售后", dd: "免手动退款/退货" },
    { tt: "自动发货", dd: "免手动发货" }
  ];
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">服务详情</div><div class="more">⋯</div></div>
  <div class="card" style="text-align:center;background:linear-gradient(180deg,#fff7f0,#fff)">
    <b style="color:#a300b3;font-size:18px">手机 + 电脑双端使用</b><br>
    <span class="tag p" style="margin-top:6px">个人 / 企业使用全搞定</span>
  </div>
  <div class="flow">
    <div style="text-align:center"><div style="display:inline-block;background:linear-gradient(135deg,#5b3aa6,#7e54d1);color:#fff;width:64px;height:64px;border-radius:16px;line-height:64px;font-size:32px;font-weight:700;box-shadow:0 4px 12px rgba(91,58,166,.4)">帮</div></div>
    <div class="cycle" style="margin-top:10px">
      ${cyc.map(c => `<div class="b"><b style="color:var(--p5)">${c.tt}</b><div style="color:#999;font-size:11.5px;margin-top:2px">${c.dd}</div></div>`).join('')}
    </div>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">上一步</button>
    <button class="btn p block" style="flex:2" onclick="startPublish()">开始铺货</button></div>`;
}

// ===== 页面：发布完成 =====
function renderPublishDone() {
  return `
  <div class="nav"><div></div><div class="title">铺货完成</div><div></div></div>
  <div style="text-align:center;padding:60px 20px">
    <div style="font-size:64px">🎉</div>
    <h2 style="margin:14px 0 6px">铺货任务已提交</h2>
    <p style="color:#888;font-size:13px;margin:0">${state.selectedProducts.length} 款商品 → 唤起本机已登录闲鱼App<br>在闲鱼内粘贴文案+上传图片即可上架</p>
  </div>
  <div class="card">
    <b style="font-size:14px">📊 任务概览</b>
    <div class="gap"></div>
    <div style="font-size:13px;line-height:2">
      <div class="row" style="justify-content:space-between"><span style="color:#888">铺货商品</span><b>${state.selectedProducts.length} 款</b></div>
      <div class="row" style="justify-content:space-between"><span style="color:#888">目标店铺</span><b>${state.selectedShops.map(s=>SHOPS.find(x=>x.id===s)?.name).join('、')}</b></div>
      <div class="row" style="justify-content:space-between"><span style="color:#888">代发工具</span><b>自动分销</b></div>
      <div class="row" style="justify-content:space-between"><span style="color:#888">服务版本</span><b style="color:#ff5000">出单宝版</b></div>
    </div>
  </div>
  <div class="card">
    <b style="font-size:14px">💡 接下来</b>
    <div class="gap"></div>
    <div style="font-size:12.5px;color:#666;line-height:1.8">
      1. 在弹出的闲鱼App中粘贴文案+上传图片完成发布<br>
      2. 回到本App点「确认已上架」同步状态<br>
      3. 接单后一键采购会直接唤起1688App完成代付<br>
      4. 物流单号自动回传，收益可在「我的」中提现
    </div>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="nav('products')">继续选品</button>
    <button class="btn p block" style="flex:2" onclick="nav('home')">回到工作台</button>
  </div>`;
}

// ===== 发布流程控制器 =====
const FLOW = ['publish-shops','publish-tool','publish-authorize','publish-pricing','publish-compare','publish-features','publish-cycle','publish-done'];

function nextPublishStep() {
  // 找到当前位置
  const idx = FLOW.indexOf(state.route);
  if (idx >= 0 && idx < FLOW.length - 1) {
    nav(FLOW[idx + 1]);
  } else if (state.route === 'publish-done') {
    nav('home');
  } else {
    nav('publish-shops');
  }
}

// ===== 页面：订单 =====
const ST_CLS = { '待采购':'y', '待发货':'p', '待收货':'g', '退款中':'warn', '已退款':'gr' };
function orderActions(o) {
  const open1688 = `<button class="btn ghost sm" onclick="event.stopPropagation();openOrder1688('${o.id}')">1688</button>`;
  if (o.status === '待采购') return `<button class="btn p sm" onclick="event.stopPropagation();oneClickPurchase('${o.id}')">一键采购</button>${open1688}`;
  if (o.status === '待发货') return `<button class="btn p2 sm" onclick="event.stopPropagation();oneClickShip('${o.id}')">一键发货</button>${open1688}`;
  if (o.status === '退款中') return `<button class="btn warn sm" onclick="event.stopPropagation();oneClickAftersale('${o.id}')">一键售后</button>`;
  return open1688;
}
function openOrder1688(oid) {
  const o = APP.orders.find(x => x.id === oid);
  const p = (window.PRODUCTS || []).find(x => x.id === (o && o.productId));
  if (p && p.link1688) DEEPLINK.open1688(p.link1688); else alert('暂无1688链接');
}
function renderOrders() {
  const orders = APP.orders;
  const counts = {
    all: orders.length,
    pay: orders.filter(o => o.status === '待采购').length,
    ship: orders.filter(o => o.status === '待发货').length,
    done: orders.filter(o => o.status === '待收货' || o.status === '已退款').length,
  };
  return `
  <div class="nav"><div></div><div class="title">订单管理</div>
    <div class="more" onclick="alert('演示：模拟买家在你闲鱼下单');simulateOrder()">＋接单</div></div>
  <div class="pd-tabs" style="background:#fff">
    <div class="t on">全部 ${counts.all}</div>
    <div class="t">待采购 ${counts.pay}</div>
    <div class="t">待发货 ${counts.ship}</div>
    <div class="t">已发/退 ${counts.done}</div>
  </div>
  ${orders.length === 0 ? `
    <div class="empty" style="text-align:center;padding:50px 20px;color:#999">
      <div style="font-size:48px">🛒</div>
      <p>还没有订单</p>
      <button class="btn p" onclick="simulateOrder()">模拟一笔接单</button>
      <p style="font-size:12px;margin-top:10px">提示：铺货后，闲鱼买家下单会进入这里，逐一点击「一键采购→一键发货」即可完成代发</p>
    </div>` : ''}
  ${orders.slice().reverse().map(o => `
    <div class="order" onclick="nav('order-detail',{id:'${o.id}'})">
      <div class="top"><b>${o.title}</b><span class="tag ${ST_CLS[o.status]||''}">${o.status}</span></div>
      <div class="row">
        <img src="${imgOf(o.productId)}" onerror="this.src='${PRODUCTS[0].image}';this.onerror=null">
        <div class="inf">
          <h5>${o.title}</h5>
          <p>👤 ${o.buyer} · 📍 ${o.addr}</p>
          <p>⏰ ${o.createdAt}</p>
        </div>
        <div class="pr">
          <b>¥${o.price.toFixed(1)}</b>
          <span class="pft">利 ¥${o.profit.toFixed(1)}</span>
        </div>
      </div>
      <div class="btns">
        ${orderActions(o)}
        ${o.status==='待收货'||o.status==='待发货'||o.status==='待采购'?'<button class="btn ghost sm" onclick="event.stopPropagation();requestRefund(\''+o.id+'\')">模拟退款</button>':''}
        <button class="btn ghost sm" onclick="event.stopPropagation()">详情</button>
      </div>
    </div>`).join('')}`;
}

// ===== 页面：订单详情 =====
function renderOrderDetail(id) {
  const o = APP.orders.find(x => x.id === id);
  if (!o) return '<div class="empty">订单不存在</div>';
  const pur = APP.purchases.find(x => x.id === o.purchaseId) || {};
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">订单详情</div><div></div></div>
  <div class="card">
    <div class="row" style="justify-content:space-between"><b>${o.title}</b><span class="tag ${ST_CLS[o.status]||''}">${o.status}</span></div>
    <div class="gap"></div>
    <div class="row">
      <img src="${imgOf(o.productId)}" style="width:80px;height:80px;border-radius:8px;object-fit:cover" onerror="this.src='${PRODUCTS[0].image}';this.onerror=null">
      <div class="inf" style="flex:1">
        <h5 style="margin:0 0 4px">${o.title}</h5>
        <p style="margin:0;color:#888;font-size:12.5px">${o.spec}</p>
        <p style="margin:4px 0 0;color:#ff5000;font-weight:600">¥${o.price.toFixed(1)}</p>
      </div>
    </div>
  </div>
  ${pur.trackingNo ? `<div class="card"><b style="font-size:14px">🚚 物流单号</b><div class="gap"></div>
    <div class="kv" style="padding:8px 0;border:0"><span>承运</span><span>${pur.trackingNo.slice(0,2)}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>运单号</span><span style="color:var(--p)">${pur.trackingNo}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>状态</span><span>${pur.status}</span></div></div>` : ''}
  <div class="card">
    <b style="font-size:14px">👤 买家信息(代发收货人)</b>
    <div class="gap"></div>
    <div class="kv" style="padding:8px 0;border:0"><span>姓名</span><span>${o.buyer}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>地址</span><span>${o.addr}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>下单</span><span>${o.createdAt}</span></div>
  </div>
  <div class="card">
    <b style="font-size:14px">💰 利润分析</b>
    <div class="gap"></div>
    <div class="kv" style="padding:8px 0;border:0"><span>售价</span><span style="color:#ff5000">¥${o.price.toFixed(1)}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>代发成本</span><span>-¥${o.cost.toFixed(1)}</span></div>
    <div class="kv" style="padding:8px 0;border:0"><span>包邮成本</span><span>-¥2.0</span></div>
    <div class="kv" style="padding:8px 0;border:0;border-top:1px dashed #f0f1f3"><b>预估利润</b><b style="color:var(--ok)">¥${o.profit.toFixed(1)}</b></div>
  </div>
  <div class="btn-row">
    ${orderActions(o) || '<button class="btn ghost" onclick="goBack()">返回</button>'}
    ${o.status==='待收货'||o.status==='待发货'||o.status==='待采购'?'<button class="btn ghost" onclick="requestRefund(\''+o.id+'\')">模拟退款</button>':''}
    <button class="btn ${o.status==='退款中'?'warn':'p'} block" style="flex:2" onclick="copyBuyer('${o.id}')">📋 复制买家地址</button>
  </div>`;
}
function copyBuyer(id) {
  const o = APP.orders.find(x => x.id === id);
  if (o) { try { navigator.clipboard.writeText(o.buyer+' '+o.addr); } catch(e){} alert('已复制：'+o.buyer+' '+o.addr); }
}

// ===== 页面：批量支付(一键采购全部待采购) =====
function renderBatchPay() {
  const wait = APP.orders.filter(o => o.status === '待采购');
  const total = wait.reduce((a,o)=>a+o.cost,0);
  const profit = wait.reduce((a,o)=>a+o.profit,0);
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">批量采购</div><div></div></div>
  <div class="card" style="text-align:center;background:linear-gradient(135deg,#fff7f0,#fff)">
    <span style="color:#888;font-size:12px">待采购订单 (${wait.length})</span>
    <div style="margin-top:4px"><b style="font-size:28px;color:#ff5000">¥${total.toFixed(2)}</b></div>
    <span class="tag g" style="margin-top:4px">预估总利润 ¥${profit.toFixed(1)}</span>
  </div>
  ${wait.length === 0 ? '<div class="empty" style="text-align:center;padding:40px;color:#999">没有待采购订单 🎉</div>' : ''}
  ${wait.map(o => `
    <div class="order">
      <div class="row">
        <img src="${imgOf(o.productId)}" onerror="this.src='${PRODUCTS[0].image}';this.onerror=null">
        <div class="inf">
          <h5>${o.title}</h5>
          <p>${o.buyer} · ${o.addr}</p>
        </div>
        <div class="pr"><b>¥${o.cost.toFixed(1)}</b></div>
      </div>
    </div>`).join('')}
  <div class="card">
    <b style="font-size:14px">📍 批量说明</b>
    <div class="gap"></div>
    <p style="font-size:12.5px;color:#666;line-height:1.8">点击「批量采购」将逐笔向 1688 厂商代付货款并生成代发订单，订单自动转为「待发货」，再到各订单点「一键发货」回填物流。</p>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">返回</button>
    <button class="btn p block" style="flex:2" ${wait.length?'':'disabled'} onclick="batchPurchase()">批量采购 ¥${total.toFixed(2)}</button>
  </div>`;
}
async function batchPurchase() {
  for (const o of APP.orders.filter(x => x.status === '待采购')) {
    await apiPost('./api/orders/' + o.id + '/purchase', {});
  }
  await loadState();
  alert('批量采购完成，已生成 1688 代发订单');
}

// ===== 页面：自动售后 =====
function renderAfterSales() {
  const refunding = APP.orders.filter(o => o.status === '退款中');
  const refunded = APP.orders.filter(o => o.status === '已退款');
  const refundAmt = refunding.concat(refunded).reduce((a,o)=>a+o.price,0);
  const a = APP.aftersales;
  const sw = (k, on) => `<div class="sw ${on?'on':''}" onclick="APP.aftersales['${k}']=${!on};this.classList.toggle('on');saveAftersales()"></div>`;
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">自动售后</div><div></div></div>
  <div class="notice">系统已开启智能自动售后，收到买家售后申请后<b>自动向 1688 厂商同步</b>(1688 厂商同意后，自动向买家同步同意)。请开启小店铺获赔通知以免漏单。</div>
  <div class="kv"><div class="l"><span>🔕</span>手动售后<div class="tip">支持同时选择多家 1688 订单，去向供应商申请售后</div></div>${sw('manual', a.manual)}</div>
  <div class="kv"><div class="l"><span>🔔</span>极速退款<div class="tip">开启极速退款的商家建议开启该方式；系统自动向 1688 厂商申请售后，退货地址自动同步买家</div></div>${sw('fast', a.fast)}</div>
  <div class="kv"><div class="l"><span>⚙️</span>自动售后<div class="tip">退款/退货申请、退货地址、退货单号自动同步厂家</div></div>${sw('auto', a.auto)}</div>
  <div class="card">
    <b style="font-size:14px">支持的售后类型</b>
    <div class="gap"></div>
    <div style="font-size:13px;line-height:2">
      ✓ 仅退款 (无需退货)<br>
      ✓ 退货退款 (含运费)<br>
      ✓ 换货<br>
      ✓ 补发<br>
      ✓ 退运费
    </div>
  </div>
  <div class="card">
    <b style="font-size:14px">📊 售后统计(实时)</b>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">待处理(退款中)</span><b style="color:var(--warn)">${refunding.length} 单</b></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">已退款</span><b style="color:#888">${refunded.length} 单</b></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">退款金额</span><b>¥${refundAmt.toFixed(1)}</b></div>
  </div>
  ${refunding.length ? `<div class="card"><b style="font-size:14px">⚡ 待处理</b><div class="gap"></div>
    ${refunding.map(o=>`<div class="row" style="justify-content:space-between"><span style="font-size:13px">${o.title}</span>
      <button class="btn warn sm" onclick="oneClickAftersale('${o.id}')">一键售后</button></div><div class="gap"></div>`).join('')}</div>` : ''}`;
}

// ===== 页面：实时消息(SSE) =====
const MSG_COLOR = { order:'#ff5000', purchase:'#ff8a3d', logistics:'#0a8a3f', aftersale:'#ff4d4f', publish:'#7a3ad1', system:'#1677ff' };
function renderMessages() {
  // 进入即标记已读(本地)
  APP.messages.forEach(m => m.read = true);
  const list = APP.messages.slice().reverse();
  return `
  <div class="nav"><div></div><div class="title">实时消息</div><div class="more" onclick="alert('实时推送：订单/采购/物流/售后事件会经 SSE 秒推到本页')">📡</div></div>
  ${list.length === 0 ? '<div class="empty" style="text-align:center;padding:50px;color:#999">暂无消息，铺货/接单后这里会实时弹出</div>' : ''}
  ${list.map(m => {
    const c = MSG_COLOR[m.type] || '#888';
    return `<div class="li">
      <div style="width:40px;height:40px;border-radius:50%;background:${c}22;color:${c};display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">${MSG_ICON[m.type]||'🔔'}</div>
      <div class="ti"><h4>${m.title}</h4><p>${m.desc}</p></div>
      <div class="ri" style="flex-direction:column;align-items:flex-end;gap:4px">
        <span class="tag">${m.type}</span><span>${timeAgo(m.ts)}</span>
      </div>
    </div>`;
  }).join('')}
  `;
}
const MSG_ICON = { order:'🛒', purchase:'🛍️', logistics:'📤', aftersale:'🛡️', publish:'🚀', system:'🔔' };

// ===== 页面：我的 =====
function renderMe() {
  const sess = getSession();
  const accName = (sess && sess.account) ? sess.account : '未登录';
  const exp = sessionExpText();
  return `
  <div class="hero" style="border-radius:0">
    <div class="row" style="gap:12px">
      <div style="width:56px;height:56px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:28px">👤</div>
      <div>
        <h1 style="margin:0">${accName}</h1>
        <p style="margin:4px 0 0">${sess ? ('密钥有效期至 ' + exp) : '请先登录'}</p>
      </div>
    </div>
  </div>
  ${sess ? `
  <div class="card" style="margin-top:10px">
    <b style="font-size:14px">🔐 登录信息</b>
    <div class="gap"></div>
    <div class="kv" style="padding:8px 0;border:0"><span>账号</span><b>${accName}</b></div>
    <div class="kv" style="padding:8px 0;border:0"><span>密钥有效期</span><b style="color:var(--ok)">${exp}</b></div>
    <div class="kv" style="padding:8px 0;border:0"><span>种子指纹</span><b style="font-family:monospace">${KeyLib.fingerprint(getSeed())}</b></div>
    <div class="btn-row" style="padding:8px 0 0">
      <button class="btn ghost" onclick="openMakerBind()">制造者设置</button>
      <button class="btn p block" style="flex:2" onclick="logout()">退出登录</button>
    </div>
  </div>` : `
  <div class="card" style="margin-top:10px;text-align:center">
    <p style="color:#888;margin:6px 0">当前未登录，部分功能不可用</p>
    <button class="btn p block" onclick="logout()">重新登录</button>
  </div>`}
  <div class="grid6" style="grid-template-columns:repeat(4,1fr)">
    <div class="g" onclick="nav('orders')"><div class="ic">📦</div><div class="tt">${APP.orders.filter(o=>o.status==='待发货'||o.status==='待采购').length}</div><div class="bd">待处理</div></div>
    <div class="g" onclick="nav('publish')"><div class="ic">🚀</div><div class="tt">${listedIds().size}</div><div class="bd">已铺货</div></div>
    <div class="g" onclick="nav('messages')"><div class="ic">💬</div><div class="tt">${unreadMsgs()}</div><div class="bd">消息</div></div>
    <div class="g" onclick="alert('查看钱包')"><div class="ic">💰</div><div class="tt">¥${APP.orders.reduce((a,o)=>a+o.profit,0).toFixed(0)}</div><div class="bd">预估收益</div></div>
  </div>
  <div class="h-tt"><b>⚙️ 设置</b></div>
  <div class="li" onclick="nav('merchant')"><span>🤝</span><div class="ti"><h4>分销中心</h4><p>商家入驻 / 分销员招募 / 团队管理</p></div><div class="ri">›</div></div>
  <div class="li" onclick="nav('after-sales')"><span>🛡️</span><div class="ti"><h4>自动售后</h4><p>智能处理退款/退货</p></div><div class="ri">›</div></div>
  <div class="li" onclick="nav('messages')"><span>💬</span><div class="ti"><h4>消息中心</h4><p>订单/售后/系统通知</p></div><div class="ri">4 条未读 ›</div></div>
  <div class="li" onclick="nav('pricing')"><span>👑</span><div class="ti"><h4>我的服务</h4><p>出单宝版 · 到期 2026-09-12</p></div><div class="ri">续费 ›</div></div>
  <div class="li" onclick="nav('settings')"><span>🔗</span><div class="ti"><h4>后端设置</h4><p>连接实时后端 / 公网同步</p></div><div class="ri">›</div></div>
  <div class="li" onclick="openMakerBind()"><span>🧬</span><div class="ti"><h4>制造者设置</h4><p>导入灵钥绑定码 / 关联签名种子</p></div><div class="ri">›</div></div>
  <div class="li" onclick="alert('帮助中心')"><span>❓</span><div class="ti"><h4>帮助中心</h4><p>新手教程/常见问题</p></div><div class="ri">›</div></div>
  <div class="li" onclick="alert('联系客服')"><span>💬</span><div class="ti"><h4>在线客服</h4><p>9:00-22:00</p></div><div class="ri">›</div></div>
  `;
}

// ===== 页面：后端设置（公网实时后端地址）=====
function renderSettings() {
  const base = API.base();
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">后端设置</div><div></div></div>
  <div class="card" style="margin-top:10px">
    <b style="font-size:14px">🔗 实时后端地址</b>
    <div class="gap"></div>
    <p style="font-size:12.5px;color:#666;line-height:1.7;margin:0">公网版App可连接你自托管的实时后端：商品每日自动更新、消息 SSE 实时推送，<b>无需重部署即可刷新</b>。留空表示使用同源后端（本机 server.py 或部署时自带后端）。</p>
    <div class="gap"></div>
    <div class="field"><label>后端 URL（含 http(s)://，不含末尾 /）</label>
      <input id="apibase" placeholder="如 https://lingyu-backend.onrender.com" value="${base.replace(/"/g,'&quot;')}"></div>
    <div class="row" style="gap:8px;margin-top:8px">
      <button class="btn p block" style="flex:2" onclick="saveApiBase()">保存并重连</button>
      <button class="btn ghost" onclick="resetApiBase()">恢复同源</button>
    </div>
  </div>
  <div class="notice">💡 后端部署：把本目录 server.py 部署到 Render / PythonAnywhere / Railway 等 Python 主机，把得到的地址填到上方即可。详见 DEPLOY.md。</div>
  `;
}
async function saveApiBase() {
  const v = (($('#apibase') && $('#apibase').value) || '').trim().replace(/\/+$/, '');
  localStorage.setItem('lingyu_api_base', v);
  if (v) { try { await apiGet('./api/health'); } catch (e) { alert('连不上该后端，请检查地址 / 部署状态'); return; } }
  alert('已保存，正在重连后端…');
  await loadProducts(false); await loadState(); reconnectStream();
  nav('me');
}
function resetApiBase() {
  localStorage.removeItem('lingyu_api_base');
  if ($('#apibase')) $('#apibase').value = '';
  alert('已恢复同源，正在重连…');
  loadProducts(false); loadState(); reconnectStream();
}

// ===== 页面：分销中心（商家入驻 + 分销员招募） =====
function renderMerchant() {
  const m = MERCHANT;
  const roleTag = m.role === 'supply' ? '货源商家' : m.role === 'sell' ? '分销商家' : '未入驻';
  const statusTag = { none:'未入驻', reviewing:'审核中', passed:'已通过', rejected:'未通过' }[m.status];
  const statusColor = { none:'#bbb', reviewing:'#ff9800', passed:'var(--ok)', rejected:'#ff4d4f' }[m.status];
  const cta = m.status === 'none' ? 'merchant-join' : 'merchant-status';
  const ctaLabel = m.status === 'none' ? '立即入驻' : (m.status === 'reviewing' ? '查看进度' : '已入驻');
  return `
  <div class="nav"><div></div><div class="title">分销中心</div><div></div></div>
  <div class="module-hero">
    <h1>🤝 分销中心</h1>
    <p>供货 · 铺货 · 团队裂变，一站式经营</p>
    <div class="m-stats">
      <div class="m"><b>${m.teamSize}</b><span>团队成员</span></div>
      <div class="m"><b>¥${m.teamSales.toLocaleString()}</b><span>团队出单额</span></div>
      <div class="m"><b>¥${m.teamCommission.toFixed(0)}</b><span>佣金分成</span></div>
    </div>
  </div>
  <div class="card" style="margin-top:10px">
    <div class="row" style="justify-content:space-between;align-items:center">
      <div><b style="font-size:14px">我的身份</b>
        <div style="margin-top:4px"><span class="tag p">${roleTag}</span>
        <span class="tag" style="color:${statusColor};background:${statusColor}22">${statusTag}</span></div>
      </div>
      <button class="btn ${m.status==='none'?'p':'ghost'} sm" onclick="nav('${cta}')">${ctaLabel}</button>
    </div>
  </div>

  <div class="dual">
    <div class="d supply" onclick="nav('merchant-join')">
      <div class="em">🏭</div><h3>商家入驻</h3>
      <p>供货商 / 分销商家 快速入驻，开通铺货与结算</p>
      <span class="go">去入驻 ›</span>
    </div>
    <div class="d dist" onclick="nav('distributor')">
      <div class="em">📣</div><h3>分销员招募</h3>
      <p>生成专属邀请，下级出单你拿佣金分成</p>
      <span class="go">去招募 ›</span>
    </div>
  </div>

  <div class="h-tt"><b>团队数据</b><a onclick="nav('distributor-list')" style="color:var(--p)">下级列表 ›</a></div>
  <div class="card">
    <div class="row" style="justify-content:space-between"><span style="color:#888">下级分销员</span><b>${DISTRIBUTORS.length} 人</b></div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">累计出单</span><b style="color:var(--p)">${INVITE.totalOrders} 单</b></div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">累计销售额</span><b>¥${INVITE.totalSales.toLocaleString()}</b></div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">累计佣金</span><b style="color:var(--ok)">¥${INVITE.totalCommission.toFixed(1)}</b></div>
  </div>`;
}

// ===== 页面：商家入驻表单 =====
function renderMerchantJoin() {
  const role = state.merchantRole || 'sell';
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">商家入驻</div><div></div></div>
  <div class="seg">
    <button class="${role==='sell'?'on':''}" onclick="state.merchantRole='sell';render()">分销商家(铺货卖货)</button>
    <button class="${role==='supply'?'on':''}" onclick="state.merchantRole='supply';render()">货源商家(供货)</button>
  </div>
  <div class="notice">${role==='sell'?'作为分销商家，你可一件代发平台货源、自动结算收益':'作为货源商家，你提供商品与供货价，由分销网络帮你卖货'}</div>
  <div class="form">
    <div class="field"><label>店铺 / 主体名称 <span class="req">*</span></label>
      <input id="m-name" placeholder="${role==='sell'?'如：闲鱼-二次元铺':'如：广州某手办工厂店'}"></div>
    <div class="field"><label>联系人手机号 <span class="req">*</span></label>
      <input id="m-phone" placeholder="用于接收审核与结算通知" value="137****8442"></div>
    ${role==='sell'?`
    <div class="field"><label>绑定销售渠道 <span class="req">*</span></label>
      <select id="m-channel"><option>闲鱼</option><option>微店</option><option>有赞</option><option>微信小商店</option><option>淘宝</option></select></div>
    `:`
    <div class="field"><label>主营类目 <span class="req">*</span></label>
      <select id="m-cat"><option>动漫手办 / 周边</option><option>服饰 / 鞋包</option><option>美妆个护</option><option>数码配件</option><option>家居百货</option></select></div>
    <div class="field"><label>供货价区间 <span class="req">*</span></label>
      <input id="m-price" placeholder="如：¥1 - ¥50"></div>
    `}
    <div class="field"><label>资质上传 <span class="req">*</span></label>
      <div class="hint">${role==='sell'?'上传实人认证截图 / 店铺后台页':'营业执照 + 法人身份证（脱敏）'}</div>
      <div class="upload">
        <div class="u" onclick="this.classList.add('done')"><div class="plus">+</div>营业执照</div>
        <div class="u" onclick="this.classList.add('done')"><div class="plus">+</div>身份证</div>
        <div class="u" onclick="this.classList.add('done')"><div class="plus">+</div>店铺页</div>
      </div>
    </div>
    <div class="field"><label>邀请码(选填)</label>
      <input id="m-invite" placeholder="有上级邀请码可填，享专属扶持"></div>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">取消</button>
    <button class="btn p block" style="flex:2" onclick="submitMerchant('${role}')">提交入驻申请</button>
  </div>`;
}

function submitMerchant(role) {
  const el = $('#m-name');
  const name = (el && el.value.trim()) || (role==='sell' ? '闲鱼-二次元铺' : '供货商家');
  MERCHANT.role = role;
  MERCHANT.status = 'reviewing';
  MERCHANT.name = name;
  MERCHANT.joinedAt = new Date().toISOString().slice(0,10);
  nav('merchant-status');
}

// ===== 页面：入驻进度 =====
function renderMerchantStatus() {
  const m = MERCHANT;
  const s1 = m.status === 'none' ? 'on' : 'done';
  const s2 = m.status === 'reviewing' ? 'on' : (m.status === 'passed' ? 'done' : '');
  const s3 = m.status === 'passed' ? 'done' : '';
  const title = m.status === 'passed' ? '入驻成功' : m.status === 'rejected' ? '未通过' : m.status === 'reviewing' ? '审核中' : '提交入驻';
  const desc = m.status === 'passed' ? '恭喜，已开通铺货与结算权限' : m.status === 'reviewing' ? '预计 1-3 个工作日完成审核' : m.status === 'rejected' ? '请完善资料后重新提交' : '请先提交入驻申请';
  const emoji = m.status === 'passed' ? '🎉' : m.status === 'rejected' ? '😢' : '⏳';
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">入驻进度</div><div></div></div>
  ${m.status==='rejected' ? `<div class="notice">很遗憾，入驻未通过。常见原因：资质不清晰 / 类目不符。可修改后重新提交。</div>` : ''}
  <div class="card" style="margin-top:10px;text-align:center">
    <div style="font-size:40px">${emoji}</div>
    <h2 style="margin:10px 0 4px">${title}</h2>
    <p style="color:#888;font-size:13px;margin:0">${desc}</p>
  </div>
  <div class="steps">
    <div class="s ${s1}"><div class="dot">${s1==='done'?'✓':'1'}</div><div class="lb">提交资料</div></div>
    <div class="s ${s2}"><div class="dot">${s2==='done'?'✓':'2'}</div><div class="lb">平台审核</div></div>
    <div class="s ${s3}"><div class="dot">${s3==='done'?'✓':'3'}</div><div class="lb">入驻成功</div></div>
  </div>
  ${m.status==='passed' ? `
  <div class="card">
    <div class="row" style="justify-content:space-between"><span style="color:#888">身份</span><b>${m.role==='supply'?'货源商家':'分销商家'}</b></div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">店铺</span><b>${m.name}</b></div>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">等级</span><b style="color:#7a3ad1">${m.level}</b></div>
  </div>
  <div class="btn-row"><button class="btn ghost" onclick="nav('merchant')">返回</button>
    <button class="btn p block" style="flex:2" onclick="nav('distributor')">去招募分销员</button></div>
  ` : `
  <div class="btn-row">
    <button class="btn ghost" onclick="goBack()">返回</button>
    ${(m.status==='none'||m.status==='rejected') ? '<button class="btn p block" style="flex:2" onclick="nav(\'merchant-join\')">去提交</button>' : ''}
  </div>`}
  `;
}

// ===== 页面：分销员招募主页 =====
function renderDistributor() {
  const iv = INVITE;
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">分销员招募</div><div></div></div>

  <div class="poster">
    <div class="pg">
      <h2>${iv.posterTitle}</h2>
      <p>${iv.posterSub}</p>
      <div class="row2">
        <div class="qr">扫码<br>加入</div>
        <div>
          <div style="font-size:12px;opacity:.9">团队长</div>
          <div style="font-size:15px;font-weight:700;margin-top:2px">卖家 137****8442</div>
          <div style="font-size:11px;opacity:.85;margin-top:4px">邀请码 ${iv.code}</div>
        </div>
      </div>
    </div>
    <div class="prod-row">
      <img class="pp" src="${imgUrl(PRODUCTS[0])}" onerror="this.src='${PRODUCTS[0].imageRemote}';this.onerror=null">
      <div class="pi"><b>${PRODUCTS[0].title}</b>
        <div class="pr">建议价 ¥${PRODUCTS[0].suggestPrice.toFixed(1)} · 你赚 ¥${PRODUCTS[0].profit.toFixed(1)}</div>
      </div>
    </div>
    <div class="foot">长按保存海报，分享到闲鱼 / 微信 / 社群</div>
  </div>

  <div class="invite-code">
    <div class="c">${iv.code}</div>
    <button onclick="alert('邀请码已复制：${iv.code}')">复制</button>
  </div>

  <div class="comm">
    <b style="font-size:14px">💸 佣金设置</b>
    <div class="crow">
      <div class="lab"><b>一级佣金</b><small>下级出单你拿分成</small></div>
      <div class="val">${iv.commission1}%</div>
      <button class="btn ghost sm" onclick="adjustComm('1',-1)">−</button>
      <button class="btn ghost sm" onclick="adjustComm('1',1)">＋</button>
    </div>
    <div class="bar"><i style="width:${Math.min(iv.commission1*5,100)}%"></i></div>
    <div class="crow">
      <div class="lab"><b>二级佣金</b><small>下下级出单分成</small></div>
      <div class="val">${iv.commission2}%</div>
      <button class="btn ghost sm" onclick="adjustComm('2',-1)">−</button>
      <button class="btn ghost sm" onclick="adjustComm('2',1)">＋</button>
    </div>
    <div class="bar"><i style="width:${Math.min(iv.commission2*8,100)}%"></i></div>
    <div class="hint" style="color:#999;font-size:11px;margin-top:8px">佣金按下级实际支付金额结算，出单后 T+1 自动到账</div>
  </div>

  <div class="card" style="text-align:center;background:linear-gradient(135deg,#fff7f0,#fff)">
    <div style="font-size:12px;color:#888">我的团队</div>
    <div style="display:flex;justify-content:space-around;margin-top:8px">
      <div><b style="font-size:20px;color:var(--p)">${iv.totalInvited}</b><br><span style="font-size:11px;color:#999">邀请人数</span></div>
      <div><b style="font-size:20px">${iv.totalOrders}</b><br><span style="font-size:11px;color:#999">出单量</span></div>
      <div><b style="font-size:20px;color:var(--ok)">¥${iv.totalCommission.toFixed(0)}</b><br><span style="font-size:11px;color:#999">佣金</span></div>
    </div>
    <div class="gap"></div>
    <button class="btn p block" onclick="nav('distributor-list')">查看下级分销员</button>
  </div>`;
}

function adjustComm(level, d) {
  if (level === '1') INVITE.commission1 = Math.max(0, Math.min(30, INVITE.commission1 + d));
  else INVITE.commission2 = Math.max(0, Math.min(20, INVITE.commission2 + d));
  render();
}

// ===== 页面：下级分销员列表 =====
function renderDistributorList() {
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">下级分销员</div>
    <div class="more" onclick="nav('distributor')">邀请</div></div>
  <div class="pft-card">
    <div style="font-size:12px;color:#888">累计佣金(可提现)</div>
    <div class="big">¥${INVITE.totalCommission.toFixed(1)}</div>
    <button class="btn p sm" style="margin-top:6px" onclick="alert('演示：提现申请已提交')">申请提现</button>
  </div>
  ${DISTRIBUTORS.map(d => `
    <div class="dist" onclick="nav('distributor-detail',{id:'${d.id}'})">
      <div class="top">
        <div class="av">${d.avatar}</div>
        <div class="nm"><b>${d.name}</b><span class="lv">${d.level}</span>
          <small>加入 ${d.joinedAt} · 最近出单 ${d.lastOrder}</small></div>
        ${d.status==='pending' ? '<span class="pend">待激活</span>' : '<span class="st">活跃</span>'}
      </div>
      <div class="mtr">
        <div class="m"><b>${d.invited}</b><span>邀请</span></div>
        <div class="m"><b>${d.orders}</b><span>出单</span></div>
        <div class="m"><b>¥${d.sales}</b><span>销售额</span></div>
        <div class="m"><b style="color:var(--ok)">¥${d.commission}</b><span>佣金</span></div>
      </div>
    </div>`).join('')}
  `;
}

// ===== 页面：分销员详情 =====
function renderDistributorDetail(id) {
  const d = DISTRIBUTORS.find(x => x.id === id);
  if (!d) return '<div class="empty">分销员不存在</div>';
  return `
  <div class="nav"><button class="back" onclick="goBack()">‹</button><div class="title">分销员详情</div><div></div></div>
  <div class="card" style="text-align:center;margin-top:10px">
    <div style="width:64px;height:64px;border-radius:50%;background:#f3f0ff;margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:34px">${d.avatar}</div>
    <h2 style="margin:10px 0 4px">${d.name} <span class="tag" style="color:#7a3ad1;background:#f3f0ff;font-size:11px">${d.level}</span></h2>
    <p style="color:#888;font-size:12.5px;margin:0">${d.status==='pending'?'待激活':'活跃'} · 加入 ${d.joinedAt}</p>
  </div>
  <div class="card">
    <div class="mtr" style="border-top:0;padding-top:0">
      <div class="m"><b style="color:var(--p)">${d.invited}</b><span>邀请人数</span></div>
      <div class="m"><b>${d.orders}</b><span>出单量</span></div>
      <div class="m"><b>¥${d.sales}</b><span>销售额</span></div>
      <div class="m"><b style="color:var(--ok)">¥${d.commission}</b><span>已结佣金</span></div>
    </div>
  </div>
  <div class="card">
    <b style="font-size:14px">📈 近 7 日出单</b>
    <div class="gap"></div>
    <div style="display:flex;align-items:flex-end;gap:6px;height:90px;padding:0 4px">
      ${[3,5,2,7,4,6,5].map(v => `<div style="flex:1;background:linear-gradient(180deg,#ff8a3d,#ff5000);border-radius:4px 4px 0 0;height:${v*12}px" title="${v}单"></div>`).join('')}
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:#bbb;margin-top:4px">
      <span>8/6</span><span>8/7</span><span>8/8</span><span>8/9</span><span>8/10</span><span>8/11</span><span>8/12</span>
    </div>
  </div>
  <div class="card">
    <b style="font-size:14px">💰 佣金结算</b>
    <div class="gap"></div>
    <div class="kv" style="padding:8px 0;border:0"><span>累计佣金</span><b style="color:var(--ok)">¥${d.commission}</b></div>
    <div class="kv" style="padding:8px 0;border:0"><span>佣金比例</span><b>一级 ${INVITE.commission1}%</b></div>
    <div class="kv" style="padding:8px 0;border:0"><span>结算状态</span><b style="color:var(--ok)">T+1 自动到账</b></div>
  </div>
  <div class="btn-row">
    <button class="btn ghost" onclick="alert('已发送消息')">发消息</button>
    <button class="btn p block" style="flex:2" onclick="alert('演示：已发送专属推广物料')">下发推广物料</button>
  </div>`;
}

// ===== 密钥登录 / 会话 =====
function getSeed() { return localStorage.getItem('lingyu_seed') || KeyLib.DEFAULT_SEED; }
function getSession() {
  try {
    const s = JSON.parse(localStorage.getItem('lingyu_session') || 'null');
    if (s && s.expiresAt && new Date(s.expiresAt).getTime() > Date.now()) return s;
  } catch (e) {}
  return null;
}
function sessionExpText() {
  const s = getSession();
  if (!s) return '';
  const d = new Date(s.expiresAt);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
async function doLogin() {
  const acc = (($('#lg-acc') && $('#lg-acc').value) || '').trim();
  const key = (($('#lg-key') && $('#lg-key').value) || '').trim();
  if (!acc || !key) { toast('请输入账号和密钥'); return; }
  const r = await KeyLib.verify(key, acc, getSeed());
  if (!r.ok) {
    const msg = {
      len: '密钥长度须为 32 位', chars: '密钥含非法字符', checksum: '密钥校验失败',
      mac: '密钥与账号不匹配', expired: '密钥已过期，请联系制造者重新签发', expiry: '密钥格式错误'
    }[r.reason] || '密钥无效';
    toast(msg); return;
  }
  // 已配置后端 → 用后端做集中校验（支持吊销/集中管控）
  const base = API.base();
  if (base) {
    try {
      const bv = await API.post('/api/keys/verify', { account: acc, key, seed: getSeed() });
      if (bv && bv.ok === false && bv.reason === 'revoked') {
        toast('该密钥已被制造者吊销，请联系制造者'); return;
      }
      if (bv && bv.ok) {
        // 登录即登记到后端，便于后续可被制造者统一吊销
        API.post('/api/keys/register', { account: acc, key, seed: getSeed() }).catch(() => {});
      }
    } catch (e) { /* 后端不可达，离线放行 */ }
  }
  localStorage.setItem('lingyu_session', JSON.stringify({ account: acc, expiresAt: r.expiresAt, loginAt: Date.now() }));
  const lg = $('#login'); if (lg) lg.classList.add('hidden');
  toast('登录成功');
  startApp();
}
function startApp() {
  nav('home');
  loadProducts(false);   // 联网拉取当天最新 10 款(失败回退打包快照)
  loadState();           // 拉取业务状态(铺货/订单/消息/售后)
  connectStream();       // 连接 SSE 实时消息推送
}
function logout() {
  localStorage.removeItem('lingyu_session');
  location.reload();
}

// 制造者设置：导入灵钥导出的绑定码 → 与灵钥同一签名种子（相互关联）
function openMakerBind() {
  sheet(`
    <div class="hd-h">⚙️ 制造者设置</div>
    <p class="hd-p">将「灵钥」密钥生成器导出的<b>绑定码</b>粘贴到下方，导入后本软件即与灵钥使用同一签名种子，可校验灵钥生成的密钥（两软件相互关联）。</p>
    <div class="field"><label>绑定码</label><input id="bindcode" placeholder="粘贴灵钥导出的绑定码"></div>
    <button class="btn p block" onclick="importBind()">导入绑定码</button>
    <div class="gap"></div>
    <p style="font-size:12px;color:#888">当前种子指纹：<b style="font-family:monospace">${KeyLib.fingerprint(getSeed())}</b></p>
    <button class="btn ghost block" onclick="closeSheet()">关闭</button>
  `);
}
async function importBind() {
  const code = (($('#bindcode') && $('#bindcode').value) || '').trim();
  const seed = KeyLib.decodeBind(code);
  if (!seed) { toast('绑定码无效'); return; }
  localStorage.setItem('lingyu_seed', seed);
  closeSheet();
  toast('已关联灵钥，指纹：' + KeyLib.fingerprint(seed));
}

// ===== 入口 =====
function boot() {
  const s = getSession();
  if (s) { const lg = $('#login'); if (lg) lg.classList.add('hidden'); startApp(); }
  // 否则保持登录遮罩可见（默认显示）
}
function bindRouteLinks() {
  $$('#tab .t').forEach(t => t.onclick = () => nav(t.dataset.route));
}
function publishSelected() {
  if (state.selectedProducts.length === 0) { alert('请先选择要铺货的商品'); return; }
  nav('publish-shops');
}

window.addEventListener('hashchange', () => {
  const h = location.hash.slice(1) || 'home';
  if (h !== state.route) nav(h);
});

boot();
