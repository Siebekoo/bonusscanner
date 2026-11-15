"""Write one self-contained HTML page with all deals, searchable and filterable."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = r"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alle aanbiedingen</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e4e2dc;--acc:#e8590c}
*{box-sizing:border-box}body{margin:0;font:15px/1.4 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 20px}
h1{font-size:20px;margin:0 0 2px}.sub{color:var(--mute);font-size:13px}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;align-items:center}
input[type=search]{flex:1 1 260px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}
select{padding:8px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 11px;font-size:13px;cursor:pointer;user-select:none}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}.chip .n{opacity:.6;margin-left:4px}
.chip.err{border-style:dashed;color:var(--mute)}
main{padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px;text-decoration:none;color:inherit;position:relative}
.card:hover{border-color:#bbb}
.img{height:120px;display:flex;align-items:center;justify-content:center}
.img img{max-width:100%;max-height:120px;object-fit:contain}
.store{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute)}
.title{font-weight:600;font-size:14px}.size{color:var(--mute);font-size:12px}
.deal{color:var(--acc);font-weight:700;font-size:13px}
.prices{margin-top:auto;display:flex;gap:8px;align-items:baseline}
.now{font-weight:700;font-size:17px}.was{color:var(--mute);text-decoration:line-through;font-size:13px}
.pct{position:absolute;top:8px;right:8px;background:var(--acc);color:#fff;border-radius:6px;padding:2px 6px;font-size:12px;font-weight:700}
.until{font-size:11px;color:var(--mute)}
.pct.multi{background:#fff;color:#1f5fbf;border:1.5px solid #1f5fbf}
.qty{font-size:12px;color:#1f5fbf;font-weight:600}
.deal.multi{color:#1f5fbf}
.legend{font-size:12px;color:var(--mute);margin-top:8px}
.legend b{display:inline-block;padding:0 5px;border-radius:4px;font-size:11px}
.legend .d{background:var(--acc);color:#fff}.legend .m{border:1.5px solid #1f5fbf;color:#1f5fbf}
@media (max-width:600px){
  header{padding:10px 12px;position:static}main{padding:10px 12px;grid-template-columns:repeat(2,1fr);gap:8px}
  .img{height:90px}.img img{max-height:90px}.bar select{flex:1 1 30%;min-width:0;font-size:13px;padding:6px}.legend{display:none}
}
.empty{grid-column:1/-1;text-align:center;color:var(--mute);padding:60px}
</style></head><body>
<header>
  <h1>Alle aanbiedingen</h1>
  <div class="sub" id="sub"></div>
  <div class="bar">
    <input type="search" id="q" placeholder="Zoek product, bv. koffie, pindakaas, shampoo…" autofocus>
    <select id="type">
      <option value="">Alle deals</option>
      <option value="korting">Alleen directe korting</option>
      <option value="meer kopen">Alleen meer kopen (1+1, 2e halve prijs…)</option>
    </select>
    <select id="sort">
      <option value="pct">Hoogste directe korting</option>
      <option value="eff">Hoogste korting incl. meer kopen</option>
      <option value="price">Laagste prijs</option>
      <option value="store">Winkel</option>
      <option value="title">Naam</option>
    </select>
    <select id="min">
      <option value="0">Alle kortingen</option>
      <option value="20">≥ 20%</option>
      <option value="25">≥ 25%</option>
      <option value="35">≥ 35%</option>
      <option value="50">≥ 50%</option>
    </select>
  </div>
  <div class="chips" id="chips"></div>
  <div class="legend"><b class="d">-30%</b> korting op 1 stuk &nbsp; <b class="m">-50% bij 2</b> alleen als je meer koopt</div>
</header>
<main id="grid"></main>
<script>
const DATA = __DATA__;
const deals = DATA.deals;
const off = new Set();
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eur = v => v == null ? '' : '€' + v.toFixed(2).replace('.', ',');
const norm = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');

function chips(){
  const counts = {};
  deals.forEach(d => counts[d.store] = (counts[d.store]||0) + 1);
  const names = Object.keys(DATA.stores).sort();
  $('chips').innerHTML = names.map(n => {
    const s = DATA.stores[n], c = counts[n]||0;
    const cls = 'chip' + (off.has(n) ? '' : ' on') + (s.ok && c ? '' : ' err');
    const tip = s.ok ? '' : ` title="${esc(s.error)}"`;
    return `<span class="${cls}" data-s="${esc(n)}"${tip}>${esc(n)}<span class="n">${c}</span></span>`;
  }).join('');
  document.querySelectorAll('.chip').forEach(el => el.onclick = e => {
    const n = el.dataset.s;
    if (e.shiftKey || e.metaKey) { off.clear(); names.forEach(x => x !== n && off.add(x)); }
    else off.has(n) ? off.delete(n) : off.add(n);
    chips(); render();
  });
}

function render(){
  const words = norm($('q').value).split(/\s+/).filter(Boolean);
  const min = +$('min').value, sort = $('sort').value, type = $('type').value;
  let list = deals.filter(d => !off.has(d.store) && (!type || d.deal_type === type) &&
    (d.effective_pct||0) >= min &&
    words.every(w => norm(d.title + ' ' + d.deal_text + ' ' + d.size + ' ' + d.category).includes(w)));
  const by = {
    // direct discounts first (biggest first), then multi-buy deals
    pct: (a,b) => ((a.deal_type==='meer kopen') - (b.deal_type==='meer kopen'))
                  || ((b.discount_pct ?? b.effective_pct ?? 0) - (a.discount_pct ?? a.effective_pct ?? 0)),
    eff: (a,b) => (b.effective_pct||0) - (a.effective_pct||0),
    price: (a,b) => (a.price_now ?? 1e9) - (b.price_now ?? 1e9),
    store: (a,b) => a.store.localeCompare(b.store),
    title: (a,b) => a.title.localeCompare(b.title)}[sort];
  list.sort(by);
  $('grid').innerHTML = list.length ? list.slice(0, 1500).map(d => `
    <a class="card" href="${esc(d.url)}" target="_blank" rel="noopener">
      ${badge(d)}
      <div class="img">${d.image ? `<img loading="lazy" src="${esc(d.image)}" alt="">` : ''}</div>
      <div class="store">${esc(d.store)}</div>
      <div class="title">${esc(d.title)}</div>
      ${d.size ? `<div class="size">${esc(d.size)}</div>` : ''}
      ${d.deal_text ? `<div class="deal ${multi(d)?'multi':''}">${esc(d.deal_text)}</div>` : ''}
      ${multi(d) ? `<div class="qty">Alleen bij ${d.min_qty} stuks</div>` : ''}
      ${prices(d)}
      ${d.valid_until ? `<div class="until">t/m ${esc(d.valid_until)}</div>` : ''}
    </a>`).join('') : '<div class="empty">Geen aanbiedingen gevonden.</div>';
  $('sub').textContent = `${list.length} van ${deals.length} aanbiedingen · bijgewerkt ${DATA.generated.replace('T',' ')}`;
}
function multi(d){ return d.deal_type === 'meer kopen'; }
function badge(d){
  if (multi(d)) return d.effective_pct ? `<span class="pct multi">-${d.effective_pct}% bij ${d.min_qty}</span>` : '';
  return d.discount_pct ? `<span class="pct">-${d.discount_pct}%</span>` : '';
}
function prices(d){
  if (!multi(d))
    return `<div class="prices"><span class="now">${eur(d.price_now)}</span><span class="was">${eur(d.price_was)}</span></div>`;
  // multi-buy: show the normal single price, plus the per-item price when buying the full amount
  const normal = d.price_was ?? d.price_now;
  const per = d.price_was && d.price_now && d.price_now < d.price_was
    ? `<span class="was" style="text-decoration:none">${eur(d.price_now)} p/st bij ${d.min_qty}</span>` : '';
  return `<div class="prices"><span class="now">${eur(normal)}</span>${per}</div>`;
}
['q','sort','min','type'].forEach(id => $(id).addEventListener('input', render));
chips(); render();
</script></body></html>
"""


def write_html(payload: dict, path: Path):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
