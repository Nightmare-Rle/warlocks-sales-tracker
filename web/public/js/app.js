/* Warlocks Sales Tracker - frontend (PWA) */
'use strict';

const API = (function () {
  const meta = document.querySelector('meta[name="api-base"]');
  const rel = meta ? meta.content : '../api/index.php';
  return new URL(rel, window.location.href).href;
})();

let state = {
  token: localStorage.getItem('st_token') || null,
  user: JSON.parse(localStorage.getItem('st_user') || 'null'),
  products: [],
  categories: [],
  cart: new Map(), // productId -> qty
};

let checkoutRef = null; // idempotency key for the current cart

const $ = (id) => document.getElementById(id);

/* ---------------- utilities ---------------- */
function toast(msg, ms = 2200) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove('show'), ms);
}

function money(n) {
  return '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  const res = await fetch(API + (path.startsWith('?') ? path : '?' + path), { ...opts, headers });
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (res.status === 401 && state.token) {
    forceLogin();
    throw new Error('Session expired. Mag-login ulit.');
  }
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

function forceLogin() {
  localStorage.removeItem('st_token');
  localStorage.removeItem('st_user');
  state.token = null; state.user = null; state.cart.clear();
  $('app').classList.remove('show');
  $('login').style.display = 'flex';
}

function requireOwner() {
  if (!state.user || state.user.role !== 'owner') { toast('Owner access lang.'); return false; }
  return true;
}

/* ---------------- auth ---------------- */
async function login(e) {
  e.preventDefault();
  try {
    const d = await api('r=login', {
      method: 'POST',
      body: JSON.stringify({ username: $('username').value.trim(), password: $('password').value })
    });
    state.token = d.token;
    state.user = d.user;
    localStorage.setItem('st_token', d.token);
    localStorage.setItem('st_user', JSON.stringify(d.user));
    enterApp();
    toast('Welcome, ' + d.user.username);
  } catch (err) { toast(err.message, 3000); }
}

function logout() {
  try { api('r=logout', { method: 'POST' }); } catch {}
  forceLogin();
}

function enterApp() {
  $('login').style.display = 'none';
  $('app').classList.add('show');
  $('whoami').textContent = state.user.username;
  $('rolebadge').textContent = state.user.role.toUpperCase();
  // hide product-edit UI for cashiers
  document.body.classList.toggle('is-owner', state.user.role === 'owner');
  switchView('dashboard');
  loadDashboard();
  loadProducts();
}

function switchView(name) {
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  ['dashboard','pos','products','history','transparency'].forEach(v =>
    $('view-' + v).style.display = (v === name) ? 'block' : 'none');
  if (name === 'pos') loadProducts();
  if (name === 'history') { if (!$('h-date').value) $('h-date').value = todayStr(); loadHistory(); }
  if (name === 'transparency') loadTransparency();
  if (name === 'dashboard') loadDashboard();
}

function todayStr() { return new Date().toISOString().slice(0, 10); }

/* ---------------- dashboard ---------------- */
async function loadDashboard() {
  try {
    const s = await api('r=summary&from=' + todayStr() + '&to=' + todayStr());
    const todayTotal = Number(s.grand_total || 0);
    const receipts = s.days && s.days.length ? Number(s.days[0].receipts) : 0;
    $('d-today').textContent = money(todayTotal);
    $('d-count').textContent = receipts;
    $('d-products').textContent = s.active_products;

    const cap = 5000;
    const pct = Math.min(100, (todayTotal / cap) * 100);
    $('jar-fill').style.height = pct + '%';
    $('jar-lbl').textContent = `${money(todayTotal)} / ${money(cap)}`;

    if (s.latest_anchor) {
      const a = s.latest_anchor;
      $('d-anchor').innerHTML = `
        <div class="mono">Day: <b>${esc(a.anchor_date)}</b> &middot; status <span class="pill ${a.status}">${esc(a.status)}</span></div>
        <div class="mono">Merkle root: <span class="hash">${esc(a.merkle_root)}</span></div>
        ${a.tx_hash ? `<div class="mono">Tx: <a href="https://polygonscan.com/tx/${esc(a.tx_hash)}" target="_blank" rel="noopener">${esc(a.tx_hash.slice(0,18))}...</a></div>` : '<div class="mono">Not yet anchored (daily cron).</div>'}`;
    } else {
      $('d-anchor').innerHTML = 'Wala pang na-anchor. Magkakaroon pagkatapos ng unang araw na may benta at gumana ang daily cron.';
    }
    drawWeek();
  } catch (err) { $('d-today').textContent = 'err'; $('d-count').textContent = '-'; toast(err.message, 3000); }
}

async function drawWeek() {
  const dates = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(); d.setDate(d.getDate() - i);
    dates.push(d.toISOString().slice(0, 10));
  }
  let totals = [];
  try {
    const s = await api('r=summary&from=' + dates[0] + '&to=' + dates[6]);
    const by = Object.fromEntries((s.days || []).map(x => [x.d, x.total]));
    totals = dates.map(d => Number(by[d] || 0));
  } catch { totals = dates.map(() => 0); }

  const cv = $('day-chart');
  if (!cv.getContext) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height, pad = 8;
  const max = Math.max(1, ...totals);
  ctx.clearRect(0, 0, W, H);
  const bw = (W - pad * 2) / 7;
  totals.forEach((t, i) => {
    const h = Math.max(3, (t / max) * (H - 34));
    const x = pad + i * bw + 2, y = H - 16 - h;
    const g = ctx.createLinearGradient(0, y, 0, H - 16);
    g.addColorStop(0, '#ff0040'); g.addColorStop(1, '#8b0000');
    ctx.fillStyle = g;
    if (ctx.roundRect) {
      ctx.beginPath(); ctx.roundRect(x, y, bw - 4, h, 4); ctx.fill();
    } else {
      ctx.fillRect(x, y, bw - 4, h);
    }
    ctx.fillStyle = '#888';
    ctx.font = '10px Consolas';
    ctx.textAlign = 'center';
    ctx.fillText(dates[i].slice(5), pad + i * bw + bw / 2, H - 4);
    ctx.fillText(t ? money(t) : '', pad + i * bw + bw / 2, y - 2);
  });
  $('chart-note').textContent = 'Huling 7 araw na benta (hindi kasama ang bayad, benta lang).';
}

/* ---------------- products ---------------- */
async function loadProducts() {
  try {
    const d = await api('r=products');
    state.products = d.products;
    state.categories = [...new Set(d.products.map(p => p.category))].sort();

    const catSel = $('pos-cat');
    const cur = catSel.value;
    catSel.innerHTML = '<option value="">Lahat</option>' +
      state.categories.map(c => `<option>${esc(c)}</option>`).join('');
    catSel.value = cur;

    renderPosList();
    renderProductList();
  } catch (err) { toast(err.message); }
}

function renderPosList() {
  const q = $('pos-search').value.trim().toLowerCase();
  const cat = $('pos-cat').value;
  const el = $('pos-list');
  const list = state.products.filter(p =>
    (!cat || p.category === cat) &&
    (!q || p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q))
  );
  if (!list.length) { el.innerHTML = '<p class="muted">Walang produktong tugma.</p>'; return; }
  el.innerHTML = list.map(p => `
    <div class="product-card" data-pid="${p.id}">
      <div class="pname">${esc(p.name)}</div>
      <div class="pprice">${money(p.price)}</div>
      <div class="pcat">${esc(p.category)}</div>
    </div>`).join('');
  el.querySelectorAll('.product-card').forEach(card => {
    card.onclick = () => addToCart(Number(card.dataset.pid));
  });
}

async function renderProductList() {
  const el = $('p-list');
  if (!state.products.length) { el.innerHTML = '<p class="muted">Wala pang produkto.</p>'; return; }
  el.innerHTML = '<table><thead><tr><th>Name</th><th>Cat</th><th>Price</th><th></th></tr></thead><tbody>' +
    state.products.map(p => `
      <tr>
        <td>${esc(p.name)}</td>
        <td class="muted">${esc(p.category)}</td>
        <td>${money(p.price)}</td>
        <td style="text-align:right;white-space:nowrap;">
          <button class="btn btn-sm" data-edit="${p.id}">Edit</button>
          <button class="btn btn-sm btn-danger" data-del="${p.id}">Del</button>
        </td>
      </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => editProduct(Number(b.dataset.edit)));
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = () => delProduct(Number(b.dataset.del)));
}

async function addProduct() {
  if (!requireOwner()) return;
  const name = $('p-name').value.trim();
  const price = parseFloat($('p-price').value);
  const cat = $('p-cat').value.trim() || 'OTHER';
  if (!name || isNaN(price) || price < 0) { toast('Ilagay ang pangalan at presyo.'); return; }
  try {
    await api('r=products', { method: 'POST', body: JSON.stringify({ name, price, category: cat }) });
    $('p-name').value = ''; $('p-price').value = ''; $('p-cat').value = '';
    toast('Naidagdag: ' + name);
    loadProducts(); loadDashboard();
  } catch (e) { toast(e.message); }
}

async function editProduct(id) {
  if (!requireOwner()) return;
  const p = state.products.find(x => x.id === id);
  if (!p) return;
  const name = prompt('Pangalan:', p.name);
  if (name == null) return;
  const price = parseFloat(prompt('Presyo:', p.price));
  if (isNaN(price)) { toast('Invalid na presyo.'); return; }
  try {
    await api('r=products/' + id, { method: 'PUT', body: JSON.stringify({ name: name.trim(), price }) });
    toast('Na-update.');
    loadProducts(); loadDashboard();
  } catch (e) { toast(e.message); }
}

async function delProduct(id) {
  if (!requireOwner()) return;
  if (!confirm('Tanggalin ang produktong ito?')) return;
  try {
    await api('r=products/' + id, { method: 'DELETE' });
    toast('Na-delete.');
    loadProducts(); loadDashboard();
  } catch (e) { toast(e.message); }
}

/* ---------------- POS / cart ---------------- */
function addToCart(pid) {
  state.cart.set(pid, (state.cart.get(pid) || 0) + 1);
  checkoutRef = null; // new content => new idempotency key
  renderCart();
}

function setQty(pid, q) {
  if (q <= 0) state.cart.delete(pid);
  else state.cart.set(pid, q);
  checkoutRef = null;
  renderCart();
}

function priceCents(p) {
  return (p.price_cents != null) ? p.price_cents : Math.round(Number(p.price) * 100);
}

function renderCart() {
  const el = $('cart-items');
  let totalCents = 0;
  if (!state.cart.size) { el.innerHTML = '<p class="muted">Walang laman.</p>'; $('cart-total').textContent = '₱0.00'; return; }
  el.innerHTML = [...state.cart.entries()].map(([pid, qty]) => {
    const p = state.products.find(x => x.id === pid);
    if (!p) return '';
    const subCents = priceCents(p) * qty; totalCents += subCents;
    return `<div class="cart-item">
      <div class="ci-name">${esc(p.name)}</div>
      <button class="qty-btn" data-q="-1" data-pid="${pid}">−</button>
      <b>${qty}</b>
      <button class="qty-btn" data-q="1" data-pid="${pid}">+</button>
      <div class="muted" style="width:80px;text-align:right;">${money(subCents / 100)}</div>
    </div>`;
  }).join('');
  $('cart-total').textContent = money(totalCents / 100);
  el.querySelectorAll('[data-q]').forEach(b => b.onclick = () =>
    setQty(Number(b.dataset.pid), (state.cart.get(Number(b.dataset.pid)) || 0) + Number(b.dataset.q)));
}

function newClientRef() {
  return 'pos-' + Date.now().toString(36) + '-' + Math.random().toString(16).slice(2, 10);
}

async function checkout() {
  if (!state.cart.size) { toast('Walang laman ang cart.'); return; }
  if (!checkoutRef) checkoutRef = newClientRef();
  const items = [...state.cart.entries()].map(([pid, qty]) => ({ product_id: pid, quantity: qty }));
  try {
    const d = await api('r=sales', { method: 'POST', body: JSON.stringify({ items, client_ref: checkoutRef }) });
    checkoutRef = null;
    state.cart.clear();
    renderCart();
    toast('Resibo ' + d.receipt_no + ' — ' + money(d.grand_total) + ' ✓', 3200);
    loadDashboard();
  } catch (e) {
    // Keep checkoutRef so a retry cannot double-charge.
    toast(e.message + ' — pindutin ulit, safe i-retry.', 4000);
  }
}

/* ---------------- history ---------------- */
async function loadHistory() {
  const date = $('h-date').value || todayStr();
  try {
    const d = await api('r=sales&date=' + date);
    const el = $('h-list');
    if (!d.receipts.length) { el.innerHTML = '<p class="muted">Walang benta sa petsang ito.</p>'; return; }
    el.innerHTML = d.receipts.map(r => `
      <div class="receipt" style="margin-bottom:10px;">
        <div class="rt"><span>${esc(r.receipt_no)}</span><span class="gold">${money(r.total)}</span></div>
        <table><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead><tbody>
        ${r.lines.map(l => `<tr><td>${esc(l.product_name)}</td><td>${l.quantity}</td><td>${money(l.price)}</td><td>${money(l.subtotal)}</td></tr>`).join('')}
        </tbody></table>
        <div class="mono" style="margin-top:6px;">hash: <span class="hash">${esc(r.hash)}</span></div>
      </div>`).join('');
  } catch (e) { $('h-list').innerHTML = '<p class="muted">' + esc(e.message) + '</p>'; }
}

/* ---------------- transparency ---------------- */
async function loadTransparency() {
  $('anchor-info').innerHTML = 'INIload...';
  try {
    const d = await api('r=anchors/latest');
    const a = d.anchor;
    $('anchor-info').innerHTML = a ? `
      <table><tbody>
        <tr><td class="muted">Araw</td><td><b>${esc(a.anchor_date)}</b></td></tr>
        <tr><td class="muted">Status</td><td><span class="pill ${esc(a.status)}">${esc(a.status)}</span></td></tr>
        <tr><td class="muted">Merkle root</td><td class="hash wrap">${esc(a.merkle_root)}</td></tr>
        <tr><td class="muted">Tx hash</td><td>${a.tx_hash ? `<a class="hash wrap" target="_blank" rel="noopener" href="https://polygonscan.com/tx/${esc(a.tx_hash)}">${esc(a.tx_hash)}</a>` : '—'}</td></tr>
        <tr><td class="muted">Chain</td><td>${esc(a.chain || '—')}</td></tr>
        <tr><td class="muted">Benta / Dami</td><td>${money(a.grand_total)} / ${a.tx_count}</td></tr>
      </tbody></table>`
      : '<p>Wala pang anchor. Lilitaw ito kapag may laman na ang unang araw at gumana ang daily cron + signer.</p>';
  } catch (e) { $('anchor-info').textContent = e.message; }
}

async function verifyHash() {
  const ref = $('verify-input').value.trim();
  if (!ref) { toast('Ilagay ang receipt no o hash.'); return; }
  try {
    const d = await api('r=verify/' + encodeURIComponent(ref));
    $('verify-result').innerHTML = `
      <div style="margin-bottom:8px;">
        <span class="pill ${d.verified ? 'ok' : 'bad'}">${d.verified ? 'VERIFIED — tunay at buo' : 'TAMPERED — hindi tugma ang hash!'}</span>
        <span class="pill ${d.anchor && d.anchor.status === 'anchored' ? 'anchored' : 'pending'}">${d.anchor && d.anchor.status === 'anchored' ? 'ANCHORED ON-CHAIN' : 'NOT YET ANCHORED'}</span>
        ${d.on_chain_match === true ? '<span class="pill ok">TUGMA SA ON-CHAIN ROOT</span>' : d.on_chain_match === false ? '<span class="pill bad">HINDI TUGMA SA CHAIN</span>' : ''}
      </div>
      <div class="mono">Receipt: <b>${esc(d.receipt_no)}</b></div>
      <div class="mono">Date: ${esc(d.sale_time)}</div>
      <div class="mono">Total: <b class="gold">${money(d.grand_total)}</b></div>
      <hr class="sep">
      <table><thead><tr><th>Item</th><th>Qty</th><th>Subtotal</th><th>Hash ok</th></tr></thead><tbody>
      ${d.lines.map(l => `<tr><td>${esc(l.product_name)}</td><td>${l.quantity}</td><td>${money(l.subtotal)}</td>
        <td><span class="pill ${l.hash_ok ? 'ok' : 'bad'}">${l.hash_ok ? 'ok' : 'FAIL'}</span></td></tr>`).join('')}
      </tbody></table>
      <div class="mono" style="margin-top:8px;">Merkle root ng araw: <span class="hash">${esc(d.merkle_root)}</span></div>
      ${d.anchor && d.anchor.tx_hash ? `<div class="mono">On-chain: <a target="_blank" rel="noopener" href="https://polygonscan.com/tx/${esc(d.anchor.tx_hash)}">${esc(d.anchor.tx_hash)}</a></div>` : ''}`;
  } catch (e) {
    $('verify-result').innerHTML = `<span class="pill bad">${esc(e.message)}</span>`;
  }
}

/* ---------------- init ---------------- */
$('login-form').addEventListener('submit', login);
$('logout').addEventListener('click', logout);
$('pos-search').addEventListener('input', renderPosList);
$('pos-cat').addEventListener('change', renderPosList);
$('pos-list').addEventListener('click', e => {
  const card = e.target.closest('.product-card');
  if (card) addToCart(Number(card.dataset.pid));
});
$('checkout').addEventListener('click', checkout);
$('p-add').addEventListener('click', addProduct);
$('h-refresh').addEventListener('click', loadHistory);
$('h-date').addEventListener('change', loadHistory);
$('verify-btn').addEventListener('click', verifyHash);
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => switchView(b.dataset.view));

if (state.token && state.user) enterApp();
else $('login').style.display = 'flex';

// PWA: register service worker (silent fail if unsupported)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

// PWA install prompt hint
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  toast('I-install ang app (Android): menu > Add to Home screen');
});