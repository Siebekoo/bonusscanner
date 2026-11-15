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
