"""Write docs/grid.html: every team's win probability in every remaining game.

Each cell uses the best information available for that game:
  market  - a posted moneyline, vig removed (this week, sometimes next week)
  line    - a posted spread with no moneyline (converted with sigma 11.3)
  rating  - our current power ratings (home - away + home field, no home
            field at neutral sites), converted the same way
"""
import json
import os
import pandas as pd
import common
from common import current_week, devig_home, market_ratings, preseason_ratings, wp_from_spread

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grid_template.html")


def grid_data(games):
    week = current_week(games)
    ratings = market_ratings(games, week + 1, preseason_ratings())
    now = common.now_et()
    upcoming = games[(games.week >= week) & (games.kickoff_et > now)]
    cells = []
    for g in upcoming.itertuples():
        neutral = g.location == "Neutral"
        if pd.notna(g.home_moneyline) and pd.notna(g.away_moneyline):
            p_home, src = devig_home(g.home_moneyline, g.away_moneyline), "market"
            spread_home = g.spread_line if pd.notna(g.spread_line) else None
        elif pd.notna(g.spread_line):
            p_home, src, spread_home = wp_from_spread(g.spread_line), "line", g.spread_line
        else:
            spread_home = ratings[g.home_team] - ratings[g.away_team] + g.hfa
            p_home, src = wp_from_spread(spread_home), "rating"
        where = getattr(g, "stadium", "") if neutral else ""
        for team, opp, home, p in ((g.home_team, g.away_team, True, p_home),
                                   (g.away_team, g.home_team, False, 1 - p_home)):
            sp = None if spread_home is None else (-spread_home if home else spread_home)
            cells.append({"team": team, "week": int(g.week), "opp": opp, "home": home,
                          "neutral": bool(neutral), "site": where if isinstance(where, str) else "",
                          "p": round(float(p), 4), "spread": None if sp is None else round(float(sp), 1),
                          "src": src, "kick": g.kickoff_et.strftime("%a %m/%d %I:%M %p")})
    weeks = sorted({c["week"] for c in cells})
    return {"built": now.strftime("%a %b %d, %I:%M %p ET"), "week": week, "weeks": weeks,
            "teams": sorted(ratings), "ratings": {t: round(r, 2) for t, r in ratings.items()},
            "cells": cells}


def build(games, out="docs/grid.html"):
    data = grid_data(games)
    html = open(TEMPLATE).read().replace("/*__DATA__*/null", json.dumps(data))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(html)
    print(f"Grid written: {out} (weeks {data['weeks'][0]}-{data['weeks'][-1]})")
    return data
