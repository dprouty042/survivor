"""Append one row per not-yet-started game in the current week:
the market's view (devigged moneyline, and spread) next to our rating's view."""
import os
import pandas as pd
import common
from common import current_week, devig_home, wp_from_spread


def take(games, slot):
    week = current_week(games)
    now = common.now_et()
    ranks = pd.read_csv("data/power_rankings.csv")
    if int(ranks.built_for_week.iloc[0]) != week:
        print(f"WARNING: rankings are for week {ranks.built_for_week.iloc[0]}, not {week}")
    rating = dict(zip(ranks.team, ranks.rating_pre))  # before this week's lines

    upcoming = games[(games.week == week) & (games.kickoff_et > now)]
    rows = []
    for g in upcoming.itertuples():
        has_ml = pd.notna(g.home_moneyline) and pd.notna(g.away_moneyline)
        mkt = devig_home(g.home_moneyline, g.away_moneyline) if has_ml else None
        rs = rating[g.home_team] - rating[g.away_team] + g.hfa
        rows.append({
            "taken_at_et": now.strftime("%Y-%m-%d %H:%M"), "slot": slot, "week": week,
            "kickoff_et": g.kickoff_et.strftime("%a %m/%d %I:%M %p"),
            "away": g.away_team, "home": g.home_team,
            "spread_home": g.spread_line, "home_ml": g.home_moneyline, "away_ml": g.away_moneyline,
            "market_wp_home": round(mkt, 4) if mkt is not None else None,
            "market_spread_wp_home": round(wp_from_spread(g.spread_line), 4) if pd.notna(g.spread_line) else None,
            "rating_spread_home": round(rs, 2),
            "rating_wp_home": round(wp_from_spread(rs), 4),
        })
    new = pd.DataFrame(rows)
    path = "data/line_snapshots.csv"
    old = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    pd.concat([old, new]).to_csv(path, index=False)
    print(f"Snapshot '{slot}': {len(new)} week-{week} games logged")
    return new
