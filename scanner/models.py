"""The one shape every store's deals get converted into."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from typing import Optional

DIRECT = "korting"        # cheaper even if you buy just one
MULTI = "meer kopen"      # only cheaper when you buy several (1+1, 2e halve prijs, 3 voor €5)


@dataclass
class Deal:
    store: str                      # e.g. "Albert Heijn"
    title: str                      # product name
    deal_text: str = ""             # "1+1 gratis", "2e halve prijs", "25% korting" ...
    price_now: Optional[float] = None
    price_was: Optional[float] = None
    size: str = ""                  # "500 g", "6 x 330 ml" ...
    category: str = ""
    valid_from: str = ""            # ISO date if known
    valid_until: str = ""
    image: str = ""
    url: str = ""
    deal_type: str = ""             # DIRECT or MULTI (see above)
    min_qty: int = 1                # how many you must buy to get the deal
    discount_pct: Optional[int] = field(default=None)    # direct discount on a single item
    effective_pct: Optional[int] = field(default=None)   # discount per item IF you buy min_qty

    def finalize(self) -> "Deal":
        self.title = " ".join((self.title or "").split())
        self.deal_text = " ".join((self.deal_text or "").split())
        if self.price_now is not None:
            self.price_now = round(float(self.price_now), 2)
        if self.price_was is not None:
            self.price_was = round(float(self.price_was), 2)

        qty, pct = classify(self.deal_text, self.price_was or self.price_now)
        price_pct = None
        if self.price_now and self.price_was and self.price_was > self.price_now:
            price_pct = round((1 - self.price_now / self.price_was) * 100)

        if qty > 1:
            # Multi-buy: no discount on a single item. Prices shown by shops for these are
            # often the per-item price when you buy the full amount.
            self.deal_type, self.min_qty = MULTI, qty
            self.effective_pct = pct if pct is not None else price_pct
            self.discount_pct = None
        else:
            self.deal_type, self.min_qty = DIRECT, 1
            self.discount_pct = price_pct if price_pct is not None else pct
            self.effective_pct = self.discount_pct
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def classify(text: str, unit_price: Optional[float] = None) -> tuple[int, Optional[int]]:
    """Return (items you must buy, discount per item when you do) for a Dutch deal text.

    1+1 gratis      -> (2, 50)     2+1 gratis   -> (3, 33)     1+2 gratis -> (3, 67)
    2e halve prijs  -> (2, 25)     2e gratis    -> (2, 50)
    3 voor 5,00     -> (3, depends on the normal price)
    25% korting     -> (1, 25)     2e artikel 50% korting -> (2, 25)
    """
    t = (text or "").lower().replace(" ", " ")

    m = re.search(r"(\d+)\s*\+\s*(\d+)", t)                       # 1+1, 2+1, 2+2, 1+2
    if m:
        pay, free = int(m.group(1)), int(m.group(2))
        if 0 < pay + free <= 20:
            return pay + free, round(free / (pay + free) * 100)

    m = re.search(r"(\d+)\s*e\s*(?:artikel|stuk|product)?\s*halve\s*prijs", t)
    if m or "tweede halve prijs" in t:
        n = int(m.group(1)) if m else 2
        return n, round(50 / n)
    m = re.search(r"(\d+)\s*e\s*(?:artikel|stuk|product)?\s*gratis", t)
    if m:
        n = int(m.group(1))
        return n, round(100 / n)
    m = re.search(r"(\d+)\s*e\s*(?:artikel|stuk|product)?\s*(\d{1,2})\s*%", t)
    if m:
        n, p = int(m.group(1)), int(m.group(2))
        return n, round(p / n)

    m = re.search(r"(?<![\d.,€])(\d{1,2})\s*(?:stuks?\s*)?voor\s*€?\s*(\d+(?:[.,]\d{1,2})?)", t)   # 3 voor 5,00
    if m:
        n, total = int(m.group(1)), _num(m.group(2))
        if n == 1:                                   # "1 voor 24.50" is just a lower price
            pct = round((1 - total / unit_price) * 100) if unit_price and unit_price > total else None
            return 1, pct
        pct = None
        if unit_price and unit_price * n > total:
            pct = round((1 - total / (unit_price * n)) * 100)
        return n, pct

    m = re.search(r"(?:bij|vanaf|per)\s*(\d+)\s*(?:stuks?|st\.?|artikelen)", t)   # "25% bij 2 stuks"
    pct_m = re.search(r"(\d{1,2})\s*%", t)
    if m and int(m.group(1)) > 1:
        return int(m.group(1)), int(pct_m.group(1)) if pct_m else None

    if pct_m:
        return 1, int(pct_m.group(1))
    return 1, None
