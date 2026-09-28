/* Public verification page - no auth needed */
'use strict';

const API = (function () {
  const meta = document.querySelector('meta[name="api-base"]');
  const rel = meta ? meta.content : '../api/index.php';
  return new URL(rel, window.location.href).href;
})();
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function money(n) {
  return '₱' + Number(n || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function api(path) {
  const res = await fetch(API + (path.startsWith('?') ? path : '?' + path));
  let data; try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) throw new Error(data.error || 'HTTP ' + res.status);
  return data;
}

async function loadAnchor() {
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
        <tr><td class="muted">Kabuuang benta ng araw</td><td>${money(a.grand_total)} (${a.tx_count} items)</td></tr>
      </tbody></table>` : '<p>Wala pang anchor.</p>';
  } catch (e) { $('anchor-info').textContent = e.message; }
}

async function doVerify() {
  const ref = $('verify-input').value.trim();
  if (!ref) return;
  $('verify-result').innerHTML = '<p class="muted">Sinisilip ang blockchain...</p>';
  try {
    const d = await api('r=verify/' + encodeURIComponent(ref));
    $('verify-result').innerHTML = `
      <div style="margin-bottom:10px;">
        <span class="pill ${d.verified ? 'ok' : 'bad'}">${d.verified ? 'VERIFIED - tunay at buo' : 'TAMPERED - nagbago ang rekord!'}</span>
        <span class="pill ${d.anchor && d.anchor.status === 'anchored' ? 'anchored' : 'pending'}">${d.anchor && d.anchor.status === 'anchored' ? 'Naka-anchor sa blockchain' : 'Hindi pa naka-anchor'}</span>
        ${d.on_chain_match === true ? '<span class="pill ok">Tugma sa on-chain root</span>' : d.on_chain_match === false ? '<span class="pill bad">Hindi tugma sa chain</span>' : ''}
      </div>
      <div class="receipt">
        <div class="rt"><span>${esc(d.receipt_no)}</span><span class="gold">${money(d.grand_total)}</span></div>
        <table><thead><tr><th>Item</th><th>Qty</th><th>Subtotal</th></tr></thead><tbody>
        ${d.lines.map(l => `<tr><td>${esc(l.product_name)}</td><td>${l.quantity}</td><td>${money(l.subtotal)}</td></tr>`).join('')}
        </tbody></table>
      </div>
      <div class="mono" style="margin-top:10px;">Araw: ${esc(d.sale_time)}</div>
      <div class="mono">Merkle root: <span class="hash">${esc(d.merkle_root)}</span></div>
      ${d.anchor && d.anchor.tx_hash ? `<div class="mono">Proof: <a target="_blank" rel="noopener" href="https://polygonscan.com/tx/${esc(d.anchor.tx_hash)}">${esc(d.anchor.tx_hash)}</a></div>` : ''}`;
  } catch (e) {
    $('verify-result').innerHTML = `<span class="pill bad">${esc(e.message)}</span>`;
  }
}

$('verify-btn').addEventListener('click', doVerify);
$('verify-input').addEventListener('keydown', e => { if (e.key === 'Enter') doVerify(); });
loadAnchor();