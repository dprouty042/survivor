"""Shared helpers. Methods match what was backtested (see README)."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

SEASON = 2026
SIGMA = 11.3          # spread -> win prob, fit to 4,170 games (2010-2025)
HFA = 1.55            # home field, points
PTS_PER_WIN = 2.0     # preseason win total -> rating
HALF_LIFE_WEEKS = 4   # older lines count half as much every 4 weeks
PRIOR_GAMES = 3       # pull toward preseason rating, worth ~3 games of lines
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ET = ZoneInfo("America/New_York")

# nflverse codes -> the codes used everywhere else in this project
TO_OURS = {"ARI": "AZ", "LA": "LAR", "WAS": "WSH"}


def now_et():
    return datetime.now(ET)


def wp_from_spread(spread):
    return 0.5 * (1 + math.erf(spread / (SIGMA * math.sqrt(2))))


def implied_prob(american):
    return abs(american) / (abs(american) + 100) if american < 0 else 100 / (american + 100)


def devig_home(home_ml, away_ml):
    h, a = implied_prob(home_ml), implied_prob(away_ml)
    return h / (h + a)


def load_games(source=GAMES_URL):
    g = pd.read_csv(source, low_memory=False)
    g = g[(g.season == SEASON) & (g.game_type == "REG")].copy()
    g["home_team"] = g.home_team.replace(TO_OURS)
    g["away_team"] = g.away_team.replace(TO_OURS)
    g["kickoff_et"] = pd.to_datetime(g.gameday + " " + g.gametime).dt.tz_localize(ET)
    # Neutral-site games (London, Brazil, Australia...) get no home-field
    # points. Fixed Sept 30, 2026: before this, HFA was applied to every game.
    g["hfa"] = np.where(g.location == "Neutral", 0.0, HFA)
    return g


def current_week(games):
    """First week that still has an unplayed game."""
    return int(games[games.result.isna()].week.min())


def preseason_ratings(path="win_totals_2026.csv"):
    wt = pd.read_csv(path)
    avg = wt.win_total.mean()
    return {r.team: (r.win_total - avg) * PTS_PER_WIN for r in wt.itertuples()}


def market_ratings(games, before_week, prior):
    """Fit one rating per team to closing spreads from weeks < before_week.
    Recency-weighted least squares, shrunk toward the preseason rating."""
    d = games[(games.week < before_week) & games.spread_line.notna()]
    teams = sorted(prior)
    idx = {t: i for i, t in enumerate(teams)}
    rows, y, w = [], [], []
    for g in d.itertuples():
        r = np.zeros(len(teams)); r[idx[g.home_team]] = 1; r[idx[g.away_team]] = -1
        rows.append(r); y.append(g.spread_line - g.hfa)
        w.append(0.5 ** ((before_week - 1 - g.week) / HALF_LIFE_WEEKS))
    for t in teams:
        r = np.zeros(len(teams)); r[idx[t]] = 1
        rows.append(r); y.append(prior[t]); w.append(PRIOR_GAMES)
    X, y, sw = np.array(rows), np.array(y), np.sqrt(np.array(w))
    sol, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    sol = sol - sol.mean()
    return dict(zip(teams, sol))
