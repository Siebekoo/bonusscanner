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
from scanner import history

ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--only", help="comma-separated: " + ",".join(STORES))
    ap.add_argument("--debug", action="store_true", help="save raw responses/screenshots")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--workers", type=int, default=4, help="stores scanned in parallel")
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--no-history", action="store_true", help="don't read or save price history")
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

    today = date.today()
    all_deals = enrich(all_deals, today)
    counts = {STORES[k]["name"]: 0 for k in keys}
    for d in all_deals:
        counts[d.store] = counts.get(d.store, 0) + 1
    for name, st in status.items():
        st["count"] = counts.get(name, 0)

    hist_dir = ROOT / "history"
    past = [] if args.no_history else history.load(hist_dir, today)
    history.annotate(all_deals, past, today)
    warnings = history.health(counts, past)
    if not args.no_history and all_deals:
        history.save(hist_dir, today, all_deals, counts)

    # direct discounts first, then multi-buy deals (1+1 etc.)
    all_deals.sort(key=lambda d: (d.deal_type == "meer kopen", -(d.effective_pct or 0),
                                  d.store, d.title))
    payload = {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "history_days": len(past),
        "stores": status,
        "warnings": warnings,
        "deals": [dict(d.to_dict(), pay=d.pay_per_item()) for d in all_deals],
    }
    (out / "deals.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    write_html(payload, out / "deals.html")
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
