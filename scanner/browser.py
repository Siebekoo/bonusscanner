"""Generic scraper: open a store's offers page in a real (headless) browser,
accept cookies, scroll until everything is loaded, and collect:

1. every JSON response the page fetched in the background,
2. JSON embedded in the page (JSON-LD, __NEXT_DATA__, __NUXT__ ...),
3. as a last resort, the visible product cards on the page.

All of it goes through extract.walk() to find the deals.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

from .extract import walk, dedupe, parse_price
from .models import Deal

COOKIE_BUTTON = re.compile(
    r"^(alles? )?(accepteren|accepteer|akkoord|toestaan|alle cookies|accept( all)?|"
    r"ik ga akkoord|ja,? (ik ga akkoord|prima)|cookies accepteren|alles toestaan)", re.I)
MORE_BUTTON = re.compile(r"(toon|laad|bekijk) (meer|alle)|meer (laden|tonen|aanbiedingen)", re.I)

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['nl-NL', 'nl', 'en']});
window.chrome = window.chrome || {runtime: {}};
"""

EMBEDDED_JS = """
() => {
  const out = [];
  document.querySelectorAll('script[type="application/ld+json"], script#__NEXT_DATA__, '
                            + 'script[type="application/json"]').forEach(s => {
    try { out.push(JSON.parse(s.textContent)); } catch (e) {}
  });
  for (const k of ['__NUXT__', '__NEXT_DATA__', '__INITIAL_STATE__', '__APOLLO_STATE__',
                   '__PRELOADED_STATE__', 'dataLayer']) {
    try { if (window[k]) out.push(JSON.parse(JSON.stringify(window[k]))); } catch (e) {}
  }
  return out;
}
"""

# Last resort: find repeated "card" elements that contain a euro price.
DOM_CARDS_JS = r"""
() => {
  const priceRe = /\d+[.,]\d{2}|\d+\s*voor|\d\s*\+\s*\d|gratis|korting|%/i;
  const sel = '[class*="product"], [class*="Product"], [class*="tile"], [class*="card"], '
            + '[class*="offer"], [class*="promo"], article, li';
  // a product photo, not a small icon (Gall & Gall puts an info.svg next to each price)
  const isPhoto = img => {
    const src = img.currentSrc || img.src || img.getAttribute('data-src') || '';
    if (/\.svg(\?|$)|icon|logo|sprite|badge|flag/i.test(src)) return false;
    const w = img.naturalWidth || img.width || 0;
    return w === 0 || w >= 48;      // 0 = not loaded yet (lazy), give it the benefit of the doubt
  };
  const photoIn = el => [...el.querySelectorAll('img')].find(isPhoto);
  const cands = [...document.querySelectorAll(sel)].filter(el => {
    const t = el.innerText || '';
    return t.length > 3 && t.length < 600 && priceRe.test(t) && photoIn(el);
  });
  // keep the innermost matching elements only
  const inner = cands.filter(el => !cands.some(o => o !== el && el.contains(o)));
  return inner.slice(0, 1500).map(el => {
    const img = photoIn(el);
    const nameEl = el.querySelector('[class*="name" i], [class*="title" i], [class*="description" i], h2, h3, h4, [itemprop="name"]');
    const links = [...el.querySelectorAll('a[href]')].map(a => (a.getAttribute('title') || a.innerText || '').trim())
                    .filter(t => t.length > 3 && !/\d+[.,]\d{2}/.test(t));
    const a = el.closest('a') || el.querySelector('a');
    // screen-reader labels often hold the full price ("Van: € 32.99 voor: € 24.99") when the
    // visible text doesn't (Gall & Gall shows "24." and adds the cents with CSS)
    const parts = [el, ...el.querySelectorAll('[aria-label]')]
      .map(x => (x.getAttribute && x.getAttribute('aria-label')) || '')
      .filter(t => /€|\d+[.,]\d{2}/.test(t));
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { const t = w.currentNode.textContent.trim(); if (t) parts.push(t); }
    return { text: parts.join('\n'), img: img ? (img.currentSrc || img.src || img.getAttribute('data-src') || '') : '',
             alt: img ? img.alt : '', href: a ? a.href : '',
             name: nameEl ? nameEl.innerText.trim() : (links.sort((x, y) => y.length - x.length)[0] || '') };
  });
}
"""


PRICE_RE = r"\d+[.,]\d{2}"
DEAL_LINE = re.compile(r"\d\s*\+\s*\d|gratis|halve prijs|korting|%|(?<![\d.,€])\d{1,2}\s*voor\b", re.I)


GENERIC_ALT = re.compile(r"^(info|image|img|product|afbeelding|foto|photo|picture|thumbnail|icon|"
                         r"truck|box|logo|banner)?$", re.I)


def _card_title(c: dict, text_lines: list[str]) -> str:
    """Product name: the tile's name element, a meaningful image alt, the longest text line,
    or as a last resort the product link (gall.nl/bacardi-carta-blanca-150cl-769851.html)."""
    for cand in (c.get("name", ""), c.get("alt", "")):
        cand = " ".join((cand or "").split())
        if cand and not GENERIC_ALT.match(cand) and not re.fullmatch(r"[\d\s.,€%+-]*", cand):
            return cand[:140]
    useful = [l for l in text_lines if not re.match(r"(normaal|van|nu|per|vanaf|op=op)\b", l, re.I)]
    if useful:
        return max(useful, key=len)
    slug = (c.get("href") or "").rstrip("/").split("/")[-1]
    slug = re.sub(r"[-_]\d{4,}$", "", re.sub(r"\.html?$", "", slug))
    if len(slug) > 3:
        words = slug.replace("-", " ").replace("_", " ").strip()
        return words[:1].upper() + words[1:]
    return ""


def _cards_to_deals(cards: list[dict]) -> list[Deal]:
    deals = []
    for c in cards:
        text = c["text"]
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        # prices split over two elements: "24." + "99" or "24" + ",99" -> "24.99"
        merged = []
        for l in lines:
            if merged and re.fullmatch(r"[.,]?\d{2}", l) and re.fullmatch(r"(€\s*)?\d+[.,]?", merged[-1]):
                merged[-1] = merged[-1].rstrip(".,") + "." + l.lstrip(".,")
            else:
                merged.append(l)
        lines = merged
        text = "\n".join(lines)
        now = was = None
        # "van € 14.99 voor € 7.50"
        m = re.search(rf"van:?\s*€?\s*({PRICE_RE})\s*voor:?\s*€?\s*({PRICE_RE})", text, re.I)
        if m:
            was, now = parse_price(m.group(1)), parse_price(m.group(2))
        promo = [l for l in lines if DEAL_LINE.search(l) and len(l) < 50
                 and not re.match(r"van:?\s*€", l, re.I)]
        if now is None:
            prices = []
            for l in lines:
                if l in promo or l == c.get("alt") or len(l) > 40 \
                        or re.search(r"per\s*(kg|kilo|liter|l\b|stuk)|/\s*(kg|l)\b", l, re.I):
                    continue
                # skip numbers that are sizes: "6.75 l", "1,5 kg", "33 x 42.5 cm"
                l = re.sub(r"\d+[.,]\d+\s*(?:x|×|l\b|ltr|liter|kg|g\b|gr|ml|cl|cm|mm|m\b|w\b|v\b)", " ", l, flags=re.I)
                prices += [parse_price(x) for x in re.findall(PRICE_RE, l)]
            prices = [p for p in prices if p]
            if prices:
                now = min(prices)
                was = max(prices) if len(set(prices)) > 1 else None
        text_lines = [l for l in lines if not re.search(PRICE_RE, l)
                      and l not in promo and len(l) > 3]
        title = _card_title(c, text_lines)
        if not title:
            continue
        deals.append(Deal(store="", title=title, deal_text=" · ".join(promo[:2]),
                          price_now=now, price_was=was,
                          image=c.get("img", ""), url=c.get("href", "")))
    return deals


def fetch_page(store_name: str, url: str, *, extra_urls=(), cents=False, headful=False,
               offscreen: bool = False, parser=None,
               debug_dir: Path | None = None, max_scrolls: int = 40, **_) -> list[Deal]:
    from playwright.sync_api import sync_playwright

    captured: list = []

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct and resp.request.resource_type in ("xhr", "fetch", "document"):
                captured.append({"url": resp.url, "data": resp.json()})
        except Exception:
            pass

    with sync_playwright() as p:
        browser = _launch(p, headful, offscreen)
        ctx = browser.new_context(
            locale="nl-NL", timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"))
        ctx.add_init_script(STEALTH_JS)
        page = ctx.new_page()
        page.on("response", on_response)

        embedded, cards = [], []
        for target in [url, *extra_urls]:
            page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2500)
            _accept_cookies(page)
            _scroll_all(page, max_scrolls)
            try:
                embedded += page.evaluate(EMBEDDED_JS)
            except Exception:
                pass
            try:
                cards += page.evaluate(DOM_CARDS_JS)
            except Exception:
                pass
            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                slug = re.sub(r"\W+", "_", store_name.lower())
                page.screenshot(path=str(debug_dir / f"{slug}.png"), full_page=False)
                try:
                    (debug_dir / f"{slug}.html").write_text(page.content()[:5_000_000], encoding="utf-8")
                except Exception:
                    pass
        browser.close()

    deals, source = [], "json"
    if parser:                              # store-specific reader (e.g. PLUS)
        try:
            deals = parser(captured)
            source = "store reader"
        except Exception as e:
            print(f"    {store_name}: store reader failed ({e}), using the general one")
    if not deals:
        deals = walk([c["data"] for c in captured] + embedded, cents=cents)
        source = "json"
    if len(deals) < 5 and source == "json":                      # JSON gave nothing useful: use visible cards
        deals = _cards_to_deals(cards)
        source = "page"

    if debug_dir:
        slug = re.sub(r"\W+", "_", store_name.lower())
        (debug_dir / f"{slug}_responses.json").write_text(
            json.dumps(captured, ensure_ascii=False, indent=1)[:50_000_000], encoding="utf-8")
        sample = [{"found": {k: v for k, v in d.to_dict().items() if v not in ("", None, [], 1)},
                   "raw": getattr(d, "_raw", None)} for d in deals[:40]]
        (debug_dir / f"{slug}_deals_raw.json").write_text(
            json.dumps(sample, ensure_ascii=False, indent=1, default=str)[:2_000_000], encoding="utf-8")
        (debug_dir / f"{slug}_cards.json").write_text(
            json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    [debug] {len(captured)} JSON responses, {len(cards)} cards, used: {source}")
        print(f"    [debug] screenshot: {debug_dir / (slug + '.png')}")

    for d in deals:
        d.store = store_name
        if d.url and not d.url.startswith("http"):
            d.url = urljoin(url, d.url)
        if d.image and d.image.startswith("//"):
            d.image = "https:" + d.image
        if not d.url:
            d.url = url
    return dedupe(deals)


OFFER_LINK = re.compile(r"aanbieding|\bacties?\b|/acties|folder|bonus|weekdeal|weekactie|"
                        r"deals?\b|voordeel|korting", re.I)
NOT_OFFER = re.compile(r"voorwaarden|cookie|privacy|vacature|klantenservice|\.pdf|login|inlog|"
                       r"account|app\b|nieuwsbrief|contact|over-ons|faq", re.I)


def discover_offer_urls(url: str, *, headful=False, offscreen=False, limit=3) -> list[str]:
    """Open the store's homepage and return links that look like an offers page."""
    from urllib.parse import urlparse
    from playwright.sync_api import sync_playwright
    root = "{0.scheme}://{0.netloc}/".format(urlparse(url))
    host = urlparse(url).netloc.replace("www.", "")
    with sync_playwright() as p:
        browser = _launch(p, headful, offscreen)
        ctx = browser.new_context(locale="nl-NL", user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"))
        ctx.add_init_script(STEALTH_JS)
        page = ctx.new_page()
        page.goto(root, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(2500)
        _accept_cookies(page)
        links = page.evaluate("""() => [...document.querySelectorAll('a[href]')]
            .map(a => ({href: a.href, text: (a.innerText || a.getAttribute('aria-label') || '').trim()}))""")
        browser.close()
    scored = {}
    for l in links:
        href, text = l["href"].split("#")[0], l["text"][:60]
        if host not in href or NOT_OFFER.search(href) or href.rstrip("/") == root.rstrip("/"):
            continue
        if not (OFFER_LINK.search(href) or OFFER_LINK.search(text)):
            continue
        score = (3 if re.search(r"aanbieding", text + href, re.I) else 0) \
              + (2 if re.search(r"deze week|alle", text, re.I) else 0) - href.count("/") * 0.1
        scored[href] = max(score, scored.get(href, -99))
    return [h for h, _ in sorted(scored.items(), key=lambda x: -x[1])][:limit]


def _launch(p, headful, offscreen=False):
    """Your normal Chrome/Edge if installed (harder for sites to tell apart from a person),
    otherwise Playwright's own Chromium."""
    args = ["--disable-blink-features=AutomationControlled"]
    if offscreen:
        args += ["--window-position=-32000,-32000", "--window-size=1366,900"]
    errors = []
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=not headful, args=args, **kw)
        except Exception as e:
            errors.append(str(e).splitlines()[0])
    raise RuntimeError("No browser found. Run:  python -m playwright install chromium\n"
                       + "\n".join(errors))


def _accept_cookies(page):
    for frame in [page.main_frame, *page.frames]:
        try:
            for btn in frame.get_by_role("button").all()[:60]:
                txt = (btn.inner_text(timeout=500) or "").strip()
                if COOKIE_BUTTON.search(txt):
                    btn.click(timeout=2000)
                    page.wait_for_timeout(1000)
                    return
        except Exception:
            continue


def _scroll_all(page, max_scrolls):
    last_h = 0
    still = 0
    for _ in range(max_scrolls):
        try:
            page.mouse.wheel(0, 2500)
        except Exception:
            pass
        page.wait_for_timeout(700)
        try:
            more = page.get_by_role("button", name=MORE_BUTTON)
            if more.count():
                more.first.click(timeout=2000)
                page.wait_for_timeout(1500)
        except Exception:
            pass
        try:
            # the page may be reloading itself (e.g. after a bot check) and have no body yet
            h = page.evaluate("(document.scrollingElement || document.documentElement || {}).scrollHeight || 0")
        except Exception:
            page.wait_for_timeout(1500)
            continue
        still = still + 1 if h == last_h else 0
        if still >= 3:
            break
        last_h = h
