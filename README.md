# Survivor data automation

Runs on GitHub's servers on a schedule. Nothing runs on your computer.

- Every run rebuilds the power rankings from all spreads through the current week (so they stay current), then logs lines. Tuesday 9:10 AM ET is the opening snapshot.
- Wed/Thu/Fri 6:10 PM, Sat 11:10 AM, Sun 11:40 AM ET: logs current spreads and moneylines for unplayed games next to our ratings.
- Rebuilds the dashboard page (docs/index.html) after each run; data is saved in data/.

All files sit at the top level of the repo on purpose (browser uploads flatten folders). The data and docs folders are created by the first run.

Method: ratings fit to prior weeks' closing spreads (recent weeks weighted more, halving every 4 weeks), pulled toward preseason win totals by about 3 games. On 639 games (2019, 2020, 2025) this beat static preseason ratings (Brier 0.2237 vs 0.2309) but not the game's own closing line (0.2124). Spread to win probability uses a standard deviation of 11.3.
