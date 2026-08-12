// ===== 灵鱼 / 灵钥 通用密钥库 =====
// 密钥 = 32 位「数字(0-9) + 特殊字符(!@#$%^&*())」，HMAC-SHA256 签名，可离线校验。
// 结构: [4位有效期编码][26位签名][2位校验位]  —— 两软件共享同一 seed 即"相互关联"。
// 主软件(灵鱼)仅校验；密钥生成器(灵钥)持有签名种子并生成密钥。无种子无法伪造。
(function () {
  'use strict';
  const CHARSET = '0123456789!@#$%^&*()'; // 10 数字 + 10 特殊字符 = 20 进制
  const BASE = BigInt(CHARSET.length);     // 20
  const EPOCH = 1767225600000;             // 2026-01-01T00:00:00Z
  const DAY = 86400000;

  // 默认种子：两软件出厂一致，即装即用；制造者可在两端改为同一私有种子以提升安全
  const DEFAULT_SEED = 'LINGYU@MAKE#2026*SEED';

  function toBaseN(num, len) {
    let n = BigInt(num);
    let s = '';
    for (let i = 0; i < len; i++) {
      s = CHARSET[Number(n % BASE)] + s;
      n = n / BASE;
    }
    return s;
  }
  function fromBaseN(str) {
    let n = 0n;
    for (const c of str) {
      const idx = CHARSET.indexOf(c);
      if (idx < 0) return null;
      n = n * BASE + BigInt(idx);
    }
    return Number(n);
  }
  function bytesToBigInt(bytes) {
    let n = 0n;
    for (const b of bytes) n = (n << 8n) | BigInt(b);
    return n;
  }
  function hashMod(str, mod) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h % mod;
  }
  async function hmacSeed(seed, msg) {
    const enc = new TextEncoder();
    const key = await crypto.subtle.importKey(
      'raw', enc.encode(seed), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const sig = await crypto.subtle.sign('HMAC', key, enc.encode(msg));
    return new Uint8Array(sig);
  }

  // 生成密钥：account=账号名, days=有效天数(从生成日起算), seed=签名种子
  async function generate(account, days, seed) {
    seed = seed || DEFAULT_SEED;
    account = (account || '').trim();
    const todayOffset = Math.floor((Date.now() - EPOCH) / DAY);
    const valid = Math.max(0, Math.min(159999 - todayOffset, Math.floor(Number(days) || 0)));
    const expiryDays = todayOffset + valid;   // 绝对到期日(距纪元天数)
    const expiryStr = toBaseN(expiryDays, 4);
    const macBytes = (await hmacSeed(seed, account + '|' + expiryDays)).slice(0, 14);
    const mac = toBaseN(bytesToBigInt(macBytes), 26);
    const checksum = toBaseN(hashMod(expiryStr + mac + seed, 400), 2);
    const key = expiryStr + mac + checksum;
    return {
      key,
      expiresAt: new Date(EPOCH + expiryDays * DAY).toISOString(),
      days: valid
    };
  }

  // 校验密钥：返回 {ok, expiresAt?, days?(剩余天数), reason?}
  async function verify(key, account, seed) {
    seed = seed || DEFAULT_SEED;
    key = (key || '').trim();
    account = (account || '').trim();
    if (key.length !== 32) return { ok: false, reason: 'len' };
    if (!/^[0-9!@#$%^&*()]+$/.test(key)) return { ok: false, reason: 'chars' };
    const expiryStr = key.slice(0, 4);
    const mac = key.slice(4, 30);
    const checksum = key.slice(30, 32);
    if (toBaseN(hashMod(expiryStr + mac + seed, 400), 2) !== checksum) return { ok: false, reason: 'checksum' };
    const expiryDays = fromBaseN(expiryStr);
    if (expiryDays == null) return { ok: false, reason: 'expiry' };
    const macBytes = (await hmacSeed(seed, account + '|' + expiryDays)).slice(0, 14);
    const macCalc = toBaseN(bytesToBigInt(macBytes), 26);
    if (macCalc !== mac) return { ok: false, reason: 'mac' };
    const expiresAt = EPOCH + expiryDays * DAY;
    if (expiresAt < Date.now()) return { ok: false, reason: 'expired', expiresAt: new Date(expiresAt).toISOString() };
    return { ok: true, expiresAt: new Date(expiresAt).toISOString(), days: Math.floor((expiresAt - Date.now()) / DAY) };
  }

  // 种子短指纹：便于制造者在两端核对"是否同一种子"
  function fingerprint(seed) {
    const s = seed || DEFAULT_SEED;
    let h = 2166136261 >>> 0;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return (h >>> 0).toString(36).toUpperCase().padStart(7, '0');
  }
  // 绑定码：把种子编码为可粘贴的 base64（主软件导入后即与灵钥关联）
  function encodeBind(seed) { return btoa(unescape(encodeURIComponent(seed || DEFAULT_SEED))); }
  function decodeBind(code) {
    try { return decodeURIComponent(escape(atob((code || '').trim()))); } catch (e) { return null; }
  }

  window.KeyLib = {
    CHARSET, DEFAULT_SEED, generate, verify, fingerprint, encodeBind, decodeBind
  };
})();
