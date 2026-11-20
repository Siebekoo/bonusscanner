"""Test a sample of product links per store (deals and the Goedkoopst price list)."""
import json, random, collections, requests
from pathlib import Path
random.seed(1)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
      "Accept-Language": "nl-NL,nl;q=0.9"}
def check(url):
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
        return {"url": url, "status": r.status_code, "final": r.url, "title": (r.text.split("<title>")[1].split("</title>")[0][:90] if "<title>" in r.text else "")}
    except Exception as e:
        return {"url": url, "status": "error", "final": "", "title": str(e)[:90]}
out = {"deals": {}, "prices": {}}
d = json.load(open("output/deals.json"))
by = collections.defaultdict(list)
for x in d["deals"]:
    by[x["store"]].append(x)
for store, xs in by.items():
    sample = random.sample(xs, min(6, len(xs)))
    out["deals"][store] = [dict(check(x["url"]), product=x["title"]) for x in sample]
data = json.load(open("cache/checkjebon.json"))
for s in data:
    ps = s.get("d") or []
    for p in random.sample(ps, min(3, len(ps))):
        out["prices"].setdefault(s["n"], []).append(dict(check(s.get("u", "") + p.get("l", "")), product=p["n"]))
Path("debug-output").mkdir(exist_ok=True)
Path("debug-output/links.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
Path("debug-output/deals_sample.json").write_text(json.dumps(d["deals"][:400], ensure_ascii=False, indent=1))
