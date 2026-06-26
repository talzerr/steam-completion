# Steam Completion Recommender

A personal CLI tool that recommends which Steam games to complete (100% achievements) next.

## Goal

You have 793 games. The tool narrows them down to a shortlist of 5–7 worth actually finishing, combining a scoring algorithm with Claude AI judgment.

## Flow

```
python fetch.py      → data/games.csv + data/hltb_cache.json
python recommend.py  → Claude-ranked shortlist of 5–7 games
```

`fetch.py` takes ~1.5 hours on first run. Subsequent runs resume from `data/progress.json` (auto-deleted on completion), so sleep/interrupt is safe.

## fetch.py

Pulls data for every game in your Steam library and writes `data/games.csv`.

Per game it fetches:
- **Steam API** — playtime, last played timestamp, achievements (your unlocks + global unlock rates)
- **Multiplayer detection** — scans achievement names/descriptions for keywords (co-op, pvp, online, etc.)
- **HowLongToBeat** — main story hours and completionist hours, cached in `data/hltb_cache.json`

If HLTB has no data for a game, it estimates hours from achievement count (`achievements_total × 0.167`).

## score.py (used internally by recommend.py)

Filters out games with no achievements or already 100%'d. Scores remaining games on four components, each min-max normalised to [0, 1]:

| Component | Weight | Signal |
|---|---|---|
| Ease | 35% | 1 / completionist_ratio (prefers games close to main-story length) |
| Size | 25% | 1 / hltb_completionist_hours (prefers shorter games) |
| Difficulty | 25% | rarity_floor / 100 (prefers games where even rare achievements are common) |
| Freshness | 15% | recency of last play session |

**Freshness formula:**
- `achievements_pct == 0` (never started) → 1.0
- played within 6 months → 1.0
- played 6 months–2 years ago → linear decay to 0.0
- not played in 2+ years → 0.0

**Penalties applied after scoring:**
- `-60` if any achievement has multiplayer keyword in name/description
- `-15` if started (`achievements_pct > 0`) but not played in 2+ years (dropped game)

## recommend.py

Takes the top 30 candidates by score, formats them with stats (comp hours, ach%, playtime, started), and sends them to Claude Opus with a prompt asking for a 5–7 game shortlist with one-line reasons per game.

Claude considers: known buggy/unobtainable achievements, game quality, online achievement viability, player momentum (already started), and variety across the shortlist.

## Configuration

Credentials in `.env` (never committed):
```
STEAM_API_KEY=...   # from https://steamcommunity.com/dev/apikey
STEAM_ID=...        # 17-digit numeric ID
ANTHROPIC_API_KEY=... # from console.anthropic.com
```

## Data files

| File | Purpose |
|---|---|
| `data/games.csv` | Full scored dataset, one row per game |
| `data/hltb_cache.json` | HLTB lookup cache (keyed by app_id) — saves re-fetching |
| `data/progress.json` | Temporary resume checkpoint — deleted after successful run |

## Re-running

- **Refresh game data:** delete `data/games.csv` and `data/progress.json`, re-run `fetch.py`
- **Keep HLTB cache:** always preserve `data/hltb_cache.json` — it took ~1.5h to build
- **Just get new recommendations:** re-run `recommend.py` directly (no re-fetch needed)
