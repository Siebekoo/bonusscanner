"""PLUS: its offers page loads every deal in one data file (GetPromotionList).

The page itself only shows deal *groups* ("Bolletje · 2 voor 3,00"), so reading the
cards gives poor results. The data file has brand, name, size, prices, label and dates.

Price conventions in that file (checked against the live site, Nov 2026):
- multi-buy ("1+1 GRATIS", "2 VOOR 7.50"): NewPrice and PriceOriginal_Lowest are the
  totals for the whole deal (e.g. Pampers 2+1: new 31.98, original 47.97 for 3 packs)
- everything else: prices are per item
"""
from __future__ import annotations

import re

from .models import Deal, classify


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _label(text: str) -> str:
    """'25 % KORTING' -> '25% korting', '2 VOOR 7.50' -> '2 voor €7,50'."""
    t = re.sub(r"\s+", " ", (text or "").strip()).lower()
    t = re.sub(r"(\d)\s*%", r"\1%", t)
    t = re.sub(r"voor (\d+)[.,](\d{2})", r"voor €\1,\2", t)
    t = re.sub(r"(\d+ gram) (\d+)[.,](\d{2})", r"\1 voor €\2,\3", t)
    return t.replace("op=op", "OP=OP")


def parse(captured: list[dict]) -> list[Deal]:
    deals = []
    for resp in captured:
        if "GetPromotionList" not in resp.get("url", ""):
            continue
        try:
            cats = resp["data"]["data"]["PromotionOfferList"]["List"]
        except (KeyError, TypeError):
            continue
        for cat in cats:
            for o in (cat.get("Category") or {}).get("Offers", {}).get("List", []):
                if o.get("IsFreeDeliveryOffer"):
                    continue
                label = _label(o.get("DisplayInfo_Label") or o.get("DisplayInfo_PromotionBasedLabel") or "")
                if label.startswith("gratis bezorging"):
                    continue
                new = _f(o.get("NewPrice"))
                orig = _f(o.get("PriceOriginal_Product"))
                lo, hi = _f(o.get("PriceOriginal_Lowest")), _f(o.get("PriceOriginal_Highest"))
                qty, _ = classify(label)
                if qty > 1:
                    # totals for the whole deal -> per item
                    was_total = orig * qty if orig else (lo or hi)
                    price_now = round(new / qty, 2) if new else None
                    price_was = round(was_total / qty, 2) if was_total else None
                else:
                    price_now = new or None
                    price_was = orig or lo or hi or None
                brand, name = (o.get("Brand") or "").strip(), (o.get("Name") or "").strip()
                title = name if not brand or name.lower().startswith(brand.lower()) else f"{brand} {name}"
                example = (o.get("Example") or "").strip()
                size = example[4:] if example.lower().startswith("per ") else (o.get("Package") or "")
                if example.lower().startswith("bijv."):
                    title += f" ({example})"
                slug = o.get("Slug") or ""
                url = (f"https://www.plus.nl/product/{slug}" if re.search(r"-\d{4,}$", slug)
                       and not slug.startswith("4455") else f"https://www.plus.nl/aanbiedingen/{slug}")
                deals.append(Deal(store="PLUS", title=title, deal_text=label, price_now=price_now,
                                  price_was=price_was, size=size, image=o.get("ImageURL") or "",
                                  url=url, valid_from=o.get("StartDate") or "",
                                  valid_until=o.get("EndDate") or ""))
    return deals
