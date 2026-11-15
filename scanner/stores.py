"""Which stores exist and how each is scraped.

If a store moves its offers page, change the URL here; nothing else needs to change.
`cents=True` means that site's JSON gives prices in cents (199 = €1.99).
`next_url` (optional) is a page with next week's deals; everything found there is put
under "Volgende week". Deals whose start date is in the future go there automatically.
"""
from __future__ import annotations

from . import ah, jumbo, browser

STORES = {
    "ah": {
        "name": "Albert Heijn",
        "fetch": ah.fetch,
    },
    "jumbo": {
        "name": "Jumbo",
        "fetch": jumbo.fetch,
    },
    "hoogvliet": {
        "name": "Hoogvliet",
        "url": "https://www.hoogvliet.com/aanbiedingen",
    },
    "etos": {
        "name": "Etos",
        "url": "https://www.etos.nl/aanbiedingen/",
    },
    "kruidvat": {
        "name": "Kruidvat",
        "url": "https://www.kruidvat.nl/aanbiedingen/dezeweek",
    },
    "dirk": {
        "name": "Dirk",
        "url": "https://www.dirk.nl/aanbiedingen",
    },
    "aldi": {
        "name": "Aldi",
        "url": "https://www.aldi.nl/aanbiedingen.html",
    },
    "lidl": {
        "name": "Lidl",
        "url": "https://www.lidl.nl/c/aanbiedingen/a10008785",
        # Lidl spreads offers over a few pages; add more here if you find them.
        "extra_urls": [],
    },
    "plus": {
        "name": "PLUS",
        "url": "https://www.plus.nl/aanbiedingen",
    },
    # --- added later. These addresses are best guesses; the health check on the page
    # will show if one finds nothing, and then the URL needs fixing here.
    "vomar": {
        "name": "Vomar",
        "url": "https://www.vomar.nl/aanbiedingen",
    },
    "dekamarkt": {
        "name": "DekaMarkt",
        "url": "https://www.dekamarkt.nl/aanbiedingen",
    },
    "coop": {
        "name": "Coop",
        "url": "https://www.coop.nl/aanbiedingen",
    },
    "spar": {
        "name": "Spar",
        # Spar applies many deals only in the cart, so this may find little.
        "url": "https://www.spar.nl/aanbiedingen/",
    },
    "action": {
        "name": "Action",
        "url": "https://www.action.com/nl-nl/weekactie/",
    },
    "gall": {
        "name": "Gall & Gall",
        "url": "https://www.gall.nl/aanbiedingen/",
    },
    "makro": {
        "name": "Makro",
        # Makro is wholesale: many prices only show after logging in with a Makro pass,
        # and prices are usually excl. btw.
        "url": "https://www.makro.nl/aanbiedingen",
    },
}


def run_store(key: str, **opts):
    cfg = STORES[key]
    if "fetch" in cfg:
        deals = cfg["fetch"](**opts)
    else:
        def go(**o):
            return browser.fetch_page(cfg["name"], cfg["url"],
                                      extra_urls=cfg.get("extra_urls", ()),
                                      cents=cfg.get("cents", False), **o)
        deals = go(**opts)
        if cfg.get("next_url"):
            try:
                nxt = browser.fetch_page(cfg["name"], cfg["next_url"],
                                         cents=cfg.get("cents", False), **opts)
                for d in nxt:
                    d.week = "volgende"
                deals += nxt
            except Exception as e:
                print(f"    {cfg['name']}: next week failed ({str(e).splitlines()[0][:80]})")
        # Some sites (Etos, Kruidvat) block invisible browsers. Retry once with a normal
        # browser window, placed off-screen so it doesn't get in your way.
        if not deals and not opts.get("headful"):
            print(f"    {cfg['name']}: nothing found, retrying with a normal browser window")
            try:
                deals = go(**{**opts, "headful": True, "offscreen": True})
            except Exception as e:
                print(f"    {cfg['name']}: retry failed ({str(e).splitlines()[0][:80]})")
    for d in deals:
        d.store = cfg["name"]
        d.finalize()
    return deals
