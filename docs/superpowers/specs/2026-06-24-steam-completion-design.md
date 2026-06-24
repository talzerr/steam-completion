# Steam Completion Challenge — Design Spec

**Date:** 2026-06-24  
**Repo:** git@github.com:talzerr/steam-completion.git  
**Goal:** Data-driven system to recommend which Steam games to complete next, optimising for a mix of quick wins and meaningful completions.

---

## Context

- 800 games owned, ~250 never touched
- 5k / 37k achievements unlocked (29% overall)
- 24 games fully completed
- Games are a means to an end — not chosen to enjoy, chosen to complete
- Target cadence: 4 small + 2 big options per recommendation batch (user picks from the pool)

---

## Repository Structure

```
steam-completion/
├── data/
│   ├── games.csv          # main dataset, full refresh on each fetch run
│   └── hltb_cache.json    # HowLongToBeat cache, append-only (slow to fetch)
├── fetch.py               # pulls Steam API + HLTB, writes data/
├── score.py               # reads data/, prints recommendations
├── config.py              # Steam API key, Steam ID, scoring weights, output counts
└── requirements.txt
```

`fetch.py` fully overwrites `games.csv` on each run. `hltb_cache.json` is only appended to — entries are never re-fetched unless manually deleted. `score.py` is read-only and never writes.

---

## Data Pipeline (`fetch.py`)

### Steam API calls (per game)

1. `IPlayerService/GetOwnedGames` — full library with playtime and last-played timestamp
2. `ISteamUserStats/GetPlayerAchievements` — user's unlocked achievements per game
3. `ISteamUserStats/GetSchemaForGame` — achievement names and descriptions (for keyword scan)
4. `ISteamUserStats/GetGlobalAchievementPercentagesForApp` — global unlock rates per achievement

### HLTB lookup

Uses `howlongtobeatpy`. Looked up by game name. Result cached in `hltb_cache.json` keyed by `app_id`. If no HLTB entry found, `hltb_found = false`, `hltb_completionist_hours = achievements_total * 0.167` (10 minutes per achievement as a rough proxy), and `completionist_ratio` defaults to `1.0` (neutral — no grind signal available).

### Derived fields computed during fetch

- `achievements_pct` = `achievements_unlocked / achievements_total`
- `avg_global_unlock_pct` = mean of all per-achievement global rates
- `rarity_floor` = minimum global unlock % across all achievements in the game
- `completionist_ratio` = `hltb_completionist_hours / hltb_main_hours`
- `has_multiplayer_achievement` = `true` if any achievement name or description matches a keyword list: `["co-op", "coop", "multiplayer", "versus", "pvp", "with a friend", "online", "competitive"]`

---

## Dataset Schema (`games.csv`)

| Column | Type | Source |
|---|---|---|
| `app_id` | int | Steam |
| `name` | str | Steam |
| `playtime_hours` | float | Steam |
| `last_played` | int (unix ts) | Steam |
| `achievements_total` | int | Steam |
| `achievements_unlocked` | int | Steam |
| `achievements_pct` | float | derived |
| `avg_global_unlock_pct` | float | Steam |
| `rarity_floor` | float | Steam |
| `has_multiplayer_achievement` | bool | derived |
| `hltb_main_hours` | float | HLTB |
| `hltb_completionist_hours` | float | HLTB |
| `completionist_ratio` | float | derived |
| `hltb_found` | bool | derived |

---

## Scoring Function (`score.py`)

### Hard filters (excluded before scoring)

- `achievements_total == 0` — no achievements, nothing to complete
- `achievements_pct == 1.0` — already fully completed

### Score components (0–100 scale, weighted sum)

| Component | Weight | Formula |
|---|---|---|
| `ease_score` | 35% | `1 / completionist_ratio`, normalised across library |
| `size_score` | 25% | `1 / hltb_completionist_hours`, normalised |
| `difficulty_score` | 25% | `rarity_floor / 100`, normalised (higher floor = more common = easier) |
| `freshness_score` | 15% | penalty for stale partial progress: full score if never played or recently played; reduced if `achievements_pct > 0` and `last_played` is old |

Normalisation: each component is min-max scaled across the filtered library before weighting.

### Penalties (applied after weighted sum)

| Condition | Penalty |
|---|---|
| `has_multiplayer_achievement == true` | −60 points |
| `achievements_pct > 0` and `last_played` > 730 days ago | −15 points (dropped game) |

The multiplayer penalty is heavy but not a hard exclusion, allowing manual override if desired.

### Output tiers and jitter

Games are split into two tiers by `hltb_completionist_hours` (median split across filtered library):

- **Small tier** (below median): weighted random sample of 4 from top-15 scorers
- **Big tier** (above median): weighted random sample of 2 from top-10 scorers

Sampling probability is proportional to score — higher-scored games appear more frequently across re-runs but are not guaranteed. Re-running `score.py` produces a fresh draw from the same pool.

All counts and pool sizes are configurable in `config.py`:

```python
SMALL_RETURN = 4
SMALL_POOL = 15
BIG_RETURN = 2
BIG_POOL = 10
STALENESS_THRESHOLD_YEARS = 2
SCORING_WEIGHTS = {
    "ease": 0.35,
    "size": 0.25,
    "difficulty": 0.25,
    "freshness": 0.15,
}
```

---

## Multiplayer Achievement Detection

Achievement names and descriptions for each game are scanned against a keyword list at fetch time. The keyword list is hardcoded but easily extended. False positives (e.g. a game with "online leaderboard" achievements that are actually solo) can be manually corrected by editing the CSV directly.

---

## Workflow

1. **First run:** `python fetch.py` — takes ~5–15 min depending on library size and HLTB rate limits. Writes `data/games.csv` and `data/hltb_cache.json`.
2. **Get recommendations:** `python score.py` — instant, prints tiered suggestions.
3. **Re-roll:** re-run `score.py` for a fresh jittered draw from the same data.
4. **Update library:** re-run `fetch.py` after completing games or acquiring new ones. HLTB cache means only new entries are fetched slowly.

---

## Out of Scope

- No web UI or interactive dashboard
- No automatic game-difficulty classification beyond the heuristics above
- No tracking of active play sessions or progress syncing
- Multiplayer detection is heuristic-only; no authoritative source consulted
