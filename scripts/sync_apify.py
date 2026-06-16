#!/usr/bin/env python
"""Command-line driver for Elbitat rate shopping.

Designed to be triggered by cron (GitHub Actions / any external scheduler). It is the
no-UI counterpart to the Streamlit "Run price check" button.

Usage
-----
  python scripts/sync_apify.py seed [--file config/competitors.yaml]
  python scripts/sync_apify.py scrape [--days 90] [--nights 1,2] [--adults 2] [--children 0]
  python scripts/sync_apify.py sync-pending          # poll any still-running runs

The daily scheduled scrape:
  python scripts/sync_apify.py scrape --days 90 --nights 1,2 --adults 2

Cost safeguards (horizon cap, competitor cap, duplicate-run suppression) are enforced
inside rate_shopping_service, so this script stays thin.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services import rate_shopping_service as rss  # noqa: E402


def cmd_seed(args: argparse.Namespace) -> int:
    import yaml

    path = Path(args.file)
    if not path.exists():
        print(f"Seed file not found: {path}")
        return 1
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("hotels", [])
    inserted = rss.seed_competitor_hotels(rows)
    print(f"Seeded {inserted} new hotel(s) from {path} ({len(rows)} in file).")
    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    nights_list = [int(n) for n in str(args.nights).split(",") if n.strip()]
    horizon = min(int(args.days), rss.MAX_HORIZON_DAYS)
    start = date.today() + timedelta(days=int(args.lead))

    # 1) Start phase — fire one Apify run per (check-in date, nights). Dedup auto-skips.
    pending: list[int] = []
    started, skipped, errors = 0, 0, 0
    for offset in range(horizon):
        ci = start + timedelta(days=offset)
        for nights in nights_list:
            try:
                res = rss.start_scrape_run(
                    check_in=ci, nights=nights, adults=int(args.adults), children=int(args.children)
                )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"  ! start failed {ci} x{nights}: {exc}")
                continue
            if res.get("skipped"):
                skipped += 1
            elif res.get("db_run_id"):
                pending.append(res["db_run_id"])
                started += 1
    print(f"Started {started} run(s), skipped {skipped} (recent duplicates), {errors} start error(s).")

    # 2) Poll phase — sync running runs until done or the overall deadline.
    deadline = time.monotonic() + int(args.timeout)
    remaining = set(pending)
    total_items, total_cost = 0, 0.0
    while remaining and time.monotonic() < deadline:
        for run_id in list(remaining):
            try:
                out = rss.sync_scrape_run(run_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! sync error run {run_id}: {exc}")
                remaining.discard(run_id)
                continue
            if out["status"] != "running":
                remaining.discard(run_id)
                total_items += int(out.get("item_count") or 0)
                total_cost += float(out.get("cost_usd") or 0.0)
        if remaining:
            time.sleep(10)

    print(
        f"Synced {len(pending) - len(remaining)}/{len(pending)} run(s). "
        f"Observations upserted: {total_items}. Approx Apify cost: ${total_cost:.4f}."
    )
    if remaining:
        print(f"{len(remaining)} run(s) still running at deadline — rerun 'sync-pending' later.")
    return 0


def cmd_sync_pending(args: argparse.Namespace) -> int:
    runs = [r for r in rss.list_recent_runs(limit=200) if r["status"] in ("running", "pending")]
    if not runs:
        print("No pending runs.")
        return 0
    done = 0
    for r in runs:
        try:
            out = rss.sync_scrape_run(r["id"])
            print(f"  run {r['id']}: {out['status']}")
            if out["status"] != "running":
                done += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ! run {r['id']}: {exc}")
    print(f"Finished {done}/{len(runs)} pending run(s).")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Write a CSV + plain-text summary of current insights (for emailing)."""
    import csv as _csv

    start = date.today()
    end = start + timedelta(days=int(args.days))
    nights = None if str(args.nights).lower() == "all" else int(args.nights)
    rows = rss.get_insights(start_date=start, end_date=end, nights=nights)

    price_fields = ["elbitat_price", "competitor_min", "competitor_median", "competitor_max"]
    for r in rows:
        n = r.get("nights") or 1
        if args.per_night:
            for pf in price_fields:
                if r.get(pf) is not None:
                    try:
                        r[pf] = round(float(r[pf]) / n, 2)
                    except (TypeError, ValueError):
                        pass

    cols = [
        "check_in", "nights", "elbitat_price", "competitor_min", "competitor_median",
        "competitor_max", "competitor_available_count", "elbitat_position",
        "median_trend_pct", "recommendation",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    above = sum(1 for r in rows if r.get("elbitat_position") == "above")
    flagged = [r for r in rows if str(r.get("recommendation", "")).startswith(("🔴", "🟠", "⚠️"))]
    basis = "per night" if args.per_night else "total stay"
    lines = [
        f"Elbitat rate-shopping report ({basis})",
        f"Window: {start} to {end}  (nights={args.nights})",
        f"Dates analysed: {len(rows)}",
        f"Dates priced ABOVE competitor median: {above}",
        f"Dates needing attention: {len(flagged)}",
        "",
    ]
    if flagged:
        lines.append("Flags:")
        for r in flagged[:30]:
            lines.append(
                f"  {r['check_in']} (x{r.get('nights')}): "
                f"Elbitat {r.get('elbitat_price')} vs median {r.get('competitor_median')} "
                f"-> {r.get('recommendation')}"
            )
    else:
        lines.append("No dates flagged for attention.")
    summary = "\n".join(lines)
    with open(args.summary_out, "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(summary)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Elbitat rate-shopping CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Seed competitor hotels from a YAML file")
    p_seed.add_argument("--file", default="config/competitors.yaml")
    p_seed.set_defaults(func=cmd_seed)

    p_scrape = sub.add_parser("scrape", help="Scrape the next N days of competitor prices")
    p_scrape.add_argument("--days", default=90, help="Horizon in days (capped by RATESHOP_MAX_HORIZON_DAYS)")
    p_scrape.add_argument("--lead", default=0, help="Days from today to start the horizon")
    p_scrape.add_argument("--nights", default="1,2", help="Comma-separated stay lengths, e.g. 1,2")
    p_scrape.add_argument("--adults", default=2)
    p_scrape.add_argument("--children", default=0)
    p_scrape.add_argument("--timeout", default=1500, help="Max seconds to wait in the poll phase")
    p_scrape.set_defaults(func=cmd_scrape)

    p_sync = sub.add_parser("sync-pending", help="Poll and sync any still-running runs")
    p_sync.set_defaults(func=cmd_sync_pending)

    p_report = sub.add_parser("report", help="Write a CSV + text summary of current insights")
    p_report.add_argument("--days", default=90)
    p_report.add_argument("--nights", default="2")
    p_report.add_argument("--per-night", dest="per_night", action="store_true")
    p_report.add_argument("--out", default="report.csv")
    p_report.add_argument("--summary-out", dest="summary_out", default="report.txt")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
