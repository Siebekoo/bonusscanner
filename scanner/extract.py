"""Turn arbitrary JSON (whatever a store's website loads) into Deal objects.

Most shop websites load their offers as JSON in the background. Rather than
hand-writing a parser per site (which breaks every few months), we walk all
captured JSON and pick out objects that *look like* a product on offer:
they have a name, and a price and/or a promotion text.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from .models import Deal

TITLE_KEYS = ("title", "name", "productName", "displayName", "productTitle", "label")
NOW_KEYS = ("price_now", "promotionalPrice", "promotionPriceValue", "offerPrice", "promotionPrice", "promoPrice", "discountPrice",
            "salePrice", "specialPrice", "bonusPrice", "currentPrice", "price", "sellingPrice",
            "actionPrice", "now", "amount", "value")
WAS_KEYS = ("oldPrice", "originalPrice", "regularPrice", "priceBefore", "priceBeforeBonus",
            "wasPrice", "listPrice", "strikethroughPrice", "previousPrice", "fromPrice",
            "basePrice", "was", "old")
PROMO_HINT = re.compile(r"promo|promotion|offer|bonus|discount|korting|actie|sticker|"
                        r"badge|shield|mechanism|tag|label|deal", re.I)
DEAL_WORDS = re.compile(r"\d\s*\+\s*\d|gratis|halve prijs|korting|%|voor\s*€?\s*\d|"
                        r"\d+\s*voor|op=op|stuntprijs|actie", re.I)
IMG_KEYS = ("image", "imageUrl", "imageURL", "img", "thumbnail", "picture", "images", "imageInfo")
URL_KEYS = ("url", "link", "href", "productUrl", "canonicalUrl", "slug")
SIZE_KEYS = ("size", "packSize", "salesUnitSize", "quantity", "unitSize", "packaging",
             "subtitle", "contentDescription")
DATE_FROM = ("startDate", "validFrom", "fromDate", "start", "dateFrom", "offerStartDate")
DATE_TO = ("endDate", "validUntil", "validTo", "toDate", "end", "dateTo", "offerEndDate")

PRICE_STR = re.compile(r"(\d{1,4})[.,](\d{2})(?!\d)")


def parse_price(v: Any, cents: bool = False) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, dict):
        for k in ("amount", "value", "now", "price", "centAmount", "cents"):
            if k in v:
                return parse_price(v[k], cents or k in ("centAmount", "cents"))
        return None
    if isinstance(v, (int, float)):
        val = v / 100 if cents else float(v)
        return val if 0 < val < 2000 else None
    if isinstance(v, str):
        m = PRICE_STR.search(v.replace(" ", ""))
        if m:
            return float(f"{m.group(1)}.{m.group(2)}")
        if v.strip().isdigit():
            return parse_price(int(v), cents)
    return None


def _first(d: dict, keys: Iterable[str]):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None


def _first_str(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        return _first_str(v[0])
    if isinstance(v, dict):
        for k in ("url", "src", "href", "value", "text", "name", "title", "path"):
            if k in v:
                return _first_str(v[k])
    return ""


def _find_price(d: dict, keys, cents, depth=0) -> Optional[float]:
    """Look for a price under one of `keys`, also one level into nested 'price' objects."""
    for k in keys:
        if k in d:
            p = parse_price(d[k], cents or "cent" in k.lower())
            if p:
                return p
    if depth < 2:
        for k, v in d.items():
            if isinstance(v, dict) and re.search(r"price|prijs|promotion|offer", k, re.I):
                p = _find_price(v, keys, cents, depth + 1)
                if p:
                    return p
    return None


def _promo_texts(d: dict, depth=0) -> list[str]:
    out = []
    for k, v in d.items():
        hinted = bool(PROMO_HINT.search(k))
        if isinstance(v, str) and 1 < len(v) < 60 and (hinted and DEAL_WORDS.search(v)):
            out.append(v)
        elif isinstance(v, (dict, list)) and depth < 3 and hinted:
            items = v if isinstance(v, list) else [v]
            for it in items[:5]:
                if isinstance(it, dict):
                    for s in it.values():
                        if isinstance(s, str) and 1 < len(s) < 60 and DEAL_WORDS.search(s):
                            out.append(s)
                    out += _promo_texts(it, depth + 1)
                elif isinstance(it, str) and DEAL_WORDS.search(it) and len(it) < 60:
                    out.append(it)
    # de-duplicate, keep order
    seen, res = set(), []
    for t in out:
        t = re.sub(r"<[^>]+>", " ", t).strip()
        if t.lower() not in seen:
            seen.add(t.lower())
            res.append(t)
    return res


SKIP_PRICE = re.compile(r"unit|per_|perkg|perkilo|perliter|perunit|per100|kilo|liter|deposit|statiegeld|tax|btw|vat|^min|^max|saving|save|discount", re.I)


def _all_prices(d: dict, cents: bool, depth=0) -> list[float]:
    """Every euro amount in the price-ish part of a product object (not unit prices)."""
    out = []
    for k, v in d.items():
        if SKIP_PRICE.search(k):
            continue
        priceish = re.search(r"price|prijs|amount|^now$|^was$|^old$", k, re.I)
        if priceish and not isinstance(v, (dict, list)):
            p = parse_price(v, cents or "cent" in k.lower())
            if p:
                out.append(p)
        elif isinstance(v, dict) and depth < 3 and (priceish or depth > 0):
            out += _all_prices(v, cents, depth + 1)
    return out


def looks_like_offer(d: dict, cents: bool, ctx: dict | None = None) -> Optional[Deal]:
    ctx = ctx or {}
    title = _first(d, TITLE_KEYS)
    if not isinstance(title, str) or not (3 <= len(title) <= 150):
        return None
    if title.startswith("http") or "{" in title:
        return None
    now = _find_price(d, NOW_KEYS, cents)
    was = _find_price(d, WAS_KEYS, cents)
    prices = sorted(set(_all_prices(d, cents)))
    if len(prices) >= 2:
        # a sale price and a regular price: the lower one is what you pay now
        if not was or was <= (now or 0):
            was = prices[-1]
        if not now or now >= was:
            now = prices[0]
    elif prices and not now:
        now = prices[0]
    promos = _promo_texts(d) or ctx.get("promos", [])
    if not (now or promos):
        return None
    if was and now and was < now:
        now, was = was, now
    if was == now:
        was = None
    size = _first(d, SIZE_KEYS)
    return Deal(
        store="",
        title=title,
        deal_text=" · ".join(promos[:2]),
        price_now=now,
        price_was=was,
        size=_first_str(size) if size else "",
        image=_first_str(_first(d, IMG_KEYS)),
        url=_first_str(_first(d, URL_KEYS)),
        valid_from=str(_first(d, DATE_FROM) or ctx.get("from", ""))[:10],
        valid_until=str(_first(d, DATE_TO) or ctx.get("until", ""))[:10],
    )


def walk(obj: Any, cents: bool = False, max_nodes: int = 300_000) -> list[Deal]:
    """Depth-first walk. A product-like dict is taken as a deal and not descended into.
    Deal text and dates on a parent object (e.g. {"tag": "1+1 gratis", "product": {...}})
    are passed down to the product found inside it."""
    found: list[Deal] = []
    stack = [(obj, {})]
    n = 0
    while stack and n < max_nodes:
        n += 1
        cur, ctx = stack.pop()
        if isinstance(cur, dict):
            deal = looks_like_offer(cur, cents, ctx)
            # Containers (dicts holding lists of products) also have a 'name'; skip those.
            holds_list = any(isinstance(v, list) and len(v) > 3 and isinstance(v[0], dict)
                             for v in cur.values())
            if deal and not holds_list:
                found.append(deal)
                continue
            child_ctx = ctx
            if not holds_list:
                promos = _promo_texts(cur)
                frm, until = _first(cur, DATE_FROM), _first(cur, DATE_TO)
                if promos or frm or until:
                    child_ctx = {"promos": promos or ctx.get("promos", []),
                                 "from": frm or ctx.get("from", ""),
                                 "until": until or ctx.get("until", "")}
            stack.extend((v, child_ctx) for v in cur.values())
        elif isinstance(cur, list):
            stack.extend((v, ctx) for v in reversed(cur))
    return found


def dedupe(deals: list[Deal]) -> list[Deal]:
    best: dict[tuple, Deal] = {}
    for d in deals:
        key = (d.title.lower().strip(), d.price_now)
        old = best.get(key)
        score = lambda x: bool(x.deal_text) + bool(x.price_was) + bool(x.image) + bool(x.url)
        if old is None or score(d) > score(old):
            best[key] = d
    return list(best.values())
