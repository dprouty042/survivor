"""Entry point for the scheduled job.

GitHub's scheduler only speaks UTC, so the workflow fires at both the
daylight-time and standard-time UTC equivalents of each slot. This script
checks the actual Eastern time and runs only if it's within the window of
a real slot, and only once per slot per week.

Usage:
  python scripts/run.py                  # scheduled run
  python scripts/run.py --force          # snapshot right now (manual button)
  python scripts/run.py --force --rebuild
  python scripts/run.py --now "2026-09-29 09:14"   # test slot detection
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import common
from common import ET, current_week, load_games
import page, rankings, snapshot

# (weekday Mon=0, hour, minute, name, rebuild rankings first)
SLOTS = [
    (1, 9, 10, "Tue open", True),
    (2, 18, 10, "Wed injury report", False),
    (3, 18, 10, "Thu pre-TNF", False),
    (4, 18, 10, "Fri final designations", False),
    (5, 11, 10, "Sat pre-Circa", False),
    (6, 11, 40, "Sun post-inactives", False),
]
EARLY, LATE = timedelta(minutes=10), timedelta(minutes=55)
DONE = "data/slots_done.txt"


def match_slot(now):
    for wd, h, m, name, rebuild in SLOTS:
        target = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=wd - now.weekday())
        if target - EARLY <= now <= target + LATE:
            return name, rebuild
    return None, False


def main():
    os.makedirs("data", exist_ok=True)  # flat repo layout: create output folders on first run
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--now")
    ap.add_argument("--games", default=common.GAMES_URL, help="local path for testing")
    a = ap.parse_args()

    now = datetime.fromisoformat(a.now).replace(tzinfo=ET) if a.now else common.now_et()
    if a.now:
        common.now_et = lambda: now
    name, rebuild = ("manual", a.rebuild) if a.force else match_slot(now)
    if name is None:
        print(f"{now:%a %H:%M} ET is not inside a slot window; nothing to do.")
        return

    games = load_games(a.games)
    week = current_week(games)
    key = f"{common.SEASON}-w{week}-{name}"
    done = open(DONE).read().split("\n") if os.path.exists(DONE) else []
    if not a.force and key in done:
        print(f"{key} already ran; skipping duplicate trigger.")
        return

    import pandas as pd
    stale = (not os.path.exists("data/power_rankings.csv") or
             int(pd.read_csv("data/power_rankings.csv").built_for_week.iloc[0]) != week)
    if rebuild or stale:
        rankings.rebuild(games)
    snapshot.take(games, name)
    page.build()
    if not a.force:
        with open(DONE, "a") as f:
            f.write(key + "\n")


if __name__ == "__main__":
    main()
