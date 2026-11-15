"""Generate realistic fake deals for several simulated weeks and run them through the real
pipeline (enrich -> history -> page). Used by the tests; also handy to preview the page:

    python tests/sample_data.py      # writes output/sample.html
"""
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from scanner.models import Deal
from scanner.enrich import enrich
from scanner import history
from scanner.report import write_html

PRODUCTS = [  # title, size, normal price
    ("Coca-Cola Zero", "6 x 330 ml", 5.49), ("Douwe Egberts Aroma Rood", "500 g", 7.99),
    ("Calvé pindakaas", "350 g", 3.29), ("Halfvolle melk", "1 l", 1.25), ("Robijn wasverzachter", "750 ml", 4.49),
    ("Pampers luiers maat 4", "44 stuks", 15.99), ("Lay's chips paprika", "225 g", 2.69), ("Kipfilet", "1 kg", 9.99),
    ("Heineken pils", "24 x 0,3 l", 17.99), ("Andrélon shampoo", "300 ml", 4.99), ("Milka melkchocolade", "100 g", 1.79),
    ("Barilla spaghetti", "500 g", 1.89), ("Elstar appels", "1 kg", 2.49), ("Jonge Goudse kaas", "500 g", 6.29),
    ("Whiskas kattenvoer", "12 x 85 g", 5.99), ("Ariel wasmiddel", "1,1 l", 11.99), ("Pepsi Max", "1,5 l", 2.29),
    ("Vivera vegaburger", "200 g", 3.49), ("Dr. Oetker pizza", "390 g", 3.99), ("Nivea douchegel", "250 ml", 3.29),
]
STORES = ["Albert Heijn", "Jumbo", "PLUS", "Dirk", "Hoogvliet", "Lidl", "Aldi", "Kruidvat", "Etos", "Vomar"]
DRUG = {"Andrélon shampoo", "Nivea douchegel", "Pampers luiers maat 4", "Robijn wasverzachter", "Ariel wasmiddel"}
DEALS = ["1+1 gratis", "2e halve prijs", "25% korting", "35% korting", "3 voor 5,00", "", "2+1 gratis"]


def week_deals(monday: date, rnd: random.Random, next_week=False):
    out = []
    for store in STORES:
        for title, size, price in PRODUCTS:
            if store in ("Kruidvat", "Etos") and title not in DRUG:
                continue
            if rnd.random() > 0.35:
                continue
            dt = rnd.choice(DEALS)
            if dt == "3 voor 5,00":
                dt = f"3 voor {price * 3 * rnd.choice([0.7, 0.8]):.2f}".replace(".", ",")
            factor = rnd.choice([0.6, 0.7, 0.75, 0.8, 0.85])
            prefix = {"Albert Heijn": "AH ", "Jumbo": "Jumbo "}.get(store, "") if title in ("Halfvolle melk", "Kipfilet") else ""
            d = Deal(store=store, title=prefix + title, size=size, deal_text=dt,
                     price_was=round(price * rnd.uniform(.95, 1.05), 2),
                     valid_from=monday.isoformat(), valid_until=(monday + timedelta(days=6)).isoformat(),
                     url="https://example.com")
            d.price_now = round(d.price_was * factor, 2) if dt in ("", "25% korting", "35% korting") else d.price_was
            out.append(d.finalize())
    # some junk the cleanup should remove
    out.append(Deal(store="Jumbo", title="Bekijk alle aanbiedingen", price_now=1.0).finalize())
    out.append(Deal(store="PLUS", title="Schrijf je in voor de nieuwsbrief", deal_text="gratis").finalize())
    return out


def build(weeks=6, today=date(2026, 11, 18), seed=3):
    rnd = random.Random(seed)
    hist = Path(tempfile.mkdtemp())
    payload = None
    for w in range(weeks, -1, -1):
        day = today - timedelta(weeks=w)
        monday = day - timedelta(days=day.weekday())
        deals = week_deals(monday, rnd)
        if w == 0:   # today: also next week's deals
            deals += week_deals(monday + timedelta(days=7), rnd)
        deals = enrich(deals, day)
        counts = {}
        for d in deals:
            counts[d.store] = counts.get(d.store, 0) + 1
        if w == 0:
            counts["Kruidvat"] = 0          # simulate a broken store today
            deals = [d for d in deals if d.store != "Kruidvat"]
        past = history.load(hist, day)
        history.annotate(deals, past, day)
        warnings = history.health(counts, past)
        history.save(hist, day, deals, counts)
        payload = {"generated": f"{day.isoformat()}T06:20", "today": day.isoformat(),
                   "history_days": len(past),
                   "stores": {s: {"ok": True, "count": counts.get(s, 0)} for s in STORES},
                   "warnings": warnings,
                   "deals": [dict(d.to_dict(), pay=d.pay_per_item()) for d in deals]}
    return payload


if __name__ == "__main__":
    p = build()
    out = Path(__file__).parents[1] / "output"
    out.mkdir(exist_ok=True)
    write_html(p, out / "sample.html")
    print(f"{len(p['deals'])} deals, warnings: {p['warnings']}\n-> {out / 'sample.html'}")
