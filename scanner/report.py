"""Write one self-contained HTML page with all deals.

App-style layout: one search box, a bottom tab bar on phones (Deals, Goedkoopst, Volgende
week, Mijn lijst), a filter panel with big toggle buttons, and product tiles that open the
product when tapped. Prices are drawn like Dutch shelf labels on a deal sticker.

Features: categories, stores, deal type, sorting (incl. price per kg/l), compare-stores
view, favorites (saved per device), price-history tags, shareable filter links, dark mode,
store health warnings, and the Goedkoopst search over all regular prices (prices.js).
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = r"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f3f5f2">
<title>Bonus</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f3f5f2; --tile:#ffffff; --ink:#17201b; --soft:#5d6862; --line:#dfe4de; --field:#e8ece7;
  --green:#1d7a4c; --green-ink:#ffffff; --greenbg:#e2f1e8;
  --sticker:#ffd23f; --sticker-ink:#17201b; --blue:#2f5bd3; --bluebg:#e6ecfb;
  --warnbg:#fff3cf; --warn:#6b4e00;
  --r-tile:18px; --r-ctl:12px;
  --font:"Archivo", system-ui, -apple-system, "Segoe UI", sans-serif;
}
[data-theme=dark]{
  --bg:#111613; --tile:#1a201c; --ink:#e9eee9; --soft:#9aa59e; --line:#2b332e; --field:#232a25;
  --green:#46b37c; --green-ink:#0c1a12; --greenbg:#18301f; --sticker:#ffd23f; --sticker-ink:#17201b;
  --blue:#7c9cff; --bluebg:#1c2541; --warnbg:#3a3010; --warn:#ffdc7a;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:400 15px/1.45 var(--font);font-stretch:100%;background:var(--bg);color:var(--ink);
     padding-bottom:calc(76px + env(safe-area-inset-bottom))}
button,input{font:inherit;color:inherit}
button{cursor:pointer;-webkit-tap-highlight-color:transparent}
:focus-visible{outline:3px solid var(--green);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

/* ---------- top bar */
.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 92%,transparent);
     backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.wrap{max-width:1180px;margin:0 auto;padding:0 18px}
.bar1{display:flex;align-items:center;gap:10px;padding:12px 0 8px}
.brand{font-weight:850;font-stretch:75%;font-size:26px;letter-spacing:-.01em;margin:0;flex:1;line-height:1}
.brand small{display:block;font-weight:450;font-stretch:100%;font-size:12.5px;color:var(--soft);letter-spacing:0;margin-top:3px}
.icon{width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:var(--tile);
      display:grid;place-items:center;flex:none}
.icon svg{width:20px;height:20px}
.search{position:relative;padding-bottom:10px}
.search svg{position:absolute;left:14px;top:13px;width:20px;height:20px;color:var(--soft);pointer-events:none}
.search input{width:100%;height:46px;border:0;border-radius:23px;background:var(--field);padding:0 44px 0 44px;font-size:16px}
.search input::placeholder{color:var(--soft)}
.search .clear{position:absolute;right:6px;top:5px;width:36px;height:36px;border:0;border-radius:50%;background:transparent;
               display:none;place-items:center;color:var(--soft)}
.search.has .clear{display:grid}
.rows{padding-bottom:10px;display:flex;flex-direction:column;gap:8px}
.chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;margin:0 -18px;padding:0 18px}
.chips::-webkit-scrollbar{display:none}
.chip{flex:none;height:36px;padding:0 14px;border-radius:18px;border:1px solid var(--line);background:var(--tile);
      display:inline-flex;align-items:center;gap:7px;font-size:14px;font-weight:550;white-space:nowrap}
.chip .n{font-weight:450;color:var(--soft);font-size:12.5px}
.chip.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.chip.on .n{color:var(--bg);opacity:.7}
.chip.off{opacity:.45}
.chip .dot{width:9px;height:9px;border-radius:50%;flex:none;box-shadow:0 0 0 1.5px var(--tile)}
.chip.filter{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chip.filter .badge{background:var(--sticker);color:var(--sticker-ink);border-radius:9px;min-width:18px;height:18px;
                    display:inline-grid;place-items:center;font-size:11.5px;font-weight:800;padding:0 5px}
.chip svg{width:16px;height:16px}
.toggles{display:flex;gap:8px;flex-wrap:wrap}

/* ---------- desktop tabs */
.tabs{display:none}
@media (min-width:860px){
  body{padding-bottom:30px}
  .tabs{display:flex;gap:4px;background:var(--field);border-radius:14px;padding:4px}
  .tabs .tab{border:0;background:transparent;border-radius:10px;height:36px;padding:0 14px;font-weight:600;font-size:14px;
             display:flex;align-items:center;gap:7px;color:var(--soft)}
  .tabs .tab.on{background:var(--tile);color:var(--ink);box-shadow:0 1px 2px rgba(23,32,27,.12)}
  .tabs .tab svg{width:17px;height:17px}
  .navbar{display:none!important}
}

/* ---------- bottom tab bar (phones) */
.navbar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--tile);border-top:1px solid var(--line);
        display:grid;grid-template-columns:repeat(4,1fr);padding-bottom:env(safe-area-inset-bottom)}
.navbar .tab{border:0;background:none;height:62px;display:flex;flex-direction:column;align-items:center;justify-content:center;
             gap:3px;font-size:11.5px;font-weight:600;color:var(--soft);position:relative}
.navbar .tab svg{width:23px;height:23px}
.navbar .tab.on{color:var(--green)}
.navbar .tab.on::before{content:"";position:absolute;top:0;left:30%;right:30%;height:3px;border-radius:0 0 3px 3px;background:var(--green)}
.navbar .tab .cnt{position:absolute;top:7px;left:calc(50% + 7px);background:var(--sticker);color:var(--sticker-ink);
                  font-size:10.5px;font-weight:800;min-width:17px;height:17px;border-radius:9px;display:grid;place-items:center;padding:0 4px}

/* ---------- status line, warnings, my-list */
.status{max-width:1180px;margin:0 auto;padding:14px 18px 2px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}
.status h2{margin:0;font-size:20px;font-weight:800;font-stretch:87%}
.status p{margin:0;color:var(--soft);font-size:13.5px}
.notice{max-width:1180px;margin:10px auto 0;padding:0 18px}
.notice details{background:var(--warnbg);color:var(--warn);border-radius:var(--r-ctl);padding:10px 14px;font-size:14px}
.notice summary{cursor:pointer;font-weight:600}
.notice ul{margin:8px 0 2px;padding-left:18px}
.listbox{max-width:1180px;margin:12px auto 0;padding:0 18px;display:none}
.listbox.show{display:block}
.listbox form{display:flex;gap:8px}
.listbox input{flex:1;height:44px;border:1px solid var(--line);background:var(--tile);border-radius:var(--r-ctl);padding:0 14px;font-size:15px}
.btn{height:44px;border:0;border-radius:var(--r-ctl);padding:0 18px;font-weight:700;background:var(--green);color:var(--green-ink)}
.btn.ghost{background:var(--field);color:var(--ink)}
.terms{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.term{height:34px;border-radius:17px;background:var(--greenbg);color:var(--green);font-weight:650;font-size:14px;
      display:inline-flex;align-items:center;gap:2px;padding:0 4px 0 13px}
.term button{border:0;background:none;width:28px;height:28px;border-radius:50%;color:inherit;display:grid;place-items:center}
.term button svg{width:14px;height:14px}
.hint{color:var(--soft);font-size:13px;margin:8px 0 0}

/* ---------- product tiles */
main{max-width:1180px;margin:0 auto;padding:14px 18px 24px;display:grid;
     grid-template-columns:repeat(auto-fill,minmax(205px,1fr));gap:14px}
@media (max-width:859px){ .top{position:static} }
@media (max-width:560px){ main{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:12px 12px 20px}
  .wrap{padding:0 12px} .chips{margin:0 -12px;padding:0 12px} }
.card{position:relative;background:var(--tile);border:1px solid var(--line);border-radius:var(--r-tile);
      padding:10px 10px 12px;display:flex;flex-direction:column;gap:6px;min-width:0}
.card:has(.go:hover){border-color:var(--soft)}
.card.isfav{border-color:var(--green)}
.go{position:absolute;inset:0;border-radius:var(--r-tile);z-index:1}
.go:focus-visible{outline-offset:-3px}
.pic{aspect-ratio:1/1;border-radius:12px;background:#fff;display:grid;place-items:center;overflow:hidden;margin-bottom:2px}
[data-theme=dark] .pic{background:#f2f4f1}
.pic img{width:86%;height:86%;object-fit:contain}
.pic .ph{font-weight:850;font-stretch:70%;font-size:34px;color:#c9d0ca}
.star{position:absolute;top:14px;right:14px;z-index:2;width:38px;height:38px;border-radius:50%;border:0;
      background:rgba(255,255,255,.92);display:grid;place-items:center;color:#5d6862;box-shadow:0 0 0 1px rgba(23,32,27,.08)}
.star svg{width:19px;height:19px}
.star.on{color:#d39b00}
.star.on svg{fill:currentColor}
.who{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--soft);font-weight:550}
.who .dot{width:9px;height:9px;border-radius:50%;flex:none}
.name{font-weight:650;font-size:14.5px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.size{font-size:12.5px;color:var(--soft)}
.priceline{margin-top:auto;display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap;padding-top:4px}
/* the shelf-label price */
.tag{display:inline-flex;align-items:flex-start;line-height:.82;font-weight:880;font-stretch:68%;letter-spacing:-.01em;
     background:var(--sticker);color:var(--sticker-ink);padding:6px 8px 5px 8px;border-radius:8px 8px 8px 2px}
.tag .eu{font-size:31px}
.tag .ct{font-size:16px;margin-left:1px;margin-top:1px}
.tag.plain{background:transparent;padding-left:0;color:var(--ink)}
.tag.multi{background:var(--blue);color:#fff}
.tag.sm .eu{font-size:23px}.tag.sm .ct{font-size:13px}
.was{color:var(--soft);font-size:13px;text-decoration:line-through;padding-bottom:3px}
.per{color:var(--soft);font-size:12.5px;padding-bottom:3px}
.deal{align-self:flex-start;font-weight:750;font-size:13px;border-radius:7px;padding:3px 8px;background:var(--warnbg);color:var(--warn)}
.deal.multi{background:var(--bluebg);color:var(--blue)}
.need{font-size:12.5px;color:var(--blue);font-weight:600}
.flags{display:flex;flex-wrap:wrap;gap:5px}
.flag{font-size:11.5px;font-weight:600;border-radius:6px;padding:2px 7px;background:var(--field);color:var(--soft)}
.flag.best{background:var(--greenbg);color:var(--green)}
.until{font-size:12px;color:var(--soft)}
.pct{position:absolute;top:14px;left:14px;z-index:2;font-weight:850;font-stretch:75%;font-size:15px;
     background:#17201b;color:#fff;border-radius:9px;padding:4px 8px}
.pct.multi{background:var(--blue);color:#fff}

/* compare view */
.cmp{grid-column:span 2;cursor:default}
@media (max-width:560px){ .cmp{grid-column:1/-1} }
.cmp .head{display:flex;gap:12px;align-items:center}
.cmp .pic{width:64px;flex:none;margin:0}
.cmp .rows2{display:flex;flex-direction:column;gap:4px;margin-top:6px}
.row{position:relative;z-index:2;display:grid;grid-template-columns:1fr auto;gap:0 10px;align-items:center;
     padding:8px 10px;border-radius:10px;text-decoration:none;color:inherit;background:var(--bg)}
.row.best{background:var(--greenbg)}
.row .s{display:flex;align-items:center;gap:7px;font-weight:650;font-size:14px}
.row .d{grid-column:1;font-size:12.5px;color:var(--soft)}
.row .p{grid-row:1/3;grid-column:2;text-align:right}
.row .u{display:block;font-size:12px;color:var(--soft);margin-top:2px}

/* goedkoopst list */
.grp{grid-column:1/-1;margin:12px 0 0;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px}
.grp h3{margin:0;font-size:18px;font-weight:800;font-stretch:87%}
.grp span{color:var(--soft);font-size:13px}
.prow{grid-column:1/-1;position:relative;display:grid;grid-template-columns:1fr auto;gap:2px 14px;align-items:center;
      background:var(--tile);border:1px solid var(--line);border-radius:var(--r-tile);padding:12px 14px;color:inherit;text-decoration:none}
.prow:hover{border-color:var(--soft)}
.prow.top{border:2px solid var(--green)}
.prow .pic{width:56px;margin:0;border-radius:10px;font-size:14px}
.prow .pic .ph{font-size:22px}
.prow .who{margin-bottom:1px}
.prow .name{font-size:14.5px}
.prow .right{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.prow .right .sub{font-size:12.5px;color:var(--soft);white-space:nowrap}
.prow .winner{position:absolute;top:-10px;left:12px;background:var(--green);color:var(--green-ink);font-size:11.5px;font-weight:750;
              border-radius:6px;padding:2px 8px}
.prow.top{padding-top:16px}
.suggest{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px}

.empty{grid-column:1/-1;text-align:center;color:var(--soft);padding:50px 12px;font-size:15px}
.empty b{color:var(--ink)}
.more{grid-column:1/-1;justify-self:center;margin-top:6px}

/* ---------- filter sheet */
.scrim{position:fixed;inset:0;background:rgba(10,16,12,.45);z-index:40;opacity:0;pointer-events:none;transition:opacity .2s}
.sheet{position:fixed;left:0;right:0;bottom:0;z-index:41;background:var(--tile);border-radius:22px 22px 0 0;
       max-height:86vh;overflow:auto;padding:8px 18px calc(18px + env(safe-area-inset-bottom));
       transform:translateY(105%);transition:transform .25s cubic-bezier(.2,.8,.2,1)}
@media (min-width:860px){ .sheet{left:50%;right:auto;width:520px;bottom:auto;top:50%;border-radius:22px;
       transform:translate(-50%,-46%);opacity:0;pointer-events:none;transition:opacity .18s,transform .18s} }
.sheet-open .scrim{opacity:1;pointer-events:auto}
.sheet-open .sheet{transform:translateY(0)}
@media (min-width:860px){ .sheet-open .sheet{transform:translate(-50%,-50%);opacity:1;pointer-events:auto} }
.grab{width:40px;height:5px;border-radius:3px;background:var(--line);margin:4px auto 10px}
.sheet h3{margin:0 0 4px;font-size:20px;font-weight:800;font-stretch:87%}
.sheet h4{margin:18px 0 8px;font-size:14px;font-weight:700}
.seg{display:flex;flex-wrap:wrap;gap:8px}
.seg button{height:42px;padding:0 15px;border-radius:var(--r-ctl);border:1px solid var(--line);background:var(--tile);font-weight:600;font-size:14px}
.seg button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.switch{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 0;border-top:1px solid var(--line);margin-top:18px;cursor:pointer}
.switch span{font-weight:600}
.switch small{display:block;color:var(--soft);font-weight:400;font-size:13px}
.switch input{appearance:none;-webkit-appearance:none;width:50px;height:30px;border-radius:15px;background:var(--line);position:relative;flex:none;cursor:pointer;transition:background .15s}
.switch input::after{content:"";position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;background:#fff;transition:transform .15s;box-shadow:0 1px 2px rgba(0,0,0,.2)}
.switch input:checked{background:var(--green)}
.switch input:checked::after{transform:translateX(20px)}
.sheet .actions{display:flex;gap:10px;margin-top:16px}
.sheet .actions .btn{flex:1}

.toast{position:fixed;bottom:calc(90px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%) translateY(10px);
       background:var(--ink);color:var(--bg);padding:10px 18px;border-radius:12px;font-size:14px;font-weight:600;
       opacity:0;transition:opacity .2s,transform .2s;pointer-events:none;z-index:60}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.credit{max-width:1180px;margin:0 auto;padding:0 18px 20px;color:var(--soft);font-size:12.5px}
.credit a{color:inherit}
</style></head><body>

<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="i-tag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></symbol>
  <symbol id="i-cal" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/></symbol>
  <symbol id="i-star" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z"/></symbol>
  <symbol id="i-sliders" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></symbol>
  <symbol id="i-share" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></symbol>
</svg>

<header class="top">
  <div class="wrap">
    <div class="bar1">
      <h1 class="brand">Bonus<small id="updated"></small></h1>
      <nav class="tabs" id="tabsTop" aria-label="Weergave"></nav>
      <button class="icon" id="share" aria-label="Link naar deze selectie delen"><svg><use href="#i-share"/></svg></button>
      <button class="icon" id="theme" aria-label="Donkere modus"><svg><use href="#i-moon"/></svg></button>
    </div>
    <div class="search" id="searchbox">
      <svg><use href="#i-search"/></svg>
      <input type="search" id="q" autocomplete="off" enterkeyhint="search">
      <button class="clear" id="qclear" aria-label="Zoekveld leegmaken"><svg width="18" height="18"><use href="#i-x"/></svg></button>
    </div>
    <div class="rows" id="filterrows">
      <div class="chips" id="cats"></div>
      <div class="chips" id="stores"></div>
    </div>
    <div class="rows" id="cheaprows" hidden>
      <div class="toggles">
        <button class="chip" id="cmultiBtn" aria-pressed="true">Ook 1+1-deals meetellen</button>
        <button class="chip" id="cperBtn" aria-pressed="true">Beste per winkel</button>
      </div>
    </div>
  </div>
</header>

<div class="notice" id="warn"></div>
<section class="listbox" id="fav">
  <form id="favform"><input id="favin" placeholder="Wat wil je in de gaten houden? bv. pepsi max" autocomplete="off">
    <button class="btn">Toevoegen</button></form>
  <div class="terms" id="terms"></div>
  <p class="hint">Of tik op de ster bij een product. Je lijst blijft op dit apparaat.</p>
</section>
<div class="status"><h2 id="heading"></h2><p id="sub"></p></div>
<main id="grid"></main>
<p class="credit" id="credit"></p>

<nav class="navbar" id="tabsBottom" aria-label="Weergave"></nav>

<div class="scrim" id="scrim"></div>
<section class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheetTitle">
  <div class="grab"></div>
  <h3 id="sheetTitle">Filters</h3>
  <h4>Soort aanbieding</h4>
  <div class="seg" id="segType"></div>
  <h4>Sorteren op</h4>
  <div class="seg" id="segSort"></div>
  <h4>Minimale korting</h4>
  <div class="seg" id="segMin"></div>
  <label class="switch"><span>Vergelijk winkels<small>Hetzelfde product bij meerdere winkels naast elkaar</small></span>
    <input type="checkbox" id="cmp"></label>
  <div class="actions"><button class="btn ghost" id="reset">Wis filters</button><button class="btn" id="done">Toon resultaten</button></div>
</section>
<div class="toast" id="toast" role="status"></div>

<script>
const DATA = __DATA__;
const ALL = DATA.deals;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eur = v => v == null ? '' : '€' + v.toFixed(2).replace('.', ',');
const norm = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
const multi = d => d.deal_type === 'meer kopen';
const icon = (id, cls='') => `<svg class="${cls}"><use href="#i-${id}"/></svg>`;
ALL.forEach((d, i) => { d.i = i; d.search = norm([d.title, d.deal_text, d.size, d.category, d.store].join(' ')); });

// store colours: only a small dot, so stores are easy to tell apart at a glance
const STORE_COLOR = {'Albert Heijn':'#00a0e2','Jumbo':'#f5b800','Lidl':'#0050aa','Aldi':'#1c3f94','PLUS':'#e2001a',
  'Dirk':'#d6001c','Hoogvliet':'#f07d00','Etos':'#c4007a','Kruidvat':'#e30613','DekaMarkt':'#c8102e','Vomar':'#ef3e33',
  'Spar':'#00843d','Action':'#0071ce','Gall & Gall':'#3b2a20','Makro':'#002d72','Coop':'#f39200','Poiesz':'#d71920','Ekoplaza':'#6aa84f'};
const dot = s => `<span class="dot" style="background:${STORE_COLOR[s] || '#8a948e'}"></span>`;

// a price drawn like a shelf label: big euros, small raised cents
function tag(v, cls=''){
  if (v == null) return '';
  const [e, c] = v.toFixed(2).split('.');
  return `<span class="tag ${cls}" aria-label="${eur(v)}"><span class="eu">${e}</span><span class="ct">${c}</span></span>`;
}

// ---------- storage (may be unavailable, e.g. private mode)
const store = {
  get(k, def){ try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch(e){ return def; } },
  set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }
};

// ---------- state
const STORES = Object.keys(DATA.stores).sort();
const S = { tab:'deze', q:'', type:'', sort:'pct', min:0, cat:'', only:new Set(), cmp:false, shown:60,
            cq:'', cmulti:true, cper:true };
let favs = store.get('bonus_favs', {terms:[], keys:[]});

function readHash(){
  const p = new URLSearchParams(location.hash.slice(1));
  S.tab = p.get('t') || 'deze';
  S.q = p.get('q') || ''; S.type = p.get('type') || ''; S.sort = p.get('sort') || 'pct';
  S.min = +(p.get('min') || 0); S.cat = p.get('cat') || ''; S.cmp = p.get('cmp') === '1';
  S.only = new Set(p.get('only') ? p.get('only').split('|') : []);
  S.cq = p.get('cq') || ''; S.cmulti = p.get('cmulti') !== '0'; S.cper = p.get('cper') !== '0';
  $('cmp').checked = S.cmp;
}
function writeHash(){
  const p = new URLSearchParams();
  if (S.tab !== 'deze') p.set('t', S.tab);
  if (S.q) p.set('q', S.q); if (S.type) p.set('type', S.type);
  if (S.sort !== 'pct') p.set('sort', S.sort); if (S.min) p.set('min', S.min);
  if (S.cat) p.set('cat', S.cat); if (S.cmp) p.set('cmp', '1');
  if (S.only.size) p.set('only', [...S.only].join('|'));
  if (S.cq) p.set('cq', S.cq); if (!S.cmulti) p.set('cmulti', '0'); if (!S.cper) p.set('cper', '0');
  const h = p.toString();
  try { history.replaceState(null, '', h ? '#' + h : location.pathname + location.search); } catch(e){}
}

// ---------- favorites
const isFav = d => favs.keys.includes(d.key) || favs.terms.some(t => norm(t).split(/\s+/).every(w => d.search.includes(w)));
const saveFavs = () => store.set('bonus_favs', favs);
function toggleStar(i){
  const d = ALL[i];
  const on = favs.keys.includes(d.key);
  favs.keys = on ? favs.keys.filter(k => k !== d.key) : [...favs.keys, d.key];
  saveFavs(); toast(on ? 'Uit je lijst gehaald' : 'Bewaard in Mijn lijst'); render(false);
}
$('favform').onsubmit = e => {
  e.preventDefault();
  const v = $('favin').value.trim();
  if (v && !favs.terms.includes(v)) { favs.terms.push(v); saveFavs(); }
  $('favin').value = ''; render();
};

// ---------- filtering
function base(){          // everything except the store/category chips, for the chip counts
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
  unit: (a,b) => ((a.unit_price == null) - (b.unit_price == null)) || ((a.unit === 'st') - (b.unit === 'st')) || ((a.unit_price ?? 0) - (b.unit_price ?? 0)),
  price: (a,b) => (a.pay ?? 1e9) - (b.pay ?? 1e9),
  store: (a,b) => a.store.localeCompare(b.store) || a.title.localeCompare(b.title),
  title: (a,b) => a.title.localeCompare(b.title),
};
const OPTIONS = {
  type: [['', 'Alles'], ['korting', 'Korting op 1 stuk'], ['meer kopen', 'Meer kopen (1+1 e.d.)']],
  sort: [['pct', 'Meeste korting'], ['eff', 'Meeste korting, ook 1+1'], ['unit', 'Laagste kilo- of literprijs'],
         ['price', 'Laagste prijs'], ['store', 'Winkel'], ['title', 'Naam']],
  min: [[0, 'Alles'], [20, '20%+'], [30, '30%+'], [40, '40%+'], [50, '50%+']],
};
const activeFilters = () => (S.type ? 1 : 0) + (S.sort !== 'pct' ? 1 : 0) + (S.min ? 1 : 0) + (S.cmp ? 1 : 0);

// ---------- tiles
function pictureOf(d){
  return d.image ? `<img loading="lazy" src="${esc(d.image)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'ph',textContent:'${esc((d.store||'?')[0])}'}))">`
                 : `<span class="ph">${esc((d.store||'?')[0])}</span>`;
}
function badge(d){
  if (multi(d)) return d.effective_pct ? `<span class="pct multi">-${d.effective_pct}% bij ${d.min_qty}</span>` : '';
  return d.discount_pct ? `<span class="pct">-${d.discount_pct}%</span>` : '';
}
function priceBlock(d){
  const unit = d.unit_price ? `<span class="per">${eur(d.unit_price)}/${d.unit}</span>` : '';
  if (!multi(d)) {
    const isDeal = d.price_was || d.discount_pct || d.deal_text;
    return `<div class="priceline">${tag(d.price_now, isDeal ? '' : 'plain')}${d.price_was ? `<span class="was">${eur(d.price_was)}</span>` : ''}${unit}</div>`;
  }
  const normal = d.price_was ?? d.price_now;
  const each = d.pay && normal && d.pay < normal ? d.pay : null;
  return `<div class="priceline">${each ? tag(each, 'multi') + `<span class="per">per stuk bij ${d.min_qty}</span>` : tag(normal, 'plain')}
          ${each ? `<span class="was">${eur(normal)}</span>` : ''}</div>`;
}
function flags(d){
  const t = [...(d.tags||[])];
  if (S.tab === 'fav' && d.week === 'volgende') t.unshift('Volgende week');
  if (!t.length) return '';
  return `<div class="flags">${t.map(x => `<span class="flag ${x.startsWith('Beste') ? 'best' : ''}">${esc(x)}</span>`).join('')}</div>`;
}
function linkFor(d){ return d.url || ''; }
function card(d){
  const fav = favs.keys.includes(d.key);
  const url = linkFor(d);
  return `<article class="card${isFav(d) ? ' isfav' : ''}">
    ${url ? `<a class="go" href="${esc(url)}" target="_blank" rel="noopener" aria-label="${esc(d.title)} bij ${esc(d.store)} bekijken"></a>` : ''}
    ${badge(d)}
    <button class="star${fav ? ' on' : ''}" data-i="${d.i}" aria-pressed="${fav}" aria-label="${fav ? 'Uit Mijn lijst halen' : 'Bewaren in Mijn lijst'}">${icon('star')}</button>
    <div class="pic">${pictureOf(d)}</div>
    <div class="who">${dot(d.store)}${esc(d.store)}</div>
    <div class="name">${esc(d.title)}</div>
    ${d.size ? `<div class="size">${esc(d.size)}</div>` : ''}
    ${d.deal_text ? `<div class="deal ${multi(d) ? 'multi' : ''}">${esc(d.deal_text)}</div>` : ''}
    ${multi(d) ? `<div class="need">Alleen als je er ${d.min_qty} koopt</div>` : ''}
    ${priceBlock(d)}
    ${flags(d)}
    ${d.valid_until ? `<div class="until">${d.week === 'volgende' && d.valid_from ? 'Vanaf ' + niceDate(d.valid_from) + ', ' : ''}t/m ${niceDate(d.valid_until)}</div>` : ''}
  </article>`;
}
function compareCard(members){
  const rows = [...members].sort((a,b) => (a.unit_price && b.unit_price) ? a.unit_price - b.unit_price : (a.pay ?? 1e9) - (b.pay ?? 1e9));
  const first = rows.find(d => d.image) || rows[0];
  const name = rows.map(d => d.title).sort((a,b) => a.length - b.length)[0];
  return `<article class="card cmp">
    <div class="head"><div class="pic">${pictureOf(first)}</div>
      <div><div class="name">${esc(name)}</div><div class="size">In de aanbieding bij ${rows.length} winkels</div></div></div>
    <div class="rows2">${rows.map((d, i) => `
      <a class="row${i === 0 ? ' best' : ''}" href="${esc(linkFor(d))}" target="_blank" rel="noopener">
        <span class="s">${dot(d.store)}${esc(d.store)}</span>
        <span class="p">${tag(d.pay, 'sm' + (i === 0 ? '' : ' plain'))}<span class="u">${d.unit_price ? eur(d.unit_price) + '/' + d.unit : (multi(d) ? 'per stuk bij ' + d.min_qty : '')}</span></span>
        <span class="d">${esc(d.deal_text || d.size || '')}</span>
      </a>`).join('')}</div>
  </article>`;
}
function niceDate(iso){
  try { return new Date(iso + 'T12:00').toLocaleDateString('nl-NL', {weekday:'short', day:'numeric', month:'short'}); }
  catch(e){ return iso; }
}

// ---------- chips
function chipRow(el, items, isOn, onClick){
  el.innerHTML = items.map(([key, label, n, extra]) =>
    `<button class="chip${isOn(key) ? ' on' : ''}${extra||''}" data-k="${esc(key)}" aria-pressed="${isOn(key)}">${label}${n != null ? `<span class="n">${n}</span>` : ''}</button>`).join('');
  el.querySelectorAll('.chip[data-k]').forEach(c => c.onclick = () => onClick(c.dataset.k));
}

// ---------- tabs
const TABS = [['deze', 'Deals', 'tag'], ['cheap', 'Goedkoopst', 'search'], ['volgende', 'Volgende week', 'cal'], ['fav', 'Mijn lijst', 'star']];
function renderTabs(){
  const count = t => ALL.filter(d => t === 'fav' ? isFav(d) : d.week === t).length;
  const nNext = count('volgende'), nFav = count('fav');
  if (S.tab === 'volgende' && !nNext) S.tab = 'deze';
  const html = TABS.filter(([k]) => k !== 'volgende' || nNext).map(([k, label, ic]) => {
    const n = k === 'fav' && nFav ? nFav : '';
    return `<button class="tab${S.tab === k ? ' on' : ''}" data-t="${k}" aria-current="${S.tab === k}">${icon(ic)}<span>${label}</span>${n ? `<span class="cnt">${n}</span>` : ''}</button>`;
  }).join('');
  $('tabsTop').innerHTML = html; $('tabsBottom').innerHTML = html;
  $('tabsBottom').style.gridTemplateColumns = `repeat(${nNext ? 4 : 3},1fr)`;
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
    if (S.tab === t.dataset.t) { window.scrollTo({top: 0, behavior: 'smooth'}); return; }
    S.tab = t.dataset.t; render(); window.scrollTo({top: 0});
  });
}

// ---------- main render
function render(resetPaging = true){
  if (resetPaging) S.shown = 60;
  renderTabs();
  const cheap = S.tab === 'cheap';
  $('filterrows').hidden = cheap; $('cheaprows').hidden = !cheap;
  $('fav').classList.toggle('show', S.tab === 'fav');
  const qv = cheap ? S.cq : S.q;
  if ($('q').value !== qv) $('q').value = qv;
  $('q').placeholder = cheap ? 'Wat heb je nodig? bv. toiletpapier, koffiebonen' : 'Zoek in de aanbiedingen';
  $('searchbox').classList.toggle('has', !!qv);
  if (cheap) { renderCheap(); writeHash(); return; }
  $('credit').innerHTML = '';

  // my list
  $('terms').innerHTML = favs.terms.map((t, i) => `<span class="term">${esc(t)}<button data-i="${i}" aria-label="${esc(t)} verwijderen">${icon('x')}</button></span>`).join('')
    + (favs.keys.length ? `<span class="term">${favs.keys.length} bewaarde producten<button data-k="1" aria-label="Alle bewaarde producten wissen">${icon('x')}</button></span>` : '');
  $('terms').querySelectorAll('button').forEach(x => x.onclick = () => {
    if (x.dataset.k) { if (confirmClear()) favs.keys = []; } else favs.terms.splice(+x.dataset.i, 1);
    saveFavs(); render();
  });

  const b = base();
  // categories, counted within the selected stores
  const inStores = b.filter(d => !S.only.size || S.only.has(d.store));
  const catCount = {};
  inStores.forEach(d => catCount[d.category] = (catCount[d.category]||0) + 1);
  const cats = Object.keys(catCount).sort((a,c) => (a === 'Overig') - (c === 'Overig') || catCount[c] - catCount[a]);
  const nf = activeFilters();
  $('cats').innerHTML = `<button class="chip filter" id="openFilters">${icon('sliders')}Filters${nf ? `<span class="badge">${nf}</span>` : ''}</button>`;
  const catEl = document.createElement('span'); catEl.style.display = 'contents'; $('cats').appendChild(catEl);
  chipRow(catEl, [['', 'Alles', inStores.length], ...cats.map(c => [c, esc(c), catCount[c]])],
    k => S.cat === k, k => { S.cat = S.cat === k ? '' : k; render(); });
  $('openFilters').onclick = openSheet;

  // stores, counted within the category
  const inCat = b.filter(d => !S.cat || d.category === S.cat);
  const stCount = {};
  inCat.forEach(d => stCount[d.store] = (stCount[d.store]||0) + 1);
  chipRow($('stores'), [['*', 'Alle winkels', null], ...STORES.map(n => [n, dot(n) + esc(n), stCount[n] || 0, stCount[n] ? '' : ' off'])],
    k => k === '*' ? !S.only.size : S.only.has(k),
    k => { if (k === '*') S.only.clear(); else S.only.has(k) ? S.only.delete(k) : S.only.add(k); render(); });

  const list = inCat.filter(d => !S.only.size || S.only.has(d.store)).sort(sorters[S.sort]);
  let html, total;
  if (S.cmp) {
    const groups = {};
    ALL.forEach(d => { if (d.group) (groups[d.group] ||= []).push(d); });
    const hit = new Set(list.filter(d => d.group).map(d => d.group));
    const blocks = [...hit].map(g => groups[g].filter(d => (S.tab === 'fav' || d.week === S.tab) && (!S.only.size || S.only.has(d.store))))
                           .filter(m => new Set(m.map(d => d.store)).size >= 2);
    blocks.sort((a,c) => Math.max(...c.map(d => d.effective_pct||0)) - Math.max(...a.map(d => d.effective_pct||0)));
    total = blocks.length;
    html = blocks.slice(0, S.shown).map(compareCard).join('');
    $('heading').textContent = 'Vergelijk winkels';
    $('sub').textContent = `${total} producten in de aanbieding bij meerdere winkels`;
  } else {
    total = list.length;
    html = list.slice(0, S.shown).map(card).join('');
    $('heading').textContent = {deze: 'Deals deze week', volgende: 'Volgende week', fav: 'Mijn lijst'}[S.tab];
    $('sub').textContent = `${total} aanbieding${total === 1 ? '' : 'en'}`;
  }
  if (!total) html = `<div class="empty">${S.tab === 'fav' && !favs.terms.length && !favs.keys.length
      ? 'Je lijst is nog leeg. Voeg hierboven iets toe, of tik op de ster bij een product.'
      : S.cmp ? 'Geen producten die bij meerdere winkels in de aanbieding zijn.'
      : 'Niets gevonden. Probeer een ander woord of <button class="chip" id="clearAll">wis de filters</button>'}</div>`;
  if (total > S.shown) html += `<button class="btn ghost more" id="more">Meer laden (nog ${total - S.shown})</button>`;
  $('grid').innerHTML = html;
  if ($('more')) $('more').onclick = () => { S.shown += 60; render(false); };
  if ($('clearAll')) $('clearAll').onclick = resetFilters;
  $('grid').querySelectorAll('.star').forEach(s => s.onclick = () => toggleStar(+s.dataset.i));
  writeHash();
}
function confirmClear(){ try { return window.confirm('Alle bewaarde producten wissen?'); } catch(e){ return true; } }
function resetFilters(){ S.q = ''; S.type = ''; S.sort = 'pct'; S.min = 0; S.cat = ''; S.only.clear(); S.cmp = false; $('cmp').checked = false; render(); }

// ---------- filter sheet
function seg(el, key, opts){
  el.innerHTML = opts.map(([v, l]) => `<button class="${String(S[key]) === String(v) ? 'on' : ''}" data-v="${v}" aria-pressed="${String(S[key]) === String(v)}">${l}</button>`).join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => { S[key] = key === 'min' ? +b.dataset.v : b.dataset.v; seg(el, key, opts); render(); });
}
function openSheet(){
  seg($('segType'), 'type', OPTIONS.type); seg($('segSort'), 'sort', OPTIONS.sort); seg($('segMin'), 'min', OPTIONS.min);
  document.body.classList.add('sheet-open'); setTimeout(() => $('done').focus(), 50);
}
function closeSheet(){ document.body.classList.remove('sheet-open'); }
$('scrim').onclick = closeSheet; $('done').onclick = closeSheet;
$('reset').onclick = () => { resetFilters(); openSheet(); };
$('cmp').onchange = () => { S.cmp = $('cmp').checked; render(); };
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

// ---------- Goedkoopst: regular prices of everything (Checkjebon) + this week's deals
let P = null, PN = null, pLoading = false, pFailed = false;
const UNIT_LABEL = {kg:'per kilo', l:'per liter', stuk:'per stuk', rol:'per rol', wasbeurt:'per wasbeurt',
                    tablet:'per tablet', luier:'per luier', ei:'per ei', doekje:'per doekje'};
const UNIT_SHORT = {kg:'kg', l:'liter', stuk:'stuk', rol:'rol', wasbeurt:'wasbeurt', tablet:'tablet', luier:'luier', ei:'ei', doekje:'doekje'};
const SUGGEST = ['toiletpapier', 'koffiebonen', 'pindakaas', 'wasmiddel', 'cola zero', 'eieren', 'luiers', 'kipfilet'];
function loadPrices(){
  if (P || pLoading || pFailed) return;
  if (window.PRICES) { initPrices(); return; }
  pLoading = true;
  const sc = document.createElement('script');
  sc.src = 'prices.js';
  sc.onload = () => { pLoading = false; initPrices(); if (S.tab === 'cheap') render(false); };
  sc.onerror = () => { pLoading = false; pFailed = true; if (S.tab === 'cheap') render(false); };
  document.head.appendChild(sc);
}
function initPrices(){
  P = window.PRICES;
  PN = P.items.map(r => ' ' + norm(r[1] + ' ' + r[3]).replace(/[^a-z0-9]+/g, ' ') + ' ');
}
function cheapResults(){
  const words = norm(S.cq).replace(/[^a-z0-9]+/g, ' ').trim().split(' ').filter(Boolean);
  if (!words.length) return null;
  const groups = {}, noUnit = [];
  for (let i = 0; i < P.items.length; i++) {
    const n = PN[i];
    if (!words.every(w => n.includes(' ' + w))) continue;
    const [s, name, price, size, qty, u, url, deal, pay, minq] = P.items[i];
    const dealOk = deal && pay != null && (minq <= 1 || S.cmulti);
    const each = dealOk ? pay : price;
    if (each == null) continue;
    const r = {store: P.stores[s], name, price, size, qty, unit: P.units[u] || '', deal: dealOk ? deal : '',
               pay: dealOk ? pay : null, minq: dealOk ? minq : 1, each,
               url: !url ? '' : url.startsWith('http') ? url : (P.prefixes[s] || '') + url};
    if (qty && r.unit) { r.up = each / qty; (groups[r.unit] ||= []).push(r); }
    else noUnit.push(r);
  }
  const out = Object.entries(groups).sort((a, b) => b[1].length - a[1].length).map(([unit, rows]) => {
    rows.sort((a, b) => a.up - b.up);
    return {unit, total: rows.length, rows: S.cper ? onePerStore(rows) : rows};
  });
  if (noUnit.length) {
    noUnit.sort((a, b) => a.each - b.each);
    out.push({unit: '', total: noUnit.length, rows: S.cper ? onePerStore(noUnit) : noUnit});
  }
  return out;
}
function onePerStore(rows){ const seen = new Set(); return rows.filter(r => !seen.has(r.store) && seen.add(r.store)); }
function cheapRow(r, i, unit){
  const multiDeal = r.deal && r.minq > 1;
  const sub = r.deal && r.price && r.pay < r.price
      ? `<span style="text-decoration:line-through">${eur(r.price)}</span> ${eur(r.pay)}${multiDeal ? ' per stuk' : ''}`
      : eur(r.each);
  const dealLine = r.deal ? `<div class="deal ${multiDeal ? 'multi' : ''}">${esc(r.deal)}${multiDeal ? `, alleen bij ${r.minq} stuks (samen ${eur(r.pay * r.minq)})` : ''}</div>` : '';
  const showSize = r.size && !r.name.toLowerCase().includes(r.size.toLowerCase());
  return `<a class="prow${i === 0 ? ' top' : ''}" href="${esc(r.url)}" target="_blank" rel="noopener">
    ${i === 0 ? '<span class="winner">Goedkoopst</span>' : ''}
    <div><div class="who">${dot(r.store)}${esc(r.store)}</div><div class="name">${esc(r.name)}</div>
      ${showSize ? `<div class="size">${esc(r.size)}</div>` : ''}${dealLine}</div>
    <div class="right">${unit ? tag(r.up, (i === 0 ? '' : 'plain') + ' sm') : tag(r.each, 'sm' + (i === 0 ? '' : ' plain'))}
      ${unit ? `<span class="sub">per ${UNIT_SHORT[unit]}</span>` : ''}<span class="sub">${sub}</span></div>
  </a>`;
}
function renderCheap(){
  $('cmultiBtn').classList.toggle('on', S.cmulti); $('cmultiBtn').setAttribute('aria-pressed', S.cmulti);
  $('cperBtn').classList.toggle('on', S.cper); $('cperBtn').setAttribute('aria-pressed', S.cper);
  $('heading').textContent = 'Waar is het het goedkoopst?';
  const others = STORES.filter(s => !(P && P.regular.includes(s)));
  $('credit').innerHTML = P
    ? `Gewone prijzen van <a href="https://www.checkjebon.nl" target="_blank" rel="noopener">Checkjebon.nl</a>, dagelijks bijgewerkt, plus de aanbiedingen van deze week. `
      + (others.length ? `Van ${esc(others.join(', '))} tellen alleen de aanbiedingen mee. ` : '')
      + 'Prijzen kunnen per filiaal verschillen.'
    : '';
  if (!P) {
    loadPrices();
    $('grid').innerHTML = `<div class="empty">${pFailed
      ? 'De prijslijst is er nog niet. Hij wordt gemaakt bij de volgende update.'
      : 'Prijzen van ruim 100.000 producten laden…'}</div>`;
    $('sub').textContent = '';
    return;
  }
  const res = cheapResults();
  if (!res) {
    $('sub').textContent = `Alle merken, ${P.items.length.toLocaleString('nl-NL')} producten bij ${P.stores.length} winkels`;
    $('grid').innerHTML = `<div class="empty">Typ wat je nodig hebt en zie waar het per kilo, liter, rol of wasbeurt het goedkoopst is, met de deals van deze week meegerekend.
      <div class="suggest">${SUGGEST.map(s => `<button class="chip" data-s="${s}">${s}</button>`).join('')}</div></div>`;
    $('grid').querySelectorAll('[data-s]').forEach(b => b.onclick = () => { S.cq = b.dataset.s; render(); });
    return;
  }
  const total = res.reduce((n, g) => n + g.total, 0);
  $('sub').textContent = `${total} producten gevonden`;
  if (!total) { $('grid').innerHTML = '<div class="empty">Niets gevonden. Probeer een ander of korter woord.</div>'; return; }
  $('grid').innerHTML = res.map(g => `
    <div class="grp"><h3>${g.unit ? 'Goedkoopst ' + UNIT_LABEL[g.unit] : 'Zonder maat, op prijs'}</h3><span>${g.total} producten${S.cper ? ', beste per winkel' : ''}</span></div>
    ${g.rows.slice(0, S.cper ? 30 : 60).map((r, i) => cheapRow(r, i, g.unit)).join('')}`).join('');
}
$('cmultiBtn').onclick = () => { S.cmulti = !S.cmulti; render(); };
$('cperBtn').onclick = () => { S.cper = !S.cper; render(); };

// ---------- warnings, updated time
if ((DATA.warnings||[]).length) {
  $('warn').innerHTML = `<details><summary>${DATA.warnings.length === 1 ? 'Eén winkel gaf' : DATA.warnings.length + ' winkels gaven'} vandaag minder resultaten dan normaal</summary>
    <ul>${DATA.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>`;
}
(function(){
  const g = DATA.generated || '';
  const today = new Date().toISOString().slice(0, 10);
  const t = g.slice(11, 16);
  $('updated').textContent = g ? (g.slice(0, 10) === today ? `Bijgewerkt vandaag om ${t}` : `Bijgewerkt ${niceDate(g.slice(0, 10))} om ${t}`) : '';
})();

// ---------- share + theme + toast
function toast(msg){ const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 1800); }
$('share').onclick = async () => {
  const url = location.href;
  try {
    if (navigator.share && matchMedia('(max-width:860px)').matches) { await navigator.share({title: 'Bonus', url}); return; }
    await navigator.clipboard.writeText(url); toast('Link gekopieerd');
  } catch(e) { if (e && e.name !== 'AbortError') prompt('Kopieer deze link:', url); }
};
function applyTheme(t){
  document.documentElement.dataset.theme = t;
  $('theme').innerHTML = icon(t === 'dark' ? 'sun' : 'moon');
  $('theme').setAttribute('aria-label', t === 'dark' ? 'Lichte modus' : 'Donkere modus');
  document.querySelector('meta[name=theme-color]').content = t === 'dark' ? '#111613' : '#f3f5f2';
}
let theme = store.get('bonus_theme', null) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
applyTheme(theme);
$('theme').onclick = () => { theme = theme === 'dark' ? 'light' : 'dark'; store.set('bonus_theme', theme); applyTheme(theme); };

// ---------- search box (deals or all products, depending on the tab)
let typing;
$('q').addEventListener('input', () => {
  $('searchbox').classList.toggle('has', !!$('q').value);
  clearTimeout(typing);
  typing = setTimeout(() => { if (S.tab === 'cheap') S.cq = $('q').value; else S.q = $('q').value; render(); }, 180);
});
$('qclear').onclick = () => { $('q').value = ''; if (S.tab === 'cheap') S.cq = ''; else S.q = ''; render(); $('q').focus(); };
window.addEventListener('hashchange', () => { readHash(); render(); });

readHash();
render();
</script></body></html>
"""


def write_html(payload: dict, path: Path):
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
