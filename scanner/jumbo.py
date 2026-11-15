"""Jumbo: try the app API first; if Jumbo has retired it, fall back to the website."""
from __future__ import annotations

import requests

from .extract import walk, dedupe
from .models import Deal
from . import browser

APP_URL = "https://mobileapi.jumbo.com/{v}/promotion-overview"
WEB_URL = "https://www.jumbo.com/aanbiedingen/nu"


def _from_app() -> list[Deal]:
    headers = {"User-Agent": "Jumbo/9.0 (Android)"}
    for v in ("v17", "v16", "v15"):
        try:
            r = requests.get(APP_URL.format(v=v), headers=headers, timeout=20)
        except requests.RequestException:
            continue
        if r.ok and "json" in r.headers.get("content-type", ""):
            deals = walk(r.json(), cents=False)
            if deals:
                return deals
    return []


def fetch(headful=False, debug_dir=None, **kw) -> list[Deal]:
    deals = _from_app()
    if not deals:
        return browser.fetch_page("Jumbo", WEB_URL, cents=True, headful=headful,
                                  debug_dir=debug_dir)
    for d in deals:
        d.store = "Jumbo"
        d.url = d.url if (d.url or "").startswith("http") else WEB_URL
    return dedupe(deals)
