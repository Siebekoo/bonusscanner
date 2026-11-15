"""Remember each day's deals so we can tell whether a deal is actually good, and notice
when a store suddenly returns far fewer deals than usual (its website probably changed).

One small gzipped file per day in history/, e.g. history/2026-11-15.json.gz (~30 KB).
Files older than a year are deleted.
"""
from __future__ import annotations

import gzip
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from .models import Deal

KEEP_DAYS = 400


def save(folder: Path, today: date, deals: list[Deal], counts: dict[str, int]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{today.isoformat()}.json.gz"
    rows = [[d.store, d.key, d.pay_per_item(), d.deal_text, d.week] for d in deals]
    counts = dict(counts)
    if path.exists():
        # a second run today (e.g. --only ah): keep the other stores from the earlier run
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                old = json.load(fh)
            rows += [r for r in old["deals"] if r[0] not in counts]
            counts = {**{k: v for k, v in old["counts"].items() if k not in counts}, **counts}
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    data = {"date": today.isoformat(), "counts": counts, "deals": rows}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    for old in folder.glob("*.json.gz"):
        try:
            if date.fromisoformat(old.name[:10]) < today - timedelta(days=KEEP_DAYS):
                old.unlink()
        except ValueError:
            pass


def load(folder: Path, today: date, days: int = 182) -> list[dict]:
    """Previous days, oldest first (today's file excluded)."""
    out = []
    if not folder.exists():
        return out
    for f in sorted(folder.glob("*.json.gz")):
        try:
            day = date.fromisoformat(f.name[:10])
        except ValueError:
            continue
        if today - timedelta(days=days) <= day < today:
            try:
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except (OSError, json.JSONDecodeError):
                continue
    return out


def _week(d: str) -> tuple[int, int]:
    return date.fromisoformat(d).isocalendar()[:2]


def annotate(deals: list[Deal], past: list[dict], today: date) -> None:
    """Add tags like 'Beste prijs in 12 weken', 'Vaak in de aanbieding', 'Nieuw'."""
    if not past:
        return
    first_day = date.fromisoformat(past[0]["date"])
    weeks_of_history = max(0, (today - first_day).days // 7)
    this_week = today.isocalendar()[:2]

    # (store, key) -> list of (date, price) seen in earlier weeks (not this week: same deal)
    seen: dict[tuple, list] = {}
    for day in past:
        if _week(day["date"]) == this_week:
            continue
        for store, key, price, _txt, week in day["deals"]:
            if week != "deze":
                continue
            seen.setdefault((store, key), []).append((day["date"], price))

    eight_weeks_ago = (today - timedelta(weeks=8)).isoformat()
    for d in deals:
        if d.week != "deze":
            continue
        hist = seen.get((d.store, d.key), [])
        price = d.pay_per_item()
        if not hist:
            if weeks_of_history >= 4:
                d.tags.append("Nieuw")
            continue
        weeks_on_sale = {_week(x) for x, _ in hist if x >= eight_weeks_ago}
        if len(weeks_on_sale) >= 4:
            d.tags.append("Vaak in de aanbieding")
        prices = [p for _, p in hist if p]
        if price and prices and price < min(prices) - 0.005 and weeks_of_history >= 2:
            d.tags.append(f"Beste prijs in {weeks_of_history} weken")
        elif price and prices and price > min(prices) + 0.005:
            d.tags.append(f"Was eerder {_eur(min(prices))}")


def _eur(v: float) -> str:
    return "€" + f"{v:.2f}".replace(".", ",")


def health(counts: dict[str, int], past: list[dict]) -> list[str]:
    """Warnings for stores that returned nothing, or far fewer deals than usual."""
    warnings = []
    recent = past[-7:]
    for store, n in sorted(counts.items()):
        usual = [day["counts"].get(store, 0) for day in recent if store in day.get("counts", {})]
        avg = mean(usual) if usual else 0
        if n == 0 and usual and avg < 1:
            continue                      # always empty (e.g. Makro): nothing new to report
        if n == 0:
            hint = f" (normaal ~{round(avg)})" if avg >= 1 else ""
            warnings.append(f"{store}: vandaag 0 aanbiedingen{hint}")
        elif avg >= 10 and n < 0.4 * avg:
            warnings.append(f"{store}: vandaag maar {n} aanbiedingen (normaal ~{round(avg)})")
    return warnings
