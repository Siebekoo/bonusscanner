"""Regular prices of (almost) everything, so the page can answer "where is X cheapest?".

The full assortments come from Checkjebon (https://www.checkjebon.nl, MIT license), which
publishes the regular prices of most Dutch supermarkets every day. This scanner's own
deals are laid on top: if a product is on sale this week, its deal price is used.

Output: output/prices.js, loaded by the page only when the "Goedkoopst" tab is opened.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .enrich import product_key, strip_accents
from .models import Deal, MULTI

SOURCE_URL = "https://raw.githubusercontent.com/supermarkt/checkjebon/main/data/supermarkets.json"
STORE_NAMES = {"ah": "Albert Heijn", "aldi": "Aldi", "dekamarkt": "DekaMarkt", "dirk": "Dirk",
               "ekoplaza": "Ekoplaza", "hoogvliet": "Hoogvliet", "jumbo": "Jumbo", "lidl": "Lidl",
               "plus": "PLUS", "poiesz": "Poiesz", "spar": "Spar", "vomar": "Vomar"}

# ---------------------------------------------------------------- download

def download(cache_dir: Path, max_age_hours: float = 20) -> Optional[list]:
    """Fresh copy of the price list, or a cached one (up to 3 days old) if download fails."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "checkjebon.json"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return json.loads(path.read_text("utf-8"))
    try:
        import requests
        r = requests.get(SOURCE_URL, timeout=60)
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        return data
    except Exception as e:
        print(f"  Could not download regular prices ({str(e).splitlines()[0][:80]})")
        if path.exists() and time.time() - path.stat().st_mtime < 3 * 86400:
            print("  Using the copy from the last run instead.")
            return json.loads(path.read_text("utf-8"))
    return None


# ---------------------------------------------------------------- sizes and units

# Product types whose sensible unit is not kg/liter. First match wins.
# (name, matches, excludes, unit label, regex for the count)
TYPES = [
    ("vochtig toiletpapier", r"vochtig\w* (toiletpapier|wc)|toiletpapier vochtig", r"houder",
     "doekje", r"(\d+)\s*-?\s*(?:st\b|st\.|stuks|doekjes)"),
    ("toiletpapier", r"toiletpapier|wc[- ]?papier|toiletrol", r"vochtig|houder|reiniger|blok|verfrisser|eend",
     "rol", r"(\d+)\s*-?\s*(?:rol|rollen|stuks|st\b|st\.)"),
    ("keukenpapier", r"keukenpapier|keukenrol", r"houder|vochtig",
     "rol", r"(\d+)\s*-?\s*(?:rol|rollen|stuks|st\b|st\.)"),
    ("vaatwastabletten", r"vaatwas\w*\s*(tabletten|tabs|capsules|caps)|all in one|all-in-1|(finish|sun)\b.*(tabs|caps|tabletten)",
     r"machinereiniger|zout|glansspoel|onderhoud", "tablet",
     r"(\d+)\s*-?\s*(?:tabs|tabletten|capsules|caps|stuks|st\b)"),
    ("wasmiddel", r"wasmiddel|wascapsules|was ?pods|wasparels|wasgel|(?<!vaat)wastabletten|discs\b",
     r"vlekverwijder|wasverzachter|wasnet|wasknijper|wasmand|waszak|vaatwas",
     "wasbeurt", r"(\d+)\s*-?\s*(?:wasbeurten|wasbeurt|scoops|capsules|caps|pods|discs|tabs|tabletten|stuks|st\b)"),
    ("luiers", r"luier|pampers|luierbroekjes|pants\b", r"tas|emmer|zak|crème|creme|doekjes",
     "luier", r"(\d+)\s*-?\s*(?:stuks|st\b|st\.|luiers|pants)"),
    ("eieren", r"\beieren\b|\bei\b|scharreleieren|vrije uitloop", r"pasen|chocola|snoep|salade|koek|noedel|mie|spread",
     "ei", r"(\d+)\s*-?\s*(?:stuks|st\b|st\.|eieren)"),
    ("koffiecups/pads", r"koffiepads|koffiecups|capsules|cups\b|pads\b",
     r"wattenschijf|make-?up|reinig|wascaps|vaatwas|cupcake|maandverband|inlegkruis|borstvoeding",
     "stuk", r"(\d+)\s*-?\s*(?:pads|cups|capsules|stuks|st\b)"),
]
TYPE_RE = [(n, re.compile(m, re.I), re.compile(x, re.I), u, re.compile(c, re.I)) for n, m, x, u, c in TYPES]
EQUIV = re.compile(r"(\d+)\s*=\s*(\d+)")   # "4=15": 4 long rolls worth 15 normal ones

AMOUNT = re.compile(
    r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*"
    r"(kilogram|kilo|kg|gram|gr|g|milliliter|millilitre|ml|centiliter|cl|liter|litre|ltr|l)(?![a-z])", re.I)
PIECES = re.compile(r"(\d+)\s*-?\s*(?:stuks|stuk|st\b|st\.|rollen|tabs|tabletten|pads|cups|zakjes)", re.I)


def parse_size(text: str) -> Optional[tuple[float, str]]:
    """Amount in kg, l or pieces: '6 x 330 ml' -> (1.98, 'l'), 'per 350 g' -> (0.35, 'kg')."""
    t = (text or "").lower().replace(",", ".")
    m = AMOUNT.search(t)
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        v = float(m.group(2)) * n
        u = m.group(3)
        if u in ("kilogram", "kilo", "kg"):
            return v, "kg"
        if u in ("gram", "gr", "g"):
            return v / 1000, "kg"
        if u in ("milliliter", "millilitre", "ml"):
            return v / 1000, "l"
        if u in ("centiliter", "cl"):
            return v / 100, "l"
        return v, "l"
    if re.search(r"per stuk|^stuk$|^1 stuk", t.strip()):
        return 1.0, "stuk"
    m = PIECES.search(t)
    if m and int(m.group(1)) > 0:
        return float(m.group(1)), "stuk"
    return None


def amount_for(name: str, size: str) -> Optional[tuple[float, str]]:
    """Best unit for this product: rolls for toilet paper, washes for detergent, else kg/l/piece."""
    text = strip_accents(f"{name} {size}".lower())
    for _type, match, exclude, unit, count in TYPE_RE:
        if match.search(text) and not exclude.search(text):
            eq = EQUIV.search(text)
            if eq and unit == "rol":
                return float(eq.group(2)), unit
            m = count.search(text)
            if m and 0 < int(m.group(1)) <= 500:
                return float(m.group(1)), unit
            break   # right type but count unknown: fall back to kg / l
    return parse_size(size) or parse_size(name)


# ---------------------------------------------------------------- attach this week's deals

def _numbers(name: str) -> set:
    """Numbers that tell variants apart (3-laags, maat 4), not the pack size."""
    t = strip_accents(name.lower())
    t = AMOUNT.sub(" ", t)
    t = EQUIV.sub(" ", t)
    t = re.sub(r"\d+\s*-?\s*(?:stuks|stuk|st\b|st\.|rollen|rol|tabs|tabletten|pads|cups|wasbeurten|"
               r"zakjes|x\b|pack|pak)", " ", t)
    return set(re.findall(r"\d+", t))


def _sim(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def attach_deals(items: list[dict], deals: list[Deal]) -> list[dict]:
    """Put each deal on the matching product in the same store. Deals that match nothing
    (or come from stores without a price list, like Etos) are added as their own items."""
    by_store: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        by_store[it["store"]].append(i)
    index: dict[tuple, list[int]] = defaultdict(list)
    toks = {}
    for i, it in enumerate(items):
        toks[i] = set(product_key(it["name"]).split())
        for w in toks[i]:
            if len(w) >= 4:
                index[(it["store"], w)].append(i)

    extra = []
    for d in deals:
        if d.week != "deze":
            continue
        dt = set(d.key.split())
        cands = set()
        for w in dt:
            if len(w) >= 4:
                cands.update(index.get((d.store, w), [])[:300])
        best, score = None, 0.0
        damt = amount_for(d.title, d.size)
        dnum = _numbers(d.title)
        for i in cands:
            s = _sim(dt, toks[i])
            if s < 0.6:
                continue
            inum = _numbers(items[i]["name"])
            if dnum and inum and dnum != inum:
                continue     # e.g. 3-laags vs 2-laags, maat 4 vs maat 5
            iamt = (items[i]["qty"], items[i]["unit"]) if items[i]["qty"] else None
            if damt and iamt and (damt[1] != iamt[1] or abs(damt[0] - iamt[0]) > 0.15 * iamt[0]):
                continue     # same name but another size
            if s > score:
                best, score = i, s
        pay = d.pay_per_item()
        if best is not None:
            it = items[best]
            if pay is None and it["price"] and d.effective_pct:
                pay = round(it["price"] * (1 - d.effective_pct / 100), 2)
            if pay and (not it["price"] or pay < it["price"] or d.deal_type == MULTI):
                it.update(deal=d.deal_text or "Aanbieding", pay=pay,
                          min_qty=d.min_qty if d.deal_type == MULTI else 1)
        elif pay:
            amt = damt
            extra.append({"store": d.store, "name": d.title, "price": d.price_was or (
                d.price_now if d.deal_type == MULTI else None), "size": d.size,
                "qty": amt[0] if amt else None, "unit": amt[1] if amt else "",
                "url": d.url, "deal": d.deal_text or "Aanbieding", "pay": pay,
                "min_qty": d.min_qty if d.deal_type == MULTI else 1})
    return items + extra


# ---------------------------------------------------------------- build

def build(data: list, deals: list[Deal]) -> dict:
    items = []
    for s in data:
        name = STORE_NAMES.get(s.get("n"), s.get("n", "?"))
        prefix = s.get("u", "")
        for p in s.get("d", []):
            price = p.get("p")
            if not isinstance(price, (int, float)) or not (0 < price < 2000) or not p.get("n"):
                continue
            amt = amount_for(p["n"], p.get("s", ""))
            items.append({"store": name, "name": p["n"], "price": round(float(price), 2),
                          "size": p.get("s", ""), "qty": amt[0] if amt else None,
                          "unit": amt[1] if amt else "", "url": p.get("l", ""), "prefix": prefix,
                          "deal": "", "pay": None, "min_qty": 1})
    items = attach_deals(items, deals)

    stores = sorted({it["store"] for it in items})
    prefixes = {}
    for it in items:
        if it.get("prefix"):
            prefixes[it["store"]] = it["prefix"]
    sidx = {s: i for i, s in enumerate(stores)}
    units = ["kg", "l", "stuk", "rol", "wasbeurt", "tablet", "luier", "ei", "doekje"]
    uidx = {u: i for i, u in enumerate(units)}
    rows = []
    for it in items:
        rows.append([sidx[it["store"]], it["name"], it["price"], it["size"],
                     round(it["qty"], 4) if it["qty"] else 0, uidx.get(it["unit"], -1),
                     it["url"], it["deal"], it["pay"], it["min_qty"]])
    regular_stores = sorted({STORE_NAMES.get(s.get("n"), s.get("n")) for s in data if s.get("d")})
    return {"stores": stores, "prefixes": [prefixes.get(s, "") for s in stores],
            "units": units, "regular": regular_stores,
            # url: full address, or the part after the store's prefix
            "fields": ["store", "name", "price", "size", "qty", "unit", "url", "deal", "pay", "min_qty"],
            "items": rows}


def write_js(prices: dict, path: Path) -> None:
    data = json.dumps(prices, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path.write_text("window.PRICES=" + data + ";", encoding="utf-8")
