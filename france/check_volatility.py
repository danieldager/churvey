#!/usr/bin/env python3
"""What needs re-checking, and when.

Every answer key has a shelf life. This reports which rows are due, on a default
MONTHLY cadence, plus the dated triggers we already know about.

Run it monthly, and always before a capture batch.

  france/check_volatility.py [--asof YYYY-MM-DD] [--last-refresh YYYY-MM-DD]
"""
import argparse
from datetime import date, timedelta

from verified import MONTHLY_DAYS, VOLATILE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--last-refresh", default="2026-08-03",
                    help="when the answer keys were last rebuilt")
    args = ap.parse_args()
    today = date.fromisoformat(args.asof)
    last = date.fromisoformat(args.last_refresh)
    age = (today - last).days

    print(f"answer keys last rebuilt {last}  ({age} days ago)")
    print(f"default cadence: every {MONTHLY_DAYS} days\n")

    due, upcoming = [], []
    for v in VOLATILE:
        over = age >= v["refresh_days"]
        trig = v.get("check_after")
        trig_due = trig and today >= date.fromisoformat(trig)
        (due if (over or trig_due) else upcoming).append((v, over, trig_due))

    if age >= MONTHLY_DAYS:
        print(f"⚠ FULL REBUILD DUE - the whole corpus is {age} days old "
              f"(cadence {MONTHLY_DAYS}). Re-run fetch_sources.py + build.py.\n")

    for label, group in (("DUE NOW", due), ("NOT YET DUE", upcoming)):
        if not group:
            continue
        print(f"=== {label} ({len(group)}) ===")
        for v, over, trig_due in group:
            why = []
            if over:
                why.append(f"{age}d old")
            if trig_due:
                why.append(f"trigger {v['check_after']} has passed")
            elif v.get("check_after"):
                why.append(f"trigger {v['check_after']}")
            print(f"  [{v['kind']:16s}] {v['binding']:8s} {v['label']}"
                  f"   ({'; '.join(why)})")
            print(f"      {v['issue']}")
            if v.get("url"):
                print(f"      {v['url']}")
        print()

    print(f"{len(due)} of {len(VOLATILE)} registered items due.")


if __name__ == "__main__":
    main()
