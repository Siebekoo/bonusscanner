#!/usr/bin/env python3
"""Scan Dutch supermarkets and drugstores for this week's deals and put them in one place.

    python scan.py                    # all stores
    python scan.py --only ah,jumbo    # just some
    python scan.py --debug            # save raw data + screenshots to debug/
    python scan.py --show             # watch the browser do its thing

Output:  output/deals.json  and  output/deals.html (open in any browser)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from datetime import date, datetime
from pathlib import Path

from scanner.stores import STORES, run_store
from scanner.report import write_html
from scanner.enrich import enrich
from scanner import history, prices

ROOT = Path(__file__).parent


def now_nl() -> datetime:
    """Dutch time, also when running on GitHub's servers (which use UTC)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Amsterdam"))
    except Exception:
        return datetime.now()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--only", help="comma-separated: " + ",".join(STORES))
    ap.add_argument("--debug", action="store_true", help="save raw responses/screenshots")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--workers", type=int, default=4, help="stores scanned in parallel")
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--no-history", action="store_true", help="don't read or save price history")
    ap.add_argument("--no-prices", action="store_true",
                    help="skip the regular price list (the Goedkoopst tab)")
    ap.add_argument("--push", action="store_true",
                    help="upload results to GitHub (for stores that block GitHub's servers)")
    args = ap.parse_args()

    keys = [k.strip() for k in args.only.split(",")] if args.only else list(STORES)
    unknown = [k for k in keys if k not in STORES]
    if unknown:
        sys.exit(f"Unknown store(s): {', '.join(unknown)}. Choose from: {', '.join(STORES)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    debug_dir = ROOT / "debug" if args.debug else None
    opts = dict(headful=args.show, debug_dir=debug_dir)

    all_deals, status = [], {}
    print(f"Scanning {len(keys)} stores...\n")

    def job(k):
        t = time.time()
        deals = run_store(k, **opts)
        return k, deals, time.time() - t

    # Playwright's sync API wants its own thread per browser, which this gives us.
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(job, k): k for k in keys}
        for f in as_completed(futures):
            k = futures[f]
            name = STORES[k]["name"]
            try:
                _, deals, secs = f.result()
                all_deals += deals
                status[name] = {"ok": True, "count": len(deals)}
                flag = "OK " if deals else "?? "
                print(f"  {flag} {name:<13} {len(deals):>4} deals  ({secs:.0f}s)")
            except Exception as e:
                status[name] = {"ok": False, "count": 0, "error": str(e).splitlines()[0][:300]}
                print(f"  ERR {name:<13} {str(e).splitlines()[0][:110]}")
                if args.debug:
                    traceback.print_exc()

    today = now_nl().date()

    if args.push:
        push_results(all_deals, keys, today)

    # Stores that found nothing here (e.g. blocked on GitHub's servers): use recent
    # results uploaded from your own PC, if there are any.
    for k in keys:
        name = STORES[k]["name"]
        if not any(d.store == name for d in all_deals):
            extra = load_pushed(k, today)
            if extra:
                all_deals += extra
                status[name] = {"ok": True, "count": len(extra), "via": "pc"}
                print(f"  PC  {name:<13} {len(extra):>4} deals from your PC")

    all_deals = enrich(all_deals, today)
    counts = {STORES[k]["name"]: 0 for k in keys}
    for d in all_deals:
        counts[d.store] = counts.get(d.store, 0) + 1
    for name, st in status.items():
        st["count"] = counts.get(name, 0)

    # GitHub keeps the shared history in history/. Runs on your own PC use history-local/
    # (not uploaded), so the two never clash when you sync.
    on_github = bool(os.environ.get("GITHUB_ACTIONS"))
    hist_dir = ROOT / "history" if on_github else ROOT / "history-local"
    past = []
    if not args.no_history:
        by_date = {d["date"]: d for d in history.load(ROOT / "history-local", today)}
        by_date.update({d["date"]: d for d in history.load(ROOT / "history", today)})
        past = [by_date[k] for k in sorted(by_date)]
    history.annotate(all_deals, past, today)
    warnings = history.health(counts, past)
    if not args.no_history and all_deals and not args.push:
        history.save(hist_dir, today, all_deals, counts)

    # direct discounts first, then multi-buy deals (1+1 etc.)
    all_deals.sort(key=lambda d: (d.deal_type == "meer kopen", -(d.effective_pct or 0),
                                  d.store, d.title))
    payload = {
        "generated": now_nl().strftime("%Y-%m-%dT%H:%M"),
        "today": today.isoformat(),
        "history_days": len(past),
        "stores": status,
        "warnings": warnings,
        "deals": [dict(d.to_dict(), pay=d.pay_per_item()) for d in all_deals],
    }
    (out / "deals.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    write_html(payload, out / "deals.html")
    if not args.no_prices and not args.push:
        build_prices(all_deals, out)
    report_warnings(warnings, counts)

    print(f"\n{len(all_deals)} deals total")
    print(f"  -> {out / 'deals.html'}")
    print(f"  -> {out / 'deals.json'}")
    if not all_deals:
        # Exit with an error so the daily online run doesn't replace a good page with an empty one.
        sys.exit("No deals found at all: is the internet connection working?")
    empty = [n for n, s in status.items() if not s["count"]]
    if empty:
        print(f"\nNo deals from: {', '.join(empty)}. Run with --debug --only <store> to see why.")


def build_prices(deals, out):
    """Regular prices of everything + this week's deals, for the Goedkoopst tab."""
    data = prices.download(ROOT / "cache")
    if not data:
        return
    p = prices.build(data, deals)
    prices.write_js(p, out / "prices.js")
    with_deal = sum(1 for r in p["items"] if r[7])
    print(f"  Price list: {len(p['items'])} products, {with_deal} with a deal this week")


PUSH_DIR = ROOT / "pushed"
MAX_AGE_DAYS = 3


def push_results(deals, keys, today):
    """Save results per store in pushed/ and upload them to GitHub with git."""
    import subprocess
    PUSH_DIR.mkdir(exist_ok=True)
    saved = []
    for k in keys:
        name = STORES[k]["name"]
        rows = [d.to_dict() for d in deals if d.store == name]
        if rows:
            (PUSH_DIR / f"{k}.json").write_text(json.dumps(
                {"date": today.isoformat(), "store": name, "deals": rows}, ensure_ascii=False), "utf-8")
            saved.append(name)
    if not saved:
        print("\nNothing to upload.")
        return
    cmds = [["git", "add", "pushed"],
            ["git", "commit", "-m", f"Deals from PC {today}: {', '.join(saved)}"],
            ["git", "pull", "--rebase", "--autostash"],
            ["git", "push"]]
    for c in cmds:
        r = subprocess.run(c, cwd=ROOT, capture_output=True, text=True)
        if r.returncode and not (c[1] == "commit" and "nothing to commit" in r.stdout + r.stderr):
            print(f"\nUpload failed at '{' '.join(c)}':\n{(r.stderr or r.stdout).strip()[:400]}")
            return
    print(f"\nUploaded to GitHub: {', '.join(saved)}")


def load_pushed(key, today):
    from scanner.models import Deal
    from dataclasses import fields
    path = PUSH_DIR / f"{key}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text("utf-8"))
        age = (today - date.fromisoformat(data["date"])).days
    except (ValueError, KeyError, json.JSONDecodeError):
        return []
    if age > MAX_AGE_DAYS:
        return []
    names = {f.name for f in fields(Deal)} - {"key", "group", "tags", "unit_price", "unit"}
    return [Deal(**{k: v for k, v in row.items() if k in names}) for row in data["deals"]]


def report_warnings(warnings, counts):
    """Print warnings; on GitHub also show them on the run page."""
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ! {w}")
    if os.environ.get("GITHUB_ACTIONS"):
        for w in warnings:
            print(f"::warning::{w}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            lines = ["## Bonusscanner", "", "| Winkel | Aanbiedingen |", "|---|---:|"]
            lines += [f"| {n} | {c} |" for n, c in sorted(counts.items())]
            if warnings:
                lines += ["", "### Waarschuwingen"] + [f"- {w}" for w in warnings]
            with open(summary, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
