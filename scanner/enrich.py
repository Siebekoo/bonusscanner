"""Make the raw deals more useful: clean out junk, add a category, price per kg/l,
which week the deal is for, and group the same product across stores."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from typing import Optional

from .models import Deal

# ---------------------------------------------------------------- cleanup

JUNK = re.compile(
    r"^(bekijk|meer info|lees meer|toon|ontdek|klik|bestel|ga naar|schrijf je in|download)|"
    r"nieuwsbrief|cadeaukaart|cadeaubon|gratis bezorg|bezorgkosten|folder|"
    r"^aanbiedingen?$|^acties?$|^bonus$|^alle aanbiedingen|cookie|inloggen|"
    r"^(deze|volgende) week$|^weekactie$|spaaractie|spaarkaart|winactie", re.I)


def is_junk(d: Deal) -> bool:
    t = d.title.strip()
    if len(t) < 3 or len(t) > 140 or JUNK.search(t):
        return True
    if sum(c.isalpha() for c in t) < 3:
        return True
    if d.price_now is None and not d.deal_text:
        return True
    if d.price_now is None and len(t.split()) == 1:
        return True          # e.g. Gall & Gall's "Chili" / "Frankrijk" wine tiles, "box" icons
    if d.price_now and d.price_now > 1500:
        return True
    return False


# ---------------------------------------------------------------- normalizing names

STORE_WORDS = {"ah", "albert", "heijn", "jumbo", "plus", "dirk", "aldi", "lidl", "hoogvliet",
               "etos", "kruidvat", "makro", "vomar", "deka", "dekamarkt", "coop", "spar",
               "action", "g'woon", "gwoon", "huismerk", "1", "de", "het", "een"}
STOP = {"alle", "of", "en", "diverse", "soorten", "varianten", "smaken", "per", "stuk", "stuks",
        "pak", "pakken", "fles", "flessen", "blik", "blikken", "zak", "doos", "voordeelverpakking",
        "voordeelpak", "multipack", "pack", "pak", "verpakking", "bijvoorbeeld", "bv", "nieuw", "x", "met", "van", "voor"}
SIZE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:x\s*\d+(?:[.,]\d+)?\s*)?"
                     r"(?:kg|kilo|gram|gr|g|ml|cl|liter|ltr|l|stuks|st|rollen|tabs|wasbeurten)\b", re.I)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(title: str) -> list[str]:
    t = strip_accents(title.lower())
    t = SIZE_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9'&+ ]+", " ", t)
    return [w for w in t.split() if w not in STOP and w not in STORE_WORDS and len(w) > 1]


def product_key(title: str) -> str:
    return " ".join(tokens(title))


# ---------------------------------------------------------------- categories
# First match wins, so more specific groups come first.

CATEGORIES = [
    ("Baby", r"luier|pampers|babydoek|zwitsal|flesvoeding|nutrilon|olvarit|fruithapje|babyshampoo|kruidvat baby"),
    ("Dieren", r"kattenvoer|hondenvoer|whiskas|felix|sheba|pedigree|gourmet|kattenbak|hondensnack|dierenvoer|kattensnack"),
    ("Drogisterij", r"shampoo|conditioner|douche|deodorant|\bdeo\b|tandpasta|tandenborstel|oral-?b|scheer|gillette|"
                    r"nivea|dove|andrelon|zonnebrand|bodylotion|make-?up|mascara|lipstick|parfum|eau de|"
                    r"maandverband|tampon|always|vitamine|paracetamol|ibuprofen|pleister|haarverf|gezichts|"
                    r"cr[eè]me(?! ?fra)|serum|lotion|wattenschijf|nagellak|sensodyne|elmex|colgate|axe\b|rexona|garnier|"
                    r"l'or[eé]al|head & shoulders|veet|wilkinson|scheermes|haargel|mondwater|zeep|handzeep"),
    ("Huishouden", r"wasmiddel|wasverzachter|robijn|ariel|persil|omo|dreft|vaatwas|finish|sun\b|afwasmiddel|"
                   r"toiletpapier|keukenpapier|keukenrol|tissue|zakdoek|allesreiniger|wc-?(eend|blok|reiniger)|"
                   r"glorix|ajax|vuilniszak|afvalzak|aluminiumfolie|vershoudfolie|batterij|duracell|"
                   r"schoonmaak|vlekverwijder|spons|kaars|lucifer|cillit|swiffer|febreze|air ?wick"),
    ("Koffie & thee", r"koffie|espresso|senseo|nespresso|dolce gusto|douwe egberts|nescaf|cappuccino|"
                      r"\bthee\b|pickwick|lipton|koffiebonen|koffiepads|capsules|cups\b"),
    ("Bier, wijn & sterk", r"\bbier\b|pils|heineken|amstel|grolsch|hertog jan|bavaria|jupiler|brand\b|"
                           r"leffe|affligem|la chouffe|radler|\bipa\b|wijn|\brose\b|ros[eé]\b|merlot|chardonnay|"
                           r"sauvignon|prosecco|\bcava\b|champagne|whisky|wodka|vodka|\brum\b|\bgin\b|jenever|likeur|"
                           r"bacardi|smirnoff|baileys|corona|desperados|hoegaarden|8\.6|palm\b|warsteiner"),
    ("Frisdrank & sap", r"coca|\bcola\b|pepsi|fanta|sprite|7up|seven up|frisdrank|ice ?tea|lipton ice|sinas|cassis|"
                        r"\bsap\b|jus d'orange|sinaasappelsap|appelsap|smoothie|limonade|siroop|ranja|"
                        r"red bull|monster|energy|spa\b|chaudfontaine|bar le duc|mineraalwater|water\b|"
                        r"rivella|fristi|chocomel|chocolademelk|dubbelfris|taksi|capri-?sun|appelsientje|roosvicee|optimel drink"),
    ("Vegetarisch", r"vega|vegetarisch|vegan|plantaardig|tofu|tempeh|beyond|vivera|valess|garden gourmet|"
                    r"vleesvervanger|falafel|linzen"),
    ("Vlees & vis", r"kip|kipfilet|kipdij|gehakt|rundvlees|varken|biefstuk|speklap|spek\b|hamburger|"
                    r"worst|rookworst|braadworst|shoarma|schnitzel|filet|ribs|spareribs|vlees|saucijs|"
                    r"slavink|kalkoen|\blam\b|zalm|vis\b|kabeljauw|tonijn|garnalen|mosselen|haring|"
                    r"kibbeling|lekkerbek|pangasius|tilapia|\bham\b|salami|cervelaat|fricandeau|rosbief|"
                    r"filet americain|kipsate|sate\b|saté"),
    ("Brood & bakkerij", r"brood|bolletje|bollen|croissant|stokbrood|pistolet|beschuit|crackers|knackebrod|"
                         r"krentenbol|afbakbrood|tijgerbrood|wrap|tortilla|pita|naan|taart|vlaai|gebak|"
                         r"muffin|donut|appelflap|tompouce|cake\b|ontbijtkoek"),
    ("Ontbijt & beleg", r"hagelslag|pindakaas|jam\b|hazelnootpasta|nutella|chocopasta|muesli|cornflakes|"
                        r"cruesli|havermout|granola|ontbijtgranen|kellogg|honing|smeerkaas|appelstroop|"
                        r"vruchtenhagel|de ruijter|calve|calvé|zoet beleg|ontbijt"),
    ("Snoep & koek", r"chocola|reep|milka|tony'?s|verkade|côte d'or|cote d'or|snickers|mars\b|twix|"
                     r"bounty|m&m|kitkat|kinder|snoep|drop|haribo|katja|winegum|lolly|mentos|stroopwafel|"
                     r"koek|koekjes|biscuit|liga|sultana|oreo|lu\b|bastogne|speculaas|pepernoot|"
                     r"kruidnoot|chocoladeletter|ijs\b|ijsjes|magnum|ben & jerry|hertog ijs|ola\b|cornetto|"
                     r"marsepein|banketstaaf"),
    ("Zuivel & eieren", r"melk|yoghurt|kwark|vla\b|vla's|toetje|pudding|room\b|slagroom|kookroom|boter|"
                        r"margarine|blue band|eieren|\bei\b|kaas|gouda|brie|mozzarella|feta|parmezaan|"
                        r"geitenkaas|roomkaas|philadelphia|alpro|optimel|danone|activia|campina|zuivel|"
                        r"creme fraiche|zure room|skyr|karnemelk|chocolademelk|milkshake|griekse"),
    ("Chips & noten", r"chips|lay'?s|doritos|pringles|croky|nibbits|borrelnoot|pinda's|cashew|noten|"
                      r"walnoot|amandel|popcorn|zoutje|tuc\b|mini toast|borrel|bitterbal|kroket|\bsnacks?\b"),
    ("Voorraadkast", r"pasta|spaghetti|macaroni|penne|fusilli|rijst|noedel|couscous|quinoa|saus|ketchup|"
                     r"mayonaise|mayo|mosterd|sambal|ketjap|soep|unox|bouillon|knorr|conimex|"
                     r"honig|olijfolie|olie\b|azijn|kruiden|peper|zout\b|suiker|meel|bakmix|"
                     r"conserven|bruine bonen|kidneybonen|witte bonen|tomatenblokjes|kikkererwten|pesto|tomatenpuree|passata|wereldkeuken|"
                     r"taco|mexicaans|italiaans|risotto|curry|tikka|wok|roerbak|jumbo pasta"),
    ("Groente & fruit", r"appel|peer|peren|banaan|bananen|sinaasappel|mandarijn|druiven|aardbei|bessen|"
                        r"framboz|meloen|mango|ananas|kiwi|citroen|limoen|avocado|tomaat|tomaten|"
                        r"komkommer|paprika|sla\b|ijsbergsla|spinazie|broccoli|bloemkool|wortel|"
                        r"winterpeen|waspeen|ui\b|uien|knoflook|champignon|courgette|aubergine|prei|"
                        r"boontjes|sperziebonen|aardappel|krieltjes|groente|fruit|salade|rucola|"
                        r"andijvie|zuurkool|rode kool|bietjes|\bmais\b|maïs|asperge|pompoen|kool\b|spruiten"),
    ("Diepvries", r"diepvries|pizza|friet|patat|frites|aviko|mccain|ovenschotel|loempia|nasi|bami|"
                  r"kant-en-klaar|maaltijd|lasagne|iglo|vissticks|spinazie a la creme|ijsblok"),
]
CAT_RE = [(name, re.compile(rx, re.I)) for name, rx in CATEGORIES]
STORE_DEFAULT_CAT = {"Etos": "Drogisterij", "Kruidvat": "Drogisterij", "Action": "Non-food",
                     "Gall & Gall": "Bier, wijn & sterk"}


def categorize(d: Deal) -> str:
    text = strip_accents(f"{d.title} {d.category}".lower())
    for name, rx in CAT_RE:
        if rx.search(text):
            return name
    return STORE_DEFAULT_CAT.get(d.store, "Overig")


# ---------------------------------------------------------------- price per kg / l

AMOUNT_RE = re.compile(
    r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|kilo|gram|gr|g|ml|cl|liter|ltr|l)\b", re.I)
PIECES_RE = re.compile(r"(\d+)\s*(?:stuks|st\.?|rollen|tabs|tabletten|capsules|pads|wasbeurten)\b", re.I)


def parse_amount(text: str) -> Optional[tuple[float, str]]:
    """'6 x 330 ml' -> (1.98, 'l'); '500 g' -> (0.5, 'kg'); '10 stuks' -> (10, 'st')."""
    m = AMOUNT_RE.search(text or "")
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        v = float(m.group(2).replace(",", "."))
        u = m.group(3).lower()
        if u in ("kg", "kilo"):
            return n * v, "kg"
        if u in ("gram", "gr", "g"):
            return n * v / 1000, "kg"
        if u == "ml":
            return n * v / 1000, "l"
        if u == "cl":
            return n * v / 100, "l"
        return n * v, "l"
    m = PIECES_RE.search(text or "")
    if m and int(m.group(1)) > 1:
        return float(m.group(1)), "st"
    return None


def unit_price(d: Deal) -> tuple[Optional[float], str]:
    amt = parse_amount(d.size) or parse_amount(d.title)
    pay = d.pay_per_item()
    if not amt or not pay or amt[0] <= 0:
        return None, ""
    qty, unit = amt
    val = pay / qty
    # sanity limits: ignore nonsense from mis-parsed sizes
    if unit in ("kg", "l") and not (0.05 <= val <= 400):
        return None, ""
    return round(val, 2), unit


# ---------------------------------------------------------------- week

def which_week(d: Deal, today: date) -> Optional[str]:
    """'deze', 'volgende', or None for deals that have already ended."""
    t = today.isoformat()
    if d.valid_until and len(d.valid_until) == 10 and d.valid_until < t:
        return None
    if d.valid_from and len(d.valid_from) == 10 and d.valid_from > t:
        return "volgende"
    return d.week or "deze"


# ---------------------------------------------------------------- same product at several stores

def _similar(a: set, b: set) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter >= 2 and inter / min(len(a), len(b)) >= 0.75 or (a == b and len(a) >= 1)


def group_products(deals: list[Deal]) -> None:
    """Give deals for (nearly) the same product at different stores a shared group id."""
    buckets: dict[str, list[int]] = defaultdict(list)
    toks = [set(d.key.split()) for d in deals]
    for i, d in enumerate(deals):
        for w in toks[i]:
            if len(w) >= 4:
                buckets[w].append(i)
    parent = list(range(len(deals)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for idx in buckets.values():
        if len(idx) > 400:          # very common word like "kaas": too broad to compare all
            continue
        for x in range(len(idx)):
            for y in range(x + 1, len(idx)):
                i, j = idx[x], idx[y]
                if deals[i].store != deals[j].store and deals[i].week == deals[j].week \
                        and _similar(toks[i], toks[j]):
                    parent[find(i)] = find(j)

    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(deals)):
        members[find(i)].append(i)
    n = 0
    for root, idx in members.items():
        if len({deals[i].store for i in idx}) >= 2:
            n += 1
            for i in idx:
                deals[i].group = f"g{n}"


# ---------------------------------------------------------------- all together

def enrich(deals: list[Deal], today: Optional[date] = None) -> list[Deal]:
    today = today or date.today()
    out, seen = [], set()
    for d in deals:
        if is_junk(d):
            continue
        week = which_week(d, today)
        if week is None:
            continue
        d.week = week
        d.key = product_key(d.title)
        if not d.key:
            continue
        dup = (d.store, d.key, d.pay_per_item(), d.week)
        if dup in seen:
            continue
        seen.add(dup)
        d.category = categorize(d)
        d.unit_price, d.unit = unit_price(d)
        out.append(d)
    group_products(out)
    return out
