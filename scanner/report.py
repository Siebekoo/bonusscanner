"""Write one self-contained HTML page with all deals.

Features: this week / next week / my list tabs, search, categories, stores, deal type,
sorting (incl. price per kg/l), compare-stores view, favorites (saved per device),
price-history tags, shareable filter links, dark mode, store health warnings.
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = r"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f6f5f2">
<title>Alle aanbiedingen</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e4e2dc;--acc:#e8590c;--blue:#1f5fbf;
      --good:#1e7a46;--goodbg:#e6f4ec;--chip:#fff;--warnbg:#fff4e0;--warn:#8a5300}
[data-theme=dark]{--bg:#161615;--card:#21211f;--ink:#ecebe7;--mute:#9c9b95;--line:#363532;--acc:#ff7a2e;--blue:#7fb0ff;
      --good:#6fd39b;--goodbg:#1d3427;--chip:#2a2a28;--warnbg:#3a2c12;--warn:#ffcf80}
*{box-sizing:border-box}
body{margin:0;font:15px/1.4 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
button,input,select{font:inherit;color:inherit}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 20px 10px}
.top{display:flex;align-items:center;gap:10px}
h1{font-size:20px;margin:0;flex:1}
.iconbtn{border:1px solid var(--line);background:var(--chip);border-radius:8px;padding:6px 10px;cursor:pointer;font-size:14px}
.sub{color:var(--mute);font-size:13px;margin-top:2px}
.tabs{display:flex;gap:4px;margin-top:10px;border-bottom:1px solid var(--line)}
.tab{border:none;background:none;padding:8px 12px;cursor:pointer;color:var(--mute);border-bottom:2px solid transparent;margin-bottom:-1px;font-weight:600}
.tab.on{color:var(--ink);border-color:var(--ink)}
.tab .n{font-weight:400;opacity:.7;margin-left:3px}
.bar{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;align-items:center}
input[type=search],.fav input{flex:1 1 240px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card)}
select{padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--card)}
label.toggle{display:flex;align-items:center;gap:6px;font-size:14px;cursor:pointer;user-select:none;white-space:nowrap}
.chips{display:flex;gap:6px;margin-top:8px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.chips::-webkit-scrollbar{display:none}
.chip{border:1px solid var(--line);background:var(--chip);border-radius:999px;padding:4px 11px;font-size:13px;cursor:pointer;user-select:none;white-space:nowrap}
.chip.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chip .n{opacity:.6;margin-left:4px}
.chip.err{border-style:dashed;opacity:.7}
.chip.term{background:var(--card);border-color:var(--acc)}
.chip.term b{margin-left:6px;cursor:pointer;opacity:.6}
.fav{display:none;margin-top:10px}
.fav.show{display:block}
.fav form{display:flex;gap:8px}
.fav button{border:none;background:var(--ink);color:var(--bg);border-radius:8px;padding:8px 14px;cursor:pointer}
.hint{font-size:12px;color:var(--mute);margin-top:6px}
details.warn{margin-top:8px;font-size:13px;background:var(--warnbg);color:var(--warn);border-radius:8px;padding:6px 10px}
details.warn summary{cursor:pointer}
details.warn ul{margin:6px 0 2px;padding-left:18px}
main{padding:16px 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:5px;position:relative;color:inherit;text-decoration:none}
.card:hover{border-color:var(--mute)}
.card.isfav{border-color:var(--acc)}
.star{position:absolute;top:6px;left:6px;border:none;background:none;font-size:20px;cursor:pointer;color:var(--mute);padding:2px 4px;line-height:1;z-index:2}
.star.on{color:var(--acc)}
.img{height:120px;display:flex;align-items:center;justify-content:center;border-radius:6px;overflow:hidden}
.img img{max-width:100%;max-height:120px;object-fit:contain}
[data-theme=dark] .img.has{background:#fff}
.store{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute)}
.title{font-weight:600;font-size:14px}
.size{color:var(--mute);font-size:12px}
.deal{color:var(--acc);font-weight:700;font-size:13px}
.deal.multi,.qty{color:var(--blue)}
.qty{font-size:12px;font-weight:600}
.prices{margin-top:auto;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.now{font-weight:700;font-size:17px}
.was{color:var(--mute);text-decoration:line-through;font-size:13px}
.per{color:var(--mute);font-size:12px}
.pct{position:absolute;top:8px;right:8px;background:var(--acc);color:#fff;border-radius:6px;padding:2px 6px;font-size:12px;font-weight:700}
.pct.multi{background:var(--card);color:var(--blue);border:1.5px solid var(--blue)}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:11px;border-radius:4px;padding:1px 6px;background:var(--line);color:var(--mute)}
.tag.best{background:var(--goodbg);color:var(--good);font-weight:600}
.tag.new{background:var(--line);color:var(--ink)}
.until{font-size:11px;color:var(--mute)}
.cmp{grid-column:span 2}
.cmp .rows{display:flex;flex-direction:column;gap:2px;margin-top:4px}
.row{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:6px 8px;border-radius:6px;text-decoration:none;color:inherit}
.row:hover{background:var(--bg)}
.row.best{background:var(--goodbg)}
.row .s{font-weight:600;font-size:13px}
.row .d{font-size:12px;color:var(--mute)}
.row .p{text-align:right;font-weight:700}
.row .u{text-align:right;font-size:12px;color:var(--mute)}
.more{grid-column:1/-1;justify-self:center;border:1px solid var(--line);background:var(--card);border-radius:8px;padding:10px 20px;cursor:pointer}
.empty{grid-column:1/-1;text-align:center;color:var(--mute);padding:60px 10px}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);padding:8px 16px;border-radius:8px;font-size:14px;opacity:0;transition:opacity .2s;pointer-events:none;z-index:9}
.toast.show{opacity:1}
.legend{font-size:12px;color:var(--mute);margin-top:8px}
.legend b{display:inline-block;padding:0 5px;border-radius:4px;font-size:11px}
.legend .d{background:var(--acc);color:#fff}.legend .m{border:1.5px solid var(--blue);color:var(--blue)}
@media (max-width:640px){
  header{position:static;padding:10px 12px}
  main{padding:10px 12px;grid-template-columns:repeat(2,1fr);gap:8px}
  .cmp{grid-column:1/-1}
  .img{height:90px}.img img{max-height:90px}
  .bar select{flex:1 1 30%;min-width:0;font-size:13px;padding:6px}
  .legend{display:none}
  .tab{padding:8px 8px;font-size:14px}
}
</style></head><body>
<header>
  <div class="top">
    <h1>Alle aanbiedingen</h1>
    <button class="iconbtn" id="share" title="Kopieer een link naar deze selectie">Deel</button>
    <button class="iconbtn" id="theme" title="Licht / donker">🌙</button>
  </div>
  <div class="sub" id="sub"></div>
  <div id="warn"></div>
  <div class="tabs" id="tabs"></div>
  <div class="fav" id="fav">
    <form id="favform"><input id="favin" placeholder="Voeg toe aan je lijst, bv. pepsi max, douwe egberts" autocomplete="off"><button>Toevoegen</button></form>
    <div class="chips" id="terms"></div>
    <div class="hint">Of tik op ☆ bij een product. Je lijst wordt alleen op dit apparaat bewaard.</div>
  </div>
  <div class="bar">
    <input type="search" id="q" placeholder="Zoek product, bv. koffie, pindakaas, shampoo…">
    <select id="type">
      <option value="">Alle deals</option>
      <option value="korting">Alleen directe korting</option>
      <option value="meer kopen">Alleen meer kopen</option>
    </select>
    <select id="sort">
      <option value="pct">Hoogste directe korting</option>
      <option value="eff">Hoogste korting incl. meer kopen</option>
      <option value="unit">Laagste prijs per kg / liter</option>
      <option value="price">Laagste prijs</option>
      <option value="store">Winkel</option>
      <option value="title">Naam</option>
    </select>
    <select id="min">
      <option value="0">Alle kortingen</option>
      <option value="20">≥ 20%</option>
      <option value="30">≥ 30%</option>
      <option value="40">≥ 40%</option>
      <option value="50">≥ 50%</option>
    </select>
    <label class="toggle"><input type="checkbox" id="cmp"> Vergelijk winkels</label>
  </div>
  <div class="chips" id="cats"></div>
  <div class="chips" id="stores"></div>
  <div class="legend"><b class="d">-30%</b> korting op 1 stuk &nbsp; <b class="m">-50% bij 2</b> alleen als je meer koopt</div>
</header>
<main id="grid"></main>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const ALL = DATA.deals;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eur = v => v == null ? '' : '€' + v.toFixed(2).replace('.', ',');
const norm = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
const multi = d => d.deal_type === 'meer kopen';
ALL.forEach((d, i) => { d.i = i; d.search = norm([d.title, d.deal_text, d.size, d.category, d.store].join(' ')); });

// ---------- storage (may be unavailable, e.g. private mode)
const store = {
  get(k, def){ try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch(e){ return def; } },
  set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }
};

// ---------- state
const S = { tab:'deze', q:'', type:'', sort:'pct', min:0, cat:'', off:new Set(), cmp:false, shown:120 };
let favs = store.get('bonus_favs', {terms:[], keys:[]});

function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get('t')) S.tab = p.get('t');
  S.q = p.get('q') || ''; S.type = p.get('type') || ''; S.sort = p.get('sort') || 'pct';
  S.min = +(p.get('min') || 0); S.cat = p.get('cat') || ''; S.cmp = p.get('cmp') === '1';
  if (p.get('only')) { const keep = new Set(p.get('only').split('|')); S.off = new Set(Object.keys(DATA.stores).filter(s => !keep.has(s))); }
  $('q').value = S.q; $('type').value = S.type; $('sort').value = S.sort; $('min').value = S.min; $('cmp').checked = S.cmp;
}
function writeHash(){
  const p = new URLSearchParams();
  if (S.tab !== 'deze') p.set('t', S.tab);
  if (S.q) p.set('q', S.q); if (S.type) p.set('type', S.type);
  if (S.sort !== 'pct') p.set('sort', S.sort); if (S.min) p.set('min', S.min);
  if (S.cat) p.set('cat', S.cat); if (S.cmp) p.set('cmp', '1');
  if (S.off.size) p.set('only', Object.keys(DATA.stores).filter(s => !S.off.has(s)).join('|'));
  const h = p.toString();
  try { history.replaceState(null, '', h ? '#' + h : location.pathname + location.search); } catch(e){}
}

// ---------- favorites
const isFav = d => favs.keys.includes(d.key) || favs.terms.some(t => norm(t).split(/\s+/).every(w => d.search.includes(w)));
function saveFavs(){ store.set('bonus_favs', favs); }
function toggleStar(i){
  const d = ALL[i];
  if (favs.keys.includes(d.key)) favs.keys = favs.keys.filter(k => k !== d.key);
  else favs.keys.push(d.key);
  saveFavs(); render(false);
}
$('favform').onsubmit = e => {
  e.preventDefault();
  const v = $('favin').value.trim();
  if (v && !favs.terms.includes(v)) { favs.terms.push(v); saveFavs(); }
  $('favin').value = ''; render();
};

// ---------- filtering
function base(){            // everything except the store/category chips, for the chip counts
  const words = norm(S.q).split(/\s+/).filter(Boolean);
  return ALL.filter(d =>
    (S.tab === 'fav' ? isFav(d) : d.week === S.tab) &&
    (!S.type || d.deal_type === S.type) &&
    (d.effective_pct || 0) >= S.min &&
    words.every(w => d.search.includes(w)));
}
const sorters = {
  pct: (a,b) => (multi(a) - multi(b)) || ((b.discount_pct ?? b.effective_pct ?? 0) - (a.discount_pct ?? a.effective_pct ?? 0)),
  eff: (a,b) => (b.effective_pct||0) - (a.effective_pct||0),
  // per kg / per liter first (cheapest first), per piece after that, unknown last
  unit: (a,b) => ((a.unit_price == null) - (b.unit_price == null)) || ((a.unit === 'st') - (b.unit === 'st')) || ((a.unit_price ?? 0) - (b.unit_price ?? 0)),
  price: (a,b) => (a.pay ?? 1e9) - (b.pay ?? 1e9),
  store: (a,b) => a.store.localeCompare(b.store) || a.title.localeCompare(b.title),
  title: (a,b) => a.title.localeCompare(b.title),
};

// ---------- rendering pieces
function badge(d){
  if (multi(d)) return d.effective_pct ? `<span class="pct multi">-${d.effective_pct}% bij ${d.min_qty}</span>` : '';
  return d.discount_pct ? `<span class="pct">-${d.discount_pct}%</span>` : '';
}
function prices(d){
  const unit = d.unit_price ? `<span class="per">${eur(d.unit_price)}/${d.unit}</span>` : '';
  if (!multi(d)) return `<div class="prices"><span class="now">${eur(d.price_now)}</span><span class="was">${eur(d.price_was)}</span>${unit}</div>`;
  const normal = d.price_was ?? d.price_now;
  const per = d.pay && normal && d.pay < normal ? `<span class="per">${eur(d.pay)} p/st bij ${d.min_qty}</span>` : '';
  return `<div class="prices"><span class="now">${eur(normal)}</span>${per}${unit}</div>`;
}
function tags(d){
  const t = [...(d.tags||[])];
  if (S.tab === 'fav' && d.week === 'volgende') t.unshift('Volgende week');
  if (!t.length) return '';
  return `<div class="tags">${t.map(x => `<span class="tag ${x.startsWith('Beste') ? 'best' : x === 'Nieuw' || x === 'Volgende week' ? 'new' : ''}">${esc(x)}</span>`).join('')}</div>`;
}
function card(d){
  const fav = isFav(d);
  return `<div class="card${fav ? ' isfav' : ''}">
    <button class="star${favs.keys.includes(d.key) ? ' on' : ''}" data-i="${d.i}" title="Bewaar in Mijn lijst">${favs.keys.includes(d.key) ? '★' : '☆'}</button>
    ${badge(d)}
    <a class="img${d.image ? ' has' : ''}" href="${esc(d.url)}" target="_blank" rel="noopener">${d.image ? `<img loading="lazy" src="${esc(d.image)}" alt="">` : ''}</a>
    <div class="store">${esc(d.store)}</div>
    <a class="title" href="${esc(d.url)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">${esc(d.title)}</a>
    ${d.size ? `<div class="size">${esc(d.size)}</div>` : ''}
    ${d.deal_text ? `<div class="deal ${multi(d) ? 'multi' : ''}">${esc(d.deal_text)}</div>` : ''}
    ${multi(d) ? `<div class="qty">Alleen bij ${d.min_qty} stuks</div>` : ''}
    ${prices(d)}
    ${tags(d)}
    ${d.valid_until ? `<div class="until">${d.valid_from && d.week === 'volgende' ? 'vanaf ' + esc(d.valid_from) + ' ' : ''}t/m ${esc(d.valid_until)}</div>` : ''}
  </div>`;
}
function compareCard(members){
  const rows = [...members].sort((a,b) => (a.unit_price && b.unit_price) ? a.unit_price - b.unit_price : (a.pay ?? 1e9) - (b.pay ?? 1e9));
  const first = rows.find(d => d.image) || rows[0];
  const name = rows.map(d => d.title).sort((a,b) => a.length - b.length)[0];
  return `<div class="card cmp">
    <div style="display:flex;gap:10px;align-items:center">
      <div class="img${first.image ? ' has' : ''}" style="height:60px;width:60px;flex:none">${first.image ? `<img loading="lazy" src="${esc(first.image)}" alt="" style="max-height:60px">` : ''}</div>
      <div><div class="title">${esc(name)}</div><div class="size">${rows.length} winkels · ${esc(rows[0].category)}</div></div>
    </div>
    <div class="rows">${rows.map((d, i) => `
      <a class="row${i === 0 ? ' best' : ''}" href="${esc(d.url)}" target="_blank" rel="noopener">
        <span class="s">${esc(d.store)}</span><span class="p">${eur(d.pay)}${multi(d) ? ' p/st' : ''}</span>
        <span class="d">${esc(d.deal_text || d.size || '')}${multi(d) ? ' · bij ' + d.min_qty + ' st' : ''}</span>
        <span class="u">${d.unit_price ? eur(d.unit_price) + '/' + d.unit : ''}</span>
      </a>`).join('')}</div>
  </div>`;
}

function chipsRow(el, items, active, onClick){
  el.innerHTML = items.map(([key, label, n, cls]) =>
    `<span class="chip ${cls||''}${active(key) ? ' on' : ''}" data-k="${esc(key)}">${esc(label)}<span class="n">${n}</span></span>`).join('');
  el.querySelectorAll('.chip').forEach(c => c.onclick = e => onClick(c.dataset.k, e));
}

function render(resetPaging = true){
  if (resetPaging) S.shown = 120;
  const b = base();

  // tabs
  const count = t => ALL.filter(d => t === 'fav' ? isFav(d) : d.week === t).length;
  const nNext = count('volgende');
  const tabs = [['deze', 'Deze week', count('deze')]];
  if (nNext) tabs.push(['volgende', 'Volgende week', nNext]);
  tabs.push(['fav', '★ Mijn lijst', count('fav')]);
  if (S.tab === 'volgende' && !nNext) S.tab = 'deze';
  $('tabs').innerHTML = tabs.map(([k, l, n]) => `<button class="tab${S.tab === k ? ' on' : ''}" data-t="${k}">${l}<span class="n">${n}</span></button>`).join('');
  $('tabs').querySelectorAll('.tab').forEach(t => t.onclick = () => { S.tab = t.dataset.t; render(); });

  // my list
  $('fav').classList.toggle('show', S.tab === 'fav');
  $('terms').innerHTML = favs.terms.map((t, i) => `<span class="chip term">${esc(t)}<b data-i="${i}" title="Verwijder">×</b></span>`).join('')
    + (favs.keys.length ? `<span class="chip term">${favs.keys.length} bewaarde producten<b data-k="1" title="Wis alle bewaarde producten">×</b></span>` : '');
  $('terms').querySelectorAll('b').forEach(x => x.onclick = () => {
    if (x.dataset.k) { if (confirmClear()) favs.keys = []; } else favs.terms.splice(+x.dataset.i, 1);
    saveFavs(); render();
  });

  // category chips (counted within current store selection)
  const inStores = b.filter(d => !S.off.has(d.store));
  const catCount = {};
  inStores.forEach(d => catCount[d.category] = (catCount[d.category]||0) + 1);
  const cats = Object.keys(catCount).sort((a,b) => (a === 'Overig') - (b === 'Overig') || catCount[b] - catCount[a]);
  chipsRow($('cats'), [['', 'Alles', inStores.length], ...cats.map(c => [c, c, catCount[c]])],
    k => S.cat === k, k => { S.cat = k; render(); });

  // store chips (counted within current category)
  const inCat = b.filter(d => !S.cat || d.category === S.cat);
  const stCount = {};
  inCat.forEach(d => stCount[d.store] = (stCount[d.store]||0) + 1);
  const names = Object.keys(DATA.stores).sort();
  chipsRow($('stores'), names.map(n => [n, n, stCount[n]||0, DATA.stores[n].count ? '' : 'err']),
    k => !S.off.has(k), (k, e) => {
      if (e.shiftKey || e.metaKey || e.ctrlKey || S.off.size === 0) {
        S.off = new Set(names.filter(x => x !== k));          // show only this store
      } else if (S.off.has(k)) {
        S.off.delete(k);                                        // add it back
      } else {
        S.off.add(k);                                           // hide it
        if (S.off.size === names.length) S.off.clear();         // nothing left: show all again
      }
      render();
    });
  if (S.off.size) $('stores').insertAdjacentHTML('beforeend', '<span class="chip" id="allst">Alle winkels</span>');
  if ($('allst')) $('allst').onclick = () => { S.off.clear(); render(); };

  // the list
  let list = inCat.filter(d => !S.off.has(d.store)).sort(sorters[S.sort]);
  let html, total;
  if (S.cmp) {
    const groups = {};
    ALL.forEach(d => { if (d.group) (groups[d.group] ||= []).push(d); });
    const hit = new Set(list.filter(d => d.group).map(d => d.group));
    const blocks = [...hit].map(g => groups[g].filter(d => d.week === (S.tab === 'fav' ? d.week : S.tab) && !S.off.has(d.store)))
                           .filter(m => new Set(m.map(d => d.store)).size >= 2);
    blocks.sort((a,b) => Math.max(...b.map(d => d.effective_pct||0)) - Math.max(...a.map(d => d.effective_pct||0)));
    total = blocks.length;
    html = blocks.slice(0, S.shown).map(compareCard).join('');
    $('sub').textContent = `${total} producten bij meerdere winkels · bijgewerkt ${DATA.generated.replace('T',' ')}`;
  } else {
    total = list.length;
    html = list.slice(0, S.shown).map(card).join('');
    $('sub').textContent = `${total} van ${ALL.filter(d => d.week === 'deze').length} aanbiedingen · bijgewerkt ${DATA.generated.replace('T',' ')}`;
  }
  if (!total) html = `<div class="empty">${S.tab === 'fav' && !favs.terms.length && !favs.keys.length
      ? 'Je lijst is nog leeg. Voeg hierboven een product toe of tik op ☆ bij een aanbieding.'
      : S.cmp ? 'Geen producten gevonden die bij meerdere winkels in de aanbieding zijn.' : 'Geen aanbiedingen gevonden.'}</div>`;
  if (total > S.shown) html += `<button class="more" id="more">Toon meer (${total - S.shown})</button>`;
  $('grid').innerHTML = html;
  if ($('more')) $('more').onclick = () => { S.shown += 120; render(false); };
  $('grid').querySelectorAll('.star').forEach(s => s.onclick = e => { e.preventDefault(); toggleStar(+s.dataset.i); });
  writeHash();
}
function confirmClear(){ try { return window.confirm('Alle bewaarde producten wissen?'); } catch(e){ return true; } }

// ---------- warnings
if ((DATA.warnings||[]).length) {
  $('warn').innerHTML = `<details class="warn"><summary>⚠ ${DATA.warnings.length} winkel${DATA.warnings.length > 1 ? 's' : ''} gaf vandaag minder resultaten dan normaal</summary>
    <ul>${DATA.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>`;
}

// ---------- share + theme
function toast(msg){ const t = $('toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 1800); }
$('share').onclick = async () => {
  const url = location.href;
  try {
    if (navigator.share && matchMedia('(max-width:640px)').matches) { await navigator.share({title: 'Aanbiedingen', url}); return; }
    await navigator.clipboard.writeText(url); toast('Link gekopieerd');
  } catch(e) { prompt('Kopieer deze link:', url); }
};
function applyTheme(t){ document.documentElement.dataset.theme = t; $('theme').textContent = t === 'dark' ? '☀️' : '🌙';
  document.querySelector('meta[name=theme-color]').content = t === 'dark' ? '#161615' : '#f6f5f2'; }
let theme = store.get('bonus_theme', null) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
applyTheme(theme);
$('theme').onclick = () => { theme = theme === 'dark' ? 'light' : 'dark'; store.set('bonus_theme', theme); applyTheme(theme); };

// ---------- inputs
let typing;
$('q').addEventListener('input', () => { clearTimeout(typing); typing = setTimeout(() => { S.q = $('q').value; render(); }, 150); });
$('type').onchange = () => { S.type = $('type').value; render(); };
$('sort').onchange = () => { S.sort = $('sort').value; render(); };
$('min').onchange = () => { S.min = +$('min').value; render(); };
$('cmp').onchange = () => { S.cmp = $('cmp').checked; render(); };
window.addEventListener('hashchange', () => { readHash(); render(); });

readHash();
render();
</script></body></html>
"""


def write_html(payload: dict, path: Path):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
