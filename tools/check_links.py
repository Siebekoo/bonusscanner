"""1) Which raw fields hold product links for stores that only got the offers page.
2) Which search-page address works per store (opened in a real browser)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from scanner.browser import _launch, _accept_cookies, STEALTH_JS

CANDIDATES = {
  "Jumbo": ["https://www.jumbo.com/producten/?searchType=keyword&searchTerms={q}", "https://www.jumbo.com/zoeken?searchTerms={q}",
            "https://www.jumbo.com/producten/?searchTerms={q}"],
  "Jumbo-promo": ["https://www.jumbo.com/aanbiedingen/jumbo-tofu-of-tempeh-naturel/3022380", "https://www.jumbo.com/aanbiedingen/3022380"],
  "Lidl": ["https://www.lidl.nl/q/search?q={q}"],
  "Lidl-product": ["https://www.lidl.nl/p/mango/p11029883", "https://www.lidl.nl/p/p11029883"],
  "PLUS": ["https://www.plus.nl/zoekresultaten?SearchTerm={q}"],
  "Hoogvliet": ["https://www.hoogvliet.com/search?query={q}", "https://hoogvliet.nl/search?query={q}"],
  "Spar": ["https://www.spar.nl/zoekresultaten/?q={q}", "https://www.spar.nl/zoeken/{q}/", "https://www.spar.nl/producten/?q={q}"],
}
TERM = {"Jumbo-promo": "tofu", "Lidl-product": "mango", "Etos": "tandpasta", "Kruidvat": "tandpasta", "Gall & Gall": "whisky", "Action": "kaars", "Makro": "koffie"}
out = {"raw": {}, "search": {}}
for f in Path("debug").glob("*_deals_raw.json"):
    rows = json.loads(f.read_text())
    out["raw"][f.stem] = [{"found_url": r["found"].get("url", ""), "raw_keys": list((r.get("raw") or {}).keys())[:40],
                           "raw": json.dumps(r.get("raw"), ensure_ascii=False)[:1500]} for r in rows[:3]]
with sync_playwright() as p:
    b = _launch(p, headful=False)
    for store, urls in CANDIDATES.items():
        term = TERM.get(store, "pindakaas")
        res = []
        for u in urls:
            url = u.format(q=term)
            ctx = b.new_context(locale="nl-NL", user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{b.version} Safari/537.36")
            ctx.add_init_script(STEALTH_JS); pg = ctx.new_page()
            try:
                r = pg.goto(url, wait_until="domcontentloaded", timeout=40000); pg.wait_for_timeout(4000); _accept_cookies(pg); pg.wait_for_timeout(6000)
                txt = pg.inner_text("body")[:200000].lower()
                res.append({"url": url, "status": r.status if r else None, "final": pg.url, "title": pg.title()[:80],
                            "term_hits": txt.count(term), "notfound": any(w in txt for w in ["niet gevonden", "geen resultaten", "404", "pagina bestaat niet"])})
            except Exception as e:
                res.append({"url": url, "error": str(e)[:120]})
            ctx.close()
        out["search"][store] = res
    b.close()
Path("debug-output").mkdir(exist_ok=True)
Path("debug-output/links3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
