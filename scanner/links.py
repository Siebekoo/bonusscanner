"""Make every product link lead somewhere useful.

Many stores' deal data has no product link, so a tile would only open the general offers
page. In that case we build a direct product link when the data has a product number
(Jumbo, Lidl), or else a link to the store's own search results for that product.

All addresses below were tested on the live sites (Nov 2026).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import quote_plus

SEARCH = {
    "Albert Heijn": "https://www.ah.nl/zoeken?query={q}",
    "Jumbo": "https://www.jumbo.com/producten/?searchType=keyword&searchTerms={q}",
    "Aldi": "https://www.aldi.nl/zoeken.html?query={q}",
    "Lidl": "https://www.lidl.nl/q/search?q={q}",
    "Kruidvat": "https://www.kruidvat.nl/search?q={q}&text={q}",
    "Etos": "https://www.etos.nl/search/?q={q}",
    "PLUS": "https://www.plus.nl/zoekresultaten?SearchTerm={q}",
    "Dirk": "https://www.dirk.nl/zoeken/producten/{q}",
    "DekaMarkt": "https://www.dekamarkt.nl/zoeken/{q}",
    "Vomar": "https://www.vomar.nl/zoeken?search={q}",
    "Gall & Gall": "https://www.gall.nl/zoeken?q={q}",
    "Action": "https://www.action.com/nl-nl/search/?q={q}",
}
# Links that only lead to a general overview page, not to the product
GENERIC = re.compile(r"/(aanbiedingen|acties|bonus|weekactie|folder)(/nu|/dezeweek|/deze-week|\.html)?/?(\?.*)?$"
                     r"|/c/aanbiedingen/a\d+/?$", re.I)


def slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def search_terms(title: str) -> str:
    """Shorter, cleaner query: drop '(Bijv. ...)', sizes and 'Alle ...' wording."""
    t = re.sub(r"\(.*?\)", " ", title)
    t = re.sub(r"\b\d+([.,]\d+)?\s*(x\s*\d+\s*)?(kg|g|gr|gram|ml|cl|l|liter|stuks?|st)\b", " ", t, flags=re.I)
    t = re.sub(r"^\s*alle\s+", "", t, flags=re.I)
    return " ".join(t.split()[:6])


def search_url(store: str, title: str) -> Optional[str]:
    tpl = SEARCH.get(store)
    q = search_terms(title)
    return tpl.format(q=quote_plus(q)) if tpl and q else None


def product_url(store: str, title: str, raw: Optional[dict]) -> Optional[str]:
    """Direct product page from a product number in the store's own data."""
    if not isinstance(raw, dict):
        return None
    pid = str(raw.get("id") or "")
    name = raw.get("name") or raw.get("title") or title
    if store == "Lidl" and pid.isdigit():
        return f"https://www.lidl.nl/p/{slug(name)}/p{pid}"
    if store == "Jumbo" and pid.isdigit() and ("discountValue" in raw or "stickers" in raw):
        return f"https://www.jumbo.com/aanbiedingen/{slug(name)}/{pid}"
    return None


def is_generic(url: str, page_urls=()) -> bool:
    if not url:
        return True
    u = url.rstrip("/")
    return any(u == p.rstrip("/") for p in page_urls if p) or bool(GENERIC.search(url))


def fix(deal, page_urls=()) -> None:
    """Replace a missing or overview-page link with a product or search link."""
    if not is_generic(deal.url, page_urls):
        return
    better = product_url(deal.store, deal.title, getattr(deal, "_raw", None)) or search_url(deal.store, deal.title)
    if better:
        deal.url = better
