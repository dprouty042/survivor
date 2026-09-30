"""Pool-specific inputs for the grid page: your entries, your pool's projected
pick %, and this week's expected value per pick.

Files (top level of the repo, uploaded by hand when they change):
  entries.csv     entry_id, week, team, result   (result: won / lost / pending)
  circa_week.csv  week, team, circa_pct          (Saturday's Circa breakdown, 0-100)

Fetched automatically:
  SurvivorGrid consensus page -> "Projected" pick % (saved to data/sg_week{N}.csv)

Projected DK pick % = 65% Circa + 35% SurvivorGrid Projected, the blend that
has tracked our DK pool best (average miss 0.67 pts over weeks 1-3). If only
one source is available for the week, that source is used alone and labeled.
"""
import os
import re
import urllib.request
from html.parser import HTMLParser

import numpy as np
import pandas as pd

SG_URL = "https://www.survivorgrid.com/picks/"
SG_FIX = {"ARI": "AZ", "WAS": "WSH", "LA": "LAR", "JAC": "JAX"}


# ---------------------------------------------------------------- entries
def load_entries(path="entries.csv"):
    """Returns (alive_ids, used) where used = {entry_id: {team: week}}."""
    if not os.path.exists(path):
        return None, None
    e = pd.read_csv(path, dtype={"entry_id": str})
    e["result"] = e["result"].fillna("pending").str.lower()
    lost = set(e.loc[e.result == "lost", "entry_id"])
    alive = [i for i in dict.fromkeys(e.entry_id) if i not in lost]  # file order
    used = {i: {} for i in alive}
    for r in e[e.entry_id.isin(alive)].itertuples():
        used[r.entry_id][r.team] = int(r.week)
    return alive, used


# ---------------------------------------------------------------- SurvivorGrid
class _Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._in = "", True

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in:
            self._row.append(self._cell.strip()); self._in = False
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in:
            self._cell += data


def parse_sg(html):
    """Team -> SurvivorGrid 'Projected' pick %. Finds the column by its header."""
    t = _Table(); t.feed(html)
    header = next((r for r in t.rows if any(h.lower().startswith("proj") for h in r)), None)
    if header is None:
        return {}
    col = next(i for i, h in enumerate(header) if h.lower().startswith("proj"))
    out = {}
    for r in t.rows:
        if len(r) <= col or not re.fullmatch(r"[A-Z]{2,3}", r[0].split()[0] if r[0] else ""):
            continue
        m = re.search(r"-?\d+(\.\d+)?", r[col])
        if m:
            team = r[0].split()[0]
            out[SG_FIX.get(team, team)] = float(m.group())
    return out


def survivorgrid(week):
    """Fetch this week's projection; fall back to the last saved copy."""
    path = f"data/sg_week{week}.csv"
    try:
        req = urllib.request.Request(SG_URL, headers={"User-Agent": "Mozilla/5.0 survivor-dashboard"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        shown = re.search(r"(\d{4})\s+Week\s+(\d+)\s+Consensus", html)
        proj = parse_sg(html)
        if proj and (shown is None or int(shown.group(2)) == week):
            pd.DataFrame({"team": list(proj), "sg_projected_pct": list(proj.values())}).to_csv(path, index=False)
            return proj
        print("SurvivorGrid: page parsed but no usable table for this week")
    except Exception as ex:  # network or layout change: keep going without it
        print(f"SurvivorGrid fetch failed ({ex.__class__.__name__}); using saved copy if any")
    if os.path.exists(path):
        d = pd.read_csv(path)
        return dict(zip(d.team, d.sg_projected_pct))
    return {}


def circa(week, path="circa_week.csv"):
    if not os.path.exists(path):
        return {}
    d = pd.read_csv(path)
    d = d[d.week == week]
    return dict(zip(d.team, d.circa_pct))


def projected_pick_pct(week, teams):
    c, s = circa(week), survivorgrid(week)
    if c and s:
        src = "65% Circa + 35% SurvivorGrid"
    elif c:
        src = "Circa only; SurvivorGrid unavailable"
    elif s:
        src = "SurvivorGrid only until this week's Circa numbers are uploaded"
    else:
        return {}, "not available yet"
    out = {}
    for t in teams:
        cv, sv = c.get(t), s.get(t)
        if cv is None and sv is None:
            out[t] = 0.0
        else:
            cv = sv if cv is None else cv
            sv = cv if sv is None else sv
            out[t] = 0.65 * cv + 0.35 * sv if (c and s) else (cv if c else sv)
    tot = sum(out.values())
    if tot > 0:
        out = {t: v * 100 / tot for t, v in out.items()}  # share of entries making a pick
    return out, src


# ---------------------------------------------------------------- expected value
def pick_ev(games_this_week, win_prob, pick_pct, sims=40000, seed=7):
    """SurvivorGrid-style EV for one week in YOUR pool: the value of an entry
    after the week if you pick team T, relative to 1.0 before the week.
    EV(T) = E[ 1{T wins} / (share of the pool that survives) ].
    Game outcomes are simulated jointly (one winner per game), so teams in the
    same game can't both win. Ignores future weeks entirely."""
    rng = np.random.default_rng(seed)
    games = [(h, a) for h, a in games_this_week]
    teams = [t for g in games for t in g]
    idx = {t: i for i, t in enumerate(teams)}
    share = np.array([pick_pct.get(t, 0.0) / 100 for t in teams])
    wins = np.zeros((sims, len(teams)), dtype=bool)
    for h, a in games:
        hw = rng.random(sims) < win_prob[h]
        wins[:, idx[h]] = hw
        wins[:, idx[a]] = ~hw
    surv = np.clip((wins * share).sum(axis=1), 1e-6, None)
    return {t: float((wins[:, idx[t]] / surv).mean()) for t in teams}
