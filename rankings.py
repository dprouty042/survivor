"""Rebuild power rankings. Ratings are fit to lines from weeks BEFORE the
current week - the exact setup that was backtested - so the midweek
tracker can compare this week's market against a rating that didn't see it."""
import os
import pandas as pd
import common
from common import current_week, market_ratings, preseason_ratings


def rebuild(games):
    week = current_week(games)
    prior = preseason_ratings()
    ratings = market_ratings(games, week, prior)
    df = pd.DataFrame({"team": list(ratings), "rating": list(ratings.values())})
    df["preseason"] = df.team.map(prior)
    df["change"] = df.rating - df.preseason
    df = df.sort_values("rating", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    df.insert(0, "built_for_week", week)
    df.insert(0, "built_at_et", common.now_et().strftime("%Y-%m-%d %H:%M"))
    df.round(3).to_csv("data/power_rankings.csv", index=False)

    hist = "data/power_rankings_history.csv"
    old = pd.read_csv(hist) if os.path.exists(hist) else pd.DataFrame()
    old = old[old.get("built_for_week", pd.Series(dtype=int)) != week] if len(old) else old
    pd.concat([old, df.round(3)]).to_csv(hist, index=False)
    print(f"Rankings rebuilt for week {week} from lines in weeks 1-{week - 1}")
    return df
