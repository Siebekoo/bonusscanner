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

FAKE_PRICES = [
    {"n": "jumbo", "u": "https://www.jumbo.com/producten/", "d": [
        {"n": "Jumbo Toiletpapier 2-laags 24 Stuks", "l": "tp", "p": 6.19, "s": ""},
        {"n": "Page Kussenzacht Toiletpapier 3-laags 9 rollen", "l": "page9", "p": 7.49, "s": ""},
        {"n": "Jumbo Vochtig Toiletpapier 80 Stuks", "l": "wet", "p": 0.94, "s": ""}]},
    {"n": "hoogvliet", "u": "https://www.hoogvliet.com/product/", "d": [
        {"n": "G'woon Toiletpapier", "l": "gw", "p": 6.25, "s": "24 rollen"},
        {"n": "Finish all in one vaatwastabletten", "l": "fin", "p": 12.99, "s": "54 tabs"}]},
    {"n": "plus", "u": "https://www.plus.nl/product/", "d": [
        {"n": "PLUS Toiletpapier 2-laags", "l": "p2", "p": 6.99, "s": "per 24 st"},
        {"n": "PLUS Toiletpapier 3-laags 16 rollen", "l": "p3", "p": 5.19, "s": ""}]},
]

def test_price_units():
    from scanner.prices import amount_for
    assert amount_for("AH Toiletpapier 2-laags 16=24 rollen", "") == (24.0, "rol")
    assert amount_for("Jumbo Vochtig Toiletpapier 80 Stuks", "") == (80.0, "doekje")
    assert amount_for("Finish all in one vaatwastabletten", "54 tabs") == (54.0, "tablet")
    assert amount_for("Ariel wasmiddel", "40 wasbeurten") == (40.0, "wasbeurt")
    assert amount_for("Page toiletpapier 6-rollen", "") == (6.0, "rol")
    assert amount_for("PLUS rosti", "Per 350 g") == (0.35, "kg")
    assert amount_for("Spar wijn", "187 Milliliter") == (0.187, "l")
    assert amount_for("Cola zero", "6 x 330 ml") == (1.98, "l")

def test_prices_with_deals():
    from scanner import prices
    from scanner.models import Deal
    from scanner.enrich import enrich
    from datetime import date
    deals = enrich([d.finalize() for d in [
        Deal(store="Jumbo", title="Page Toiletpapier Kussenzacht 3-laags 9 rollen", deal_text="1+1 gratis", price_now=7.49),
        Deal(store="PLUS", title="PLUS Toiletpapier 3-laags", size="16 rollen", deal_text="25% korting",
             price_now=3.89, price_was=5.19),
        Deal(store="Etos", title="Etos toiletpapier 24 rollen", deal_text="1+1 gratis", price_now=9.99)]],
        date(2026, 11, 17))
    p = prices.build(FAKE_PRICES, deals)
    rows = {r[1]: r for r in p["items"]}
    page = rows["Page Kussenzacht Toiletpapier 3-laags 9 rollen"]
    assert (page[7], page[8], page[9]) == ("1+1 gratis", 3.75, 2)          # deal on the right pack
    assert rows["PLUS Toiletpapier 3-laags 16 rollen"][8] == 3.89           # 3-laags, not 2-laags
    assert rows["PLUS Toiletpapier 2-laags"][7] == ""
    assert "Etos toiletpapier 24 rollen" in rows                            # store without a price list
    assert p["stores"][rows["Etos toiletpapier 24 rollen"][0]] == "Etos"

def test_cheapest_tab_in_browser():
    from scanner import prices
    from playwright.sync_api import sync_playwright
    folder = Path(tempfile.mkdtemp())
    write_html({"generated": "2026-11-17T06:10", "stores": {"Jumbo": {"count": 0}}, "warnings": [],
                "deals": []}, folder / "deals.html")
    prices.write_js(prices.build(FAKE_PRICES, []), folder / "prices.js")
    errors = []
    with sync_playwright() as p:
        b = browser._launch(p, headful=False)
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto((folder / "deals.html").as_uri() + "#t=cheap&cq=toiletpapier")
        pg.wait_for_selector(".prow", timeout=10000)
        groups = pg.locator(".grp").all_inner_texts()
        assert groups[0].startswith("Goedkoopst per rol"), groups
        first = pg.locator(".prow").first.inner_text()
        assert "Jumbo Toiletpapier 2-laags" in first and "0,26" in first, first
        assert any("per doekje" in g for g in groups)        # wipes kept apart
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

def test_finds_moved_offers_page():
    """Store URL is wrong: the scanner should find the offers page via the homepage."""
    from scanner import stores
    srv = _serve(); base = f"http://127.0.0.1:{srv.server_port}"
    stores.STORES["test"] = {"name": "Testshop", "url": base + "/bestaat-niet", "cents": True}
    try:
        deals = stores.run_store("test", headful=True, offscreen=True) if _has_display() \
            else _run_headless_discovery(base)
    finally:
        del stores.STORES["test"]
    assert len(deals) == 18, len(deals)

def _has_display():
    import os
    return bool(os.environ.get("DISPLAY")) or sys.platform in ("win32", "darwin")

def _run_headless_discovery(base):
    found = browser.discover_offer_urls(base + "/bestaat-niet")
    assert found and found[0].endswith("/shop_json.html"), found
    return browser.fetch_page("Testshop", found[0], cents=True)

def test_implausible_discount():
    from scanner.models import Deal
    cheese = Deal(store="X", title="Jong belegen kaas", price_now=1.99, price_was=15.99).finalize()
    assert cheese.price_was is None and cheese.discount_pct is None
    real = Deal(store="X", title="Wasmiddel", deal_text="70% korting", price_now=3.0, price_was=10.0).finalize()
    assert real.discount_pct == 70

def test_gall_style_tiles():
    """Icons next to prices, cents added with CSS, full price only in screen-reader labels."""
    srv = _serve(); base = f"http://127.0.0.1:{srv.server_port}"
    deals = {d.title: d.finalize() for d in browser.fetch_page("Gall & Gall", base + "/shop_gall.html")}
    assert set(deals) == {"Bacardí Carta Blanca", "Smirnoff"}, deals.keys()
    b = deals["Bacardí Carta Blanca"]
    assert (b.price_now, b.price_was, b.discount_pct) == (24.99, 32.99, 24)
    assert b.image.endswith("IMG_685921.png") and b.url.endswith("769851.html")

def test_plus_reader():
    from scanner import plus
    offer = lambda **k: {"Brand": "PLUS", "Name": "x", "Example": "", "Package": "", "Slug": "4455-1",
                         "NewPrice": "0", "PriceOriginal_Product": "0", "PriceOriginal_Lowest": "0",
                         "PriceOriginal_Highest": "0", "DisplayInfo_Label": "", "DisplayInfo_PromotionBasedLabel": "",
                         "StartDate": "2026-11-11", "EndDate": "2026-11-17", "ImageURL": "", "IsFreeDeliveryOffer": False, **k}
    data = {"url": "https://www.plus.nl/screenservices/x/DataActionGetPromotionList_Optimization",
            "data": {"data": {"PromotionOfferList": {"List": [{"Category": {"Offers": {"List": [
                offer(Brand="Alle Pampers", Name="", Example="Bijv. Premium Protection maat 3",
                      NewPrice="31.98", PriceOriginal_Lowest="47.97", DisplayInfo_Label="2+1 GRATIS"),
                offer(Name="Courgette groen", Example="Per 1 st", PriceOriginal_Product="0.89",
                      DisplayInfo_Label="2 VOOR 1.00", Slug="plus-courgette-groen-stuk-1-st-114068"),
                offer(Name="Handappels", Example="Per 1000 gram", NewPrice="1.00", PriceOriginal_Product="1.49"),
                offer(Name="Bolletje", DisplayInfo_Label="Gratis bezorging BIJ 10.00 EURO", IsFreeDeliveryOffer=True),
            ]}}}]}}}}
    deals = {d.title: d.finalize() for d in plus.parse([data])}
    assert len(deals) == 3
    p = next(d for t, d in deals.items() if "Pampers" in t)
    assert (p.min_qty, p.pay_per_item(), p.price_was) == (3, 10.66, 15.99)
    c = deals["PLUS Courgette groen"]
    assert (c.deal_text, c.pay_per_item(), c.size) == ("2 voor €1,00", 0.5, "1 st")
    assert c.url == "https://www.plus.nl/product/plus-courgette-groen-stuk-1-st-114068"
    assert deals["PLUS Handappels"].discount_pct == 33

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
