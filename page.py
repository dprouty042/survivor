"""Write docs/index.html (served by GitHub Pages) from the data files."""
import glob, os, shutil
import pandas as pd
import common

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1f21;--mute:#6b6f76;--line:#e3e0d8;--card:#fff;--up:#1f7a4d;--down:#b3372f}
@media (prefers-color-scheme:dark){:root{--bg:#141517;--fg:#ececec;--mute:#9aa0a6;--line:#2b2d31;--card:#1b1c1f;--up:#5cc394;--down:#ef7a70}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 2px}h2{font-size:17px;margin:28px 0 8px}
.mute{color:var(--mute);font-size:13px}.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:420px}th,td{padding:7px 10px;text-align:right;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}th{font-size:12px;color:var(--mute);font-weight:600;border-bottom:1px solid var(--line)}
tr+tr td{border-top:1px solid var(--line)}.up{color:var(--up)}.down{color:var(--down)}p{margin:6px 0}
"""


def pct(x):
    return f"{x * 100:.0f}%"


def signed(x, suffix=""):
    if round(x, 1) == 0:
        return "0" + suffix
    cls = "up" if x > 0 else "down"
    return f'<span class="{cls}">{x:+.1f}{suffix}</span>'


def week_table(snaps, week):
    s = snaps[snaps.week == week]
    if s.empty:
        return "<p class='mute'>No snapshots yet this week.</p>", ""
    rows = []
    for (a, h), grp in s.groupby(["away", "home"]):
        first, last = grp.iloc[0], grp.iloc[-1]
        home_fav = (last.market_wp_home if pd.notna(last.market_wp_home) else last.market_spread_wp_home) >= 0.5
        fav, dog = (h, a) if home_fav else (a, h)
        m = last.market_wp_home if home_fav else 1 - last.market_wp_home
        m0 = first.market_wp_home if home_fav else 1 - first.market_wp_home
        r = last.rating_wp_home if home_fav else 1 - last.rating_wp_home
        where = "vs" if home_fav else "@"
        rows.append((m, f"<tr><td><b>{fav}</b> {where} {dog}</td><td>{last.kickoff_et}</td>"
                        f"<td>{pct(m)}</td><td>{signed((m - m0) * 100, ' pts')}</td>"
                        f"<td>{pct(r)}</td><td>{signed((m - r) * 100, ' pts')}</td></tr>"))
    rows.sort(key=lambda x: -x[0])
    head = ("<tr><th>Favorite</th><th>Kickoff (ET)</th><th>Market</th>"
            "<th>Moved this week</th><th>Our rating</th><th>Market − rating</th></tr>")
    stamp = f"Latest snapshot: {s.taken_at_et.iloc[-1]} ET ({s.slot.iloc[-1]})"
    return f"<div class='wrap'><table>{head}{''.join(r for _, r in rows)}</table></div>", stamp


def build():
    ranks = pd.read_csv("data/power_rankings.csv")
    week = int(ranks.built_for_week.iloc[0])
    try:
        snaps = pd.read_csv("data/line_snapshots.csv")
    except FileNotFoundError:
        snaps = pd.DataFrame(columns=["week"])
    wk_html, stamp = week_table(snaps, week)
    rk = "".join(f"<tr><td>{r['rank']}</td><td><b>{r.team}</b></td><td>{r.rating:+.1f}</td>"
                 f"<td>{r.preseason:+.1f}</td><td>{signed(r.change)}</td></tr>" for _, r in ranks.iterrows())
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Survivor Dashboard — Week {week}</title>
<style>{CSS}</style></head><body><main>
<h1>Survivor Dashboard — Week {week}</h1>
<p class="mute">Page rebuilt {common.now_et().strftime('%a %b %d, %I:%M %p')} ET · updates automatically</p>

<h2>This week: market vs. our ratings</h2>
<p class="mute">{stamp}. <b>Market</b> = win probability from the moneyline with the bookmaker's margin removed.
<b>Moved this week</b> = change since the first snapshot this week. <b>Our rating</b> = what our power ratings
(built Tuesday, before this week's lines) expected. A big positive gap means the market likes that favorite
more than our ratings do — often injury news.</p>
{wk_html}

<h2>Power rankings</h2>
<p class="mute">Rebuilt Tuesday for week {week} from every closing spread in earlier weeks. Rating = points vs. an
average team; home rating − away rating + 1.55 = projected spread.</p>
<div class="wrap"><table><tr><th>#</th><th>Team</th><th>Rating</th><th>Preseason</th><th>Change</th></tr>{rk}</table></div>

<h2>Schedule (Eastern)</h2>
<p>Tue 9:10 AM rankings + opening snapshot · Wed 6:10 PM after first injury report · Thu 6:10 PM after Thursday report, before TNF ·
Fri 6:10 PM after final injury designations · Sat 11:10 AM before Circa's Saturday lock · Sun 11:40 AM after inactives, before DK's 1 PM lock.</p>
<p class="mute">GitHub's scheduler can run late, occasionally by 15+ minutes. Don't treat Sunday's snapshot as your final check.
Lines: nflverse (updates every 10–30 minutes). Raw data: <a href="data/line_snapshots.csv">line snapshots</a> · <a href="data/power_rankings_history.csv">rankings history</a>.</p>
</main></body></html>"""
    os.makedirs("docs", exist_ok=True)
    open("docs/index.html", "w").write(html)
    os.makedirs("docs/data", exist_ok=True)
    for f in glob.glob("data/*.csv"):
        shutil.copy(f, "docs/data/")
    print("Page written: docs/index.html")
