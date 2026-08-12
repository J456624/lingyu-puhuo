// ===== 灵钥·密钥生成器（制造者专属）=====
// 仅软件制造者可进入；生成 32 位「数字+特殊字符」密钥，可设有效期。
// 与主软件(灵鱼)通过共享 seed 关联：导出的"绑定码"导入灵鱼后即相互关联。
const $ = (s, p = document) => p.querySelector(s);
const $$ = (s, p = document) => [...p.querySelectorAll(s)];
const LS = {
  hash: 'lingyao_maker_hash',
  seed: 'lingyao_seed',
  hist: 'lingyao_history'
};
const state = { route: 'gen', days: 182, custom: '', last: null };

function getSeed() { return localStorage.getItem(LS.seed) || KeyLib.DEFAULT_SEED; }
function fingerprint() { return KeyLib.fingerprint(getSeed()); }
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return (h >>> 0).toString(16); }
function getHist() { try { return JSON.parse(localStorage.getItem(LS.hist) || '[]'); } catch (e) { return []; } }
function saveHist(h) { localStorage.setItem(LS.hist, JSON.stringify(h.slice(0, 200))); }

// ===== 制造者门禁 =====
function makerGate(mode) {
  const isSetup = mode === 'setup';
  $('#view').innerHTML = `
  <div class="gate">
    <div class="g-logo">🔐</div>
    <h1>灵钥 · 密钥生成器</h1>
    <p class="g-sub">${isSetup ? '首次使用，请设置制造者口令（仅你本人可生成密钥）' : '请输入制造者口令以进入'}</p>
    <div class="field"><input id="mk" type="password" placeholder="制造者口令" autocomplete="off"></div>
    ${isSetup ? `<div class="field"><input id="mk2" type="password" placeholder="再次确认口令" autocomplete="off"></div>` : ''}
    <button class="btn p block" onclick="submitGate('${mode}')">${isSetup ? '设置并进入' : '进入'}</button>
    <p class="g-tip">⚠️ 此软件仅服务于软件制造者（你）。忘记口令需清除本应用数据后重置。</p>
  </div>`;
  setTimeout(() => { const e = $('#mk'); if (e) e.focus(); }, 50);
}
function submitGate(mode) {
  const v = ($('#mk') && $('#mk').value) || '';
  if (mode === 'setup') {
    const v2 = ($('#mk2') && $('#mk2').value) || '';
    if (v.length < 4) { toast('口令至少 4 位'); return; }
    if (v !== v2) { toast('两次输入不一致'); return; }
    localStorage.setItem(LS.hash, hashStr(v));
    toast('已设置，进入中…');
  } else {
    if (hashStr(v) !== localStorage.getItem(LS.hash)) { toast('口令错误'); return; }
  }
  enterApp();
}
function enterApp() {
  $('#fp').textContent = 'FP:' + fingerprint();
  bindNav();
  render();
}

// ===== 导航 / 渲染 =====
const nav = (route) => { state.route = route; $$('#tab .t').forEach(t => t.classList.toggle('on', t.dataset.route === route)); render(); window.scrollTo(0, 0); };
function bindNav() { $$('#tab .t').forEach(t => t.onclick = () => nav(t.dataset.route)); }
function render() {
  const v = $('#view');
  if (state.route === 'gen') v.innerHTML = renderGen();
  else if (state.route === 'history') v.innerHTML = renderHistory();
  else if (state.route === 'keymgr') v.innerHTML = renderKeyMgr();
  else if (state.route === 'maker') v.innerHTML = renderMaker();
}
const VAL_PRESETS = [['30', '1 个月'], ['90', '3 个月'], ['182', '半年'], ['365', '1 年'], ['730', '2 年']];
function renderGen() {
  const days = state.custom ? state.custom : state.days;
  return `
  <div class="nav"><div></div><div class="title">生成密钥</div><div></div></div>
  <div class="card" style="margin-top:10px">
    <b style="font-size:14px">① 绑定账号</b>
    <div class="gap"></div>
    <p style="font-size:12px;color:#666;margin:0 0 8px">填写该密钥对应的使用者账号（如分销员闲鱼号 / 手机号后 4 位），使用者登录灵鱼时需输入相同账号。</p>
    <div class="field"><input id="acc" placeholder="如：fenxiao_01 或 8442" autocomplete="off"></div>
  </div>
  <div class="card">
    <b style="font-size:14px">② 有效期限</b>
    <div class="gap"></div>
    <div class="chips" style="display:flex;gap:8px;flex-wrap:wrap">
      ${VAL_PRESETS.map(c => `<span class="chip ${String(state.days) === c[0] && !state.custom ? 'on' : ''}" onclick="state.custom='';state.days=${c[0]};render()">${c[1]}</span>`).join('')}
      <span class="chip ${state.custom ? 'on' : ''}" onclick="setCustom()">自定义</span>
    </div>
    ${state.custom ? `<div class="field" style="margin-top:10px"><input id="cday" type="number" placeholder="有效天数，如 120" value="${state.custom}"><div style="font-size:12px;color:#888;margin-top:4px">${state.custom} 天 ≈ ${(state.custom/30).toFixed(1)} 个月</div></div>` : `<div style="font-size:12px;color:#888;margin-top:6px">当前：${days} 天（≈ ${(days/30).toFixed(1)} 个月）</div>`}
  </div>
  <div class="btn-row" style="position:sticky;bottom:0;background:#fff;border-top:1px solid var(--bd)">
    <button class="btn p block" onclick="doGenerate()">🔑 生成密钥</button>
  </div>
  <p class="g-tip" style="padding:0 16px">密钥为 32 位「数字 + 特殊字符」，由本机 HMAC-SHA256 签名生成，离线可校验，他人无法伪造。</p>`;
}
function setCustom() {
  const v = prompt('输入有效天数（如 120）：', state.custom || '120');
  if (v == null) return;
  const n = parseInt(v, 10);
  if (!n || n < 1) { toast('天数无效'); return; }
  state.custom = String(n); state.days = n; render();
}
async function doGenerate() {
  const acc = ($('#acc') && $('#acc').value || '').trim();
  if (!acc) { toast('请填写绑定账号'); return; }
  const days = parseInt(state.custom || state.days, 10);
  const r = await KeyLib.generate(acc, days, getSeed());
  state.last = { account: acc, key: r.key, expiresAt: r.expiresAt, days: r.days, createdAt: new Date().toISOString() };
  const hist = getHist(); hist.unshift(state.last); saveHist(hist);
  showKeySheet(state.last);
}
function showKeySheet(d) {
  const exp = new Date(d.expiresAt);
  sheet(`
    <div class="hd-h">🔑 密钥已生成</div>
    <p class="hd-p">账号 <b>${d.account}</b> · 有效期至 <b>${exp.getFullYear()}-${String(exp.getMonth()+1).padStart(2,'0')}-${String(exp.getDate()).padStart(2,'0')}</b>（${d.days} 天）</p>
    <div class="keybox" onclick="copyKey('${d.key}')">${d.key}</div>
    <p class="hd-foot">点击密钥可复制，发给使用者后在灵鱼「密钥登录」中输入账号+此密钥即可。</p>
    <div class="hd-actions">
      <button class="btn p block" onclick="copyKey('${d.key}');toast('密钥已复制')">📋 复制密钥</button>
      <div class="gap"></div>
      <button class="btn ghost block" onclick="registerKeyBackend('${d.account}','${d.key}')">☁️ 登记到后端</button>
    </div>
    <div class="gap"></div>
    <button class="btn ghost block" onclick="closeSheet()">完成</button>`);
}
function copyKey(k) { try { navigator.clipboard.writeText(k); } catch (e) {} }
function copyText(t) { if (!t) return; try { navigator.clipboard.writeText(t); } catch (e) {} }

// ===== 登记到后端（供灵鱼登录时集中校验 / 可被吊销）=====
async function registerKeyBackend(account, key) {
  if (!API.base()) { toast('未配置后端地址（见「密钥管理」）'); return false; }
  try {
    const r = await API.post('/api/keys/register', { account, key, seed: getSeed() });
    if (r && r.ok) { toast('已登记到后端'); return true; }
    toast('登记失败: ' + (r && r.error || '未知错误'));
    return false;
  } catch (e) { toast('后端连接失败'); return false; }
}

// ===== 密钥管理（后端：吊销 / 查询）=====
function renderKeyMgr() {
  const base = localStorage.getItem('lingyu_api_base') || '';
  const admin = localStorage.getItem('lingyao_admin_key') || '';
  const adminAcc = localStorage.getItem('lingyao_admin_account') || 'maker';
  return `
  <div class="nav"><div></div><div class="title">密钥管理（后端）</div><div></div></div>
  <div class="card" style="margin-top:10px">
    <b style="font-size:14px">🔗 实时后端地址</b>
    <div class="gap"></div>
    <p style="font-size:12px;color:#666;margin:0 0 8px">填你部署的 server.py 公网地址（含 http(s)://，不含末尾 /）。留空则仅本地生成、不登记。</p>
    <div class="field"><input id="kg-base" placeholder="如 https://lingyu-backend.onrender.com" value="${base.replace(/"/g,'&quot;')}"></div>
    <button class="btn p block" onclick="saveKgBase()">保存后端地址</button>
  </div>
  <div class="card">
    <b style="font-size:14px">🔐 管理密钥（账号 maker）</b>
    <div class="gap"></div>
    <p style="font-size:12px;color:#666;margin:0 0 8px">用于登录后端执行吊销/查询。请用本工具生成一个 account=maker 的密钥保存于此。</p>
    <div class="keybox sm" onclick="copyText('${admin}')">${admin || '（未设置）'}</div>
    <div class="gap"></div>
    <button class="btn ghost block" onclick="genAdminKey()">生成管理密钥（2 年）</button>
  </div>
  <div class="card">
    <b style="font-size:14px">📋 已登记密钥</b>
    <div class="gap"></div>
    <button class="btn ghost block" onclick="fetchKeys()">拉取后端密钥列表</button>
    <div id="kg-list" style="margin-top:10px"></div>
  </div>`;
}
function saveKgBase() {
  const v = (($('#kg-base') && $('#kg-base').value) || '').trim().replace(/\/+$/, '');
  localStorage.setItem('lingyu_api_base', v);
  if (v) { toast('已保存后端地址'); } else { toast('已清空，仅本地模式'); }
}
async function genAdminKey() {
  const r = await KeyLib.generate('maker', 730, getSeed());
  localStorage.setItem('lingyao_admin_key', r.key);
  localStorage.setItem('lingyao_admin_account', 'maker');
  toast('管理密钥已生成并保存');
  render();
}
async function fetchKeys() {
  const base = API.base();
  const admin = localStorage.getItem('lingyao_admin_key') || '';
  const adminAcc = localStorage.getItem('lingyao_admin_account') || 'maker';
  const el = document.getElementById('kg-list');
  if (!base) { toast('请先保存后端地址'); return; }
  if (!admin) { toast('请先生成管理密钥'); return; }
  try {
    const d = await API.get('/api/keys?makerKey=' + encodeURIComponent(admin) + '&makerAccount=' + encodeURIComponent(adminAcc) + '&seed=' + encodeURIComponent(getSeed()));
    if (!d || !d.ok) { toast('查询失败: ' + (d && d.error || '')); return; }
    if (!d.keys.length) { el.innerHTML = '<p style="color:#999;font-size:12px">暂无登记记录（在「生成密钥」后点「登记到后端」）</p>'; return; }
    el.innerHTML = d.keys.map(k => {
      const revoked = k.status === 'revoked';
      const exp = k.expiresAt ? new Date(k.expiresAt).toLocaleDateString() : '—';
      return `<div class="li" style="align-items:center">
        <div class="ti"><h4>${k.account}</h4>
          <p style="font-family:monospace;font-size:11px;word-break:break-all">${k.key}</p>
          <p style="color:${revoked ? '#ff4d4f' : '#888'}">${revoked ? '已吊销' : ('有效至 ' + exp)}</p></div>
        <div class="ri">${revoked
          ? '<span class="tag" style="color:#ff4d4f">已吊销</span>'
          : `<button class="btn warn sm" onclick="revokeKey('${k.account}','${k.key}')">吊销</button>`}</div>
      </div>`;
    }).join('');
  } catch (e) { toast('后端连接失败'); }
}
async function revokeKey(account, key) {
  const base = API.base();
  const admin = localStorage.getItem('lingyao_admin_key') || '';
  if (!base || !admin) { toast('缺少后端或管理密钥'); return; }
  if (!confirm('确认吊销账号 ' + account + ' 的密钥？吊销后该账号将无法登录灵鱼。')) return;
  try {
    const r = await API.post('/api/keys/revoke', { account, key, authKey: admin, authAccount: 'maker', seed: getSeed() });
    if (r && r.ok) { toast('已吊销'); fetchKeys(); }
    else toast('吊销失败: ' + (r && r.error || ''));
  } catch (e) { toast('后端连接失败'); }
}

function renderHistory() {
  const h = getHist();
  return `
  <div class="nav"><div></div><div class="title">签发记录</div><div></div></div>
  ${h.length === 0 ? '<div class="empty" style="text-align:center;padding:50px;color:#999"><div style="font-size:42px">📜</div><p>还没有签发记录</p></div>' : ''}
  ${h.map((d, i) => {
    const exp = new Date(d.expiresAt);
    const expired = exp < new Date();
    return `<div class="li">
      <div style="width:40px;height:40px;border-radius:50%;background:#7a3ad122;color:#7a3ad1;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">🔑</div>
      <div class="ti">
        <h4>${d.account}</h4>
        <p style="font-family:monospace;font-size:12px;word-break:break-all">${d.key}</p>
        <p style="color:${expired ? '#ff4d4f' : '#888'}">${expired ? '已过期' : '有效至'} ${exp.getFullYear()}-${String(exp.getMonth()+1).padStart(2,'0')}-${String(exp.getDate()).padStart(2,'0')}</p>
      </div>
      <div class="ri"><button class="btn ghost sm" onclick="copyKey('${d.key}');toast('已复制')">复制</button></div>
    </div>`;
  }).join('')}`;
}

function renderMaker() {
  const seed = getSeed();
  const bind = KeyLib.encodeBind(seed);
  return `
  <div class="nav"><div></div><div class="title">制造者设置</div><div></div></div>
  <div class="card" style="margin-top:10px">
    <b style="font-size:14px">🔗 关联主软件（灵鱼）</b>
    <div class="gap"></div>
    <p style="font-size:12px;color:#666;line-height:1.7;margin:0">把下方「绑定码」复制到灵鱼 App 的 <b>我的 → 制造者设置</b> 中导入，两端即使用同一签名种子，灵鱼才能校验你生成的密钥（相互关联）。</p>
    <div class="keybox sm" onclick="copyBind()">${bind}</div>
    <button class="btn ghost block" style="margin-top:8px" onclick="copyBind();toast('绑定码已复制')">📋 复制绑定码</button>
  </div>
  <div class="card">
    <b style="font-size:14px">🧬 签名种子</b>
    <div class="gap"></div>
    <div class="row" style="justify-content:space-between"><span style="color:#888">种子指纹</span><b style="font-family:monospace">${fingerprint()}</b></div>
    <div class="gap"></div>
    <p style="font-size:12px;color:#888;margin:0 0 8px">改成私有种子可提升安全（灵鱼也须同步改）。保留默认种子则两软件出厂即互通。</p>
    <div class="field"><input id="seed" placeholder="输入新的私有种子" autocomplete="off"></div>
    <button class="btn p block" onclick="saveSeed()">保存种子并重算指纹</button>
  </div>
  <div class="card">
    <b style="font-size:14px">🔒 制造者口令</b>
    <div class="gap"></div>
    <button class="btn ghost block" onclick="changePass()">修改进入口令</button>
  </div>
  <p class="g-tip" style="padding:0 16px">本软件仅服务于软件制造者。密钥在本地用种子签名，不上传任何服务器。</p>`;
}
function copyBind() { try { navigator.clipboard.writeText(KeyLib.encodeBind(getSeed())); } catch (e) {} }
function saveSeed() {
  const v = ($('#seed') && $('#seed').value || '').trim();
  if (v.length < 6) { toast('种子至少 6 位'); return; }
  localStorage.setItem(LS.seed, v);
  $('#fp').textContent = 'FP:' + fingerprint();
  toast('已保存，指纹：' + fingerprint());
  render();
}
function changePass() {
  const old = prompt('输入当前口令：');
  if (old == null) return;
  if (hashStr(old) !== localStorage.getItem(LS.hash)) { toast('当前口令错误'); return; }
  const nv = prompt('输入新口令（至少 4 位）：');
  if (!nv || nv.length < 4) { toast('口令至少 4 位'); return; }
  const nv2 = prompt('再次输入新口令：');
  if (nv !== nv2) { toast('两次不一致'); return; }
  localStorage.setItem(LS.hash, hashStr(nv));
  toast('口令已修改');
}

// ===== 弹层 =====
function sheet(html) { $('#sheet').innerHTML = `<button class="close" onclick="closeSheet()">✕</button>${html}`; $('#mask').classList.add('on'); }
function closeSheet() { $('#mask').classList.remove('on'); }
$('#mask').addEventListener('click', e => { if (e.target.id === 'mask') closeSheet(); });

// ===== 入口 =====
function toast(msg) { let t = $('#toast'); if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); } t.textContent = msg; t.classList.add('on'); clearTimeout(t._tm); t._tm = setTimeout(() => t.classList.remove('on'), 1600); }
(function init() {
  if (!localStorage.getItem(LS.hash)) makerGate('setup');
  else makerGate('login');
})();
