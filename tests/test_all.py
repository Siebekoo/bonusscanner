"""Offline tests: extractor on sample JSON, AH parser, HTML report, and the full browser
pipeline against a fake local shop (needs Chrome or Playwright's Chromium)."""
import http.server, json, sys, threading, functools, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from scanner.extract import walk
from scanner import ah, browser
from scanner.report import write_html

def test_extract_nested_cents():
    data = json.load(open(Path(__file__).parent / "site/api/offers0.json"))
    deals = walk(data, cents=True)
    assert len(deals) == 6, deals
    d = deals[0]
    assert d.title == "Testproduct 0 koffie" and d.price_now == 2.99 and d.price_was == 4.99, d
    assert d.deal_text == "1+1 gratis" and d.valid_until == "2026-11-17", d

def test_extract_flat_euros():
    data = {"items": [{"name": "Chips naturel", "price": {"now": 1.19, "was": 1.89},
                       "unitPrice": {"amount": 7.44}, "badge": "2 voor 2,00"},
                      {"name": "Geen aanbieding zonder prijs"}]}
    deals = walk(data)
    assert len(deals) == 1 and deals[0].price_now == 1.19 and deals[0].price_was == 1.89
    assert deals[0].deal_text == "2 voor 2,00"

def test_ah_parser():
    p = {"webshopId": 123, "title": "AH Halfvolle melk", "currentPrice": 1.09,
         "priceBeforeBonus": 1.45, "bonusMechanism": "2e halve prijs", "salesUnitSize": "1 l",
         "images": [{"width": 200, "url": "s.jpg"}, {"width": 800, "url": "l.jpg"}]}
    d = ah._to_deal(p, {"bonusStartDate": "2026-11-10", "bonusEndDate": "2026-11-16"}).finalize()
    assert d.price_now == 1.09 and d.image == "l.jpg"
    assert d.deal_type == "meer kopen" and d.min_qty == 2 and d.discount_pct is None
    assert d.effective_pct == 25
    assert d.url.endswith("wi123") and d.valid_until == "2026-11-16"

def test_classify():
    from scanner.models import classify
    assert classify("1+1 gratis") == (2, 50)
    assert classify("2+1gratis") == (3, 33)
    assert classify("2ehalve prijs") == (2, 25)
    assert classify("3 voor 5,00", 2.49) == (3, 33)
    assert classify("25% korting") == (1, 25)
    assert classify("Mijn Etos 10%korting van € 9.99 voor € 8.99") == (1, 10)

def test_direct_vs_multi():
    from scanner.models import Deal
    a = Deal(store="x", title="a", deal_text="30% korting", price_now=0.7, price_was=1.0).finalize()
    b = Deal(store="x", title="b", deal_text="1+1 gratis", price_now=2.0).finalize()
    assert (a.deal_type, a.discount_pct, a.min_qty) == ("korting", 30, 1)
    assert (b.deal_type, b.discount_pct, b.effective_pct, b.min_qty) == ("meer kopen", None, 50, 2)

def test_categories():
    from scanner.models import Deal
    from scanner.enrich import categorize
    cases = {"Calvé pindakaas 350 g": "Ontbijt & beleg", "Jonge Goudse kaas 48+": "Zuivel & eieren",
             "Garnier serum": "Drogisterij", "Bacardi rum 70 cl": "Bier, wijn & sterk",
             "Crème fraîche 200 ml": "Zuivel & eieren", "Boterhamworst": "Vlees & vis",
             "Milka melkchocolade": "Snoep & koek", "Lay's chips paprika": "Chips & noten",
             "Hollandse tomaten": "Groente & fruit", "Coca-Cola Zero 6 x 330 ml": "Frisdrank & sap",
             "Pampers luiers maat 4": "Baby", "Robijn wasverzachter": "Huishouden",
             "Vivera vegetarische kipstuckjes": "Vegetarisch", "Tomatenpuree 70 g": "Voorraadkast"}
    wrong = {t: categorize(Deal(store="X", title=t)) for t in cases
             if categorize(Deal(store="X", title=t)) != cases[t]}
    assert not wrong, wrong

def test_unit_price_and_grouping():
    from scanner.models import Deal
    from scanner.enrich import enrich
    from datetime import date
    ds = [Deal(store="AH", title="AH Halfvolle melk", size="1 l", price_now=1.09, price_was=1.25),
          Deal(store="Jumbo", title="Jumbo Halfvolle melk", size="1 l", price_now=0.99, price_was=1.19),
          Deal(store="PLUS", title="Coca-Cola Zero", size="6 x 330 ml", deal_text="1+1 gratis", price_now=5.49),
          Deal(store="Dirk", title="Bekijk alle aanbiedingen", price_now=1.0),
          Deal(store="Dirk", title="Oude aanbieding", price_now=1.0, valid_until="2026-01-01")]
    out = enrich([d.finalize() for d in ds], date(2026, 11, 18))
    assert [d.title for d in out] == ["AH Halfvolle melk", "Jumbo Halfvolle melk", "Coca-Cola Zero"]
    milk = out[:2]
    assert milk[0].group and milk[0].group == milk[1].group
    assert (milk[0].unit_price, milk[0].unit) == (1.09, "l")
    cola = out[2]
    assert cola.pay_per_item() == 2.75 and cola.unit_price == 1.39 and cola.unit == "l"

def test_next_week():
    from scanner.models import Deal
    from scanner.enrich import enrich
    from datetime import date
    d = Deal(store="AH", title="Pindakaas", price_now=2.0, valid_from="2026-11-23").finalize()
    assert enrich([d], date(2026, 11, 18))[0].week == "volgende"

def test_history_and_health():
    sys.path.insert(0, str(Path(__file__).parent))
    from sample_data import build
    p = build()
    tags = [t for d in p["deals"] for t in d["tags"]]
    assert any(t.startswith("Beste prijs in") for t in tags)
    assert any(t == "Vaak in de aanbieding" for t in tags)
    assert p["warnings"] and p["warnings"][0].startswith("Kruidvat: vandaag 0")
    assert not any("nieuwsbrief" in d["title"] for d in p["deals"])
    assert {d["week"] for d in p["deals"]} == {"deze", "volgende"}

def test_page_in_browser():
    """Open the sample page and use every feature; fail on any JavaScript error."""
    sys.path.insert(0, str(Path(__file__).parent))
    from sample_data import build
    from playwright.sync_api import sync_playwright
    out = Path(tempfile.mkdtemp()) / "page.html"
    write_html(build(), out)
    errors = []
    with sync_playwright() as p:
        b = browser._launch(p, headful=False)
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(out.as_uri())
        n = lambda: pg.locator("#grid .card").count()
        assert n() > 20
        pg.fill("#q", "cola"); pg.wait_for_timeout(300)
        assert 0 < n() < 20
        pg.fill("#q", ""); pg.wait_for_timeout(300)
        pg.check("#cmp"); assert pg.locator(".cmp").count() > 3; pg.uncheck("#cmp")
        pg.locator("#grid .star").first.click()
        pg.locator(".tab", has_text="Mijn lijst").click()
        assert n() >= 1
        pg.reload(); pg.wait_for_timeout(200)
        assert n() >= 1, "favorites should survive a reload"
        pg.locator(".tab", has_text="Volgende week").click(); assert n() > 10
        pg.click("#theme")
        b.close()
    assert not errors, errors

def _serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler,
                          directory=str(Path(__file__).parent / "site"))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def test_browser_json_and_scroll():
    srv = _serve(); base = f"http://127.0.0.1:{srv.server_port}"
    deals = browser.fetch_page("Testshop", base + "/shop_json.html", cents=True, max_scrolls=15)
    assert len(deals) == 18, f"expected all 3 pages via scrolling, got {len(deals)}"
    assert all(d.url.startswith(base + "/producten/") for d in deals)
    assert {d.deal_text for d in deals} == {"1+1 gratis", "2e halve prijs", "25% korting"}

def test_browser_page_cards():
    srv = _serve(); base = f"http://127.0.0.1:{srv.server_port}"
    deals = {d.title: d for d in browser.fetch_page("Folder", base + "/shop_dom.html")}
    assert len(deals) == 6, deals.keys()
    pk = deals["Pindakaas 350 g"]
    assert pk.price_now == 2.29 and pk.price_was == 3.49 and pk.deal_text == "1+1 gratis"
    nv = deals["Nivea babycreme"]          # Etos style: "van € 14.99 voor € 7.50"
    assert (nv.price_was, nv.price_now) == (14.99, 7.5) and nv.deal_text == "1+1gratis", nv

def test_report():
    out = Path(tempfile.mkdtemp()) / "x.html"
    write_html({"generated": "2026-11-15T15:00", "stores": {"A": {"ok": True, "count": 1}},
                "deals": [{"store": "A", "title": "</script><b>", "discount_pct": 10}]}, out)
    assert "</script><b>" not in out.read_text()

if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try: fn(); print("PASS", name)
            except Exception as e: fails += 1; print("FAIL", name, "->", e)
    sys.exit(fails)
