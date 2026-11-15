"""Albert Heijn: uses the same API as the Appie app (anonymous token, no login)."""
from __future__ import annotations

from datetime import date

import requests

from .models import Deal

API = "https://api.ah.nl"
HEADERS = {
    "User-Agent": "Appie/8.22.3 Model/phone Android/7.0-API24",
    "x-application": "AHWEBSHOP",
    "Content-Type": "application/json; charset=UTF-8",
}


def _price(v):
    if isinstance(v, dict):
        v = v.get("now") or v.get("amount") or v.get("value")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_deal(p: dict, period: dict) -> Deal:
    images = p.get("images") or []
    img = ""
    if images:
        # pick the largest image
        img = sorted(images, key=lambda i: i.get("width", 0))[-1].get("url", "")
    wid = p.get("webshopId") or p.get("id")
    labels = p.get("discountLabels") or []
    label_txt = ", ".join(l.get("defaultDescription", "") for l in labels if isinstance(l, dict))
    return Deal(
        store="Albert Heijn",
        title=p.get("title", ""),
        deal_text=p.get("bonusMechanism") or label_txt or (p.get("shield") or {}).get("text", ""),
        price_now=_price(p.get("currentPrice")),
        price_was=_price(p.get("priceBeforeBonus")),
        size=p.get("salesUnitSize", "") or p.get("unitPriceDescription", ""),
        category=p.get("mainCategory", ""),
        valid_from=p.get("bonusStartDate") or period.get("bonusStartDate", ""),
        valid_until=p.get("bonusEndDate") or period.get("bonusEndDate", ""),
        image=img,
        url=f"https://www.ah.nl/producten/product/wi{wid}" if wid else "https://www.ah.nl/bonus",
    )


def fetch(debug_dir=None, headful=False, **kw) -> list[Deal]:
    """App API first; AH sometimes breaks it (HTTP 500), then read www.ah.nl/bonus instead."""
    try:
        deals = _from_app()
        if deals:
            return deals
        reason = "app API returned no deals"
    except Exception as e:
        reason = str(e).splitlines()[0][:100]
    print(f"    Albert Heijn: {reason} -> using the website instead")
    from . import browser
    return browser.fetch_page("Albert Heijn", "https://www.ah.nl/bonus",
                              headful=headful, debug_dir=debug_dir, **kw)


def _from_app() -> list[Deal]:
    s = requests.Session()
    s.headers.update(HEADERS)
    tok = s.post(f"{API}/mobile-auth/v1/auth/token/anonymous",
                 json={"clientId": "appie"}, timeout=20)
    tok.raise_for_status()
    s.headers["Authorization"] = f"Bearer {tok.json()['access_token']}"

    meta = s.get(f"{API}/mobile-services/bonuspage/v1/metadata", timeout=20)
    meta.raise_for_status()
    today = date.today().isoformat()
    deals: list[Deal] = []
    seen = set()

    for period in meta.json().get("periods", []):
        if not (period.get("bonusStartDate", "") <= today <= period.get("bonusEndDate", "9999")):
            continue
        for section in period.get("urlMetadataList", []):
            r = s.get(f"{API}/mobile-services/{section['url'].lstrip('/')}", timeout=30)
            if not r.ok:
                continue
            for item in r.json().get("bonusGroupOrProducts", []):
                products = []
                if item.get("product"):
                    products.append(item["product"])
                if item.get("bonusGroup"):
                    g = s.get(f"{API}/mobile-services/bonuspage/v1/segment", timeout=30, params={
                        "date": today, "segmentId": item["bonusGroup"]["id"],
                        "includeActivatableDiscount": "false"})
                    if g.ok:
                        products += g.json().get("products", [])
                for p in products:
                    key = p.get("webshopId") or p.get("title")
                    if key in seen:
                        continue
                    seen.add(key)
                    deals.append(_to_deal(p, period))
    return deals
