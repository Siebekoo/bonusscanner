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
from datetime import datetime
from pathlib import Path

from scanner.stores import STORES, run_store
from scanner.report import write_html

ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--only", help="comma-separated: " + ",".join(STORES))
    ap.add_argument("--debug", action="store_true", help="save raw responses/screenshots")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--workers", type=int, default=3, help="stores scanned in parallel")
    ap.add_argument("--out", default=str(ROOT / "output"))
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

    # direct discounts first, then multi-buy deals (1+1 etc.)
    all_deals.sort(key=lambda d: (d.deal_type == "meer kopen", -(d.effective_pct or 0),
                                  d.store, d.title))
    payload = {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "stores": status,
        "deals": [d.to_dict() for d in all_deals],
    }
    (out / "deals.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    write_html(payload, out / "deals.html")

    print(f"\n{len(all_deals)} deals total")
    print(f"  -> {out / 'deals.html'}")
    print(f"  -> {out / 'deals.json'}")
    if not all_deals:
        # Exit with an error so the daily online run doesn't replace a good page with an empty one.
        sys.exit("No deals found at all: is the internet connection working?")
    empty = [n for n, s in status.items() if not s["count"]]
    if empty:
        print(f"\nNo deals from: {', '.join(empty)}. Run with --debug --only <store> to see why.")


if __name__ == "__main__":
    main()
