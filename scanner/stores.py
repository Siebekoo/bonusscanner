"""Which stores exist and how each is scraped.

If a store moves its offers page, change the URL here; nothing else needs to change.
`cents=True` means that site's JSON gives prices in cents (199 = €1.99).
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
