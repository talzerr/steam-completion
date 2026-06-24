# Steam Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-script CLI system that fetches Steam + HLTB data and recommends which games to complete next, scored by ease, size, difficulty, and freshness.

**Architecture:** `fetch.py` hits Steam and HLTB APIs, computes derived fields, and writes a CSV + JSON cache. `score.py` reads that CSV, applies a weighted scoring formula with penalties, splits games into small/big tiers, and prints two `rich` tables. `config.py` holds all tuneable constants.

**Tech Stack:** Python 3.10+, pandas, requests, howlongtobeatpy, tqdm, rich, pytest

## Global Constraints

- Python 3.10+ (uses `dict | None` union type hint syntax)
- All tuneable constants live in `config.py` — never hardcode them in `fetch.py` or `score.py`
- `score.py` is read-only: it never writes any file
- `hltb_cache.json` is append-only: entries are never overwritten once written
- `games.csv` is fully overwritten on every `fetch.py` run
- Steam API key and Steam ID are set directly in `config.py` (no env vars, no .env file)

---

### Task 1: Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `config.STEAM_API_KEY`, `config.STEAM_ID`, `config.SCORING_WEIGHTS`, `config.MULTIPLAYER_KEYWORDS`, `config.SMALL_RETURN`, `config.SMALL_POOL`, `config.BIG_RETURN`, `config.BIG_POOL`, `config.STALENESS_THRESHOLD_YEARS`, `config.FRESHNESS_RECENT_MONTHS`

- [ ] **Step 1: Create `requirements.txt`**

```
requests
howlongtobeatpy
pandas
tqdm
rich
pytest
```

- [ ] **Step 2: Create `config.py`**

```python
STEAM_API_KEY = "your_api_key_here"
STEAM_ID = "your_steam_id_here"

SMALL_RETURN = 4
SMALL_POOL = 15
BIG_RETURN = 2
BIG_POOL = 10
STALENESS_THRESHOLD_YEARS = 2
FRESHNESS_RECENT_MONTHS = 6

SCORING_WEIGHTS = {
    "ease": 0.35,
    "size": 0.25,
    "difficulty": 0.25,
    "freshness": 0.15,
}

MULTIPLAYER_KEYWORDS = [
    "co-op", "coop", "multiplayer", "versus", "pvp",
    "with a friend", "online", "competitive",
]
```

- [ ] **Step 3: Fill in your Steam API key and Steam ID in `config.py`**

Get your API key at https://steamcommunity.com/dev/apikey. Your Steam ID is the 17-digit number in your Steam profile URL (e.g. `76561198012345678`).

- [ ] **Step 4: Create the data directory and test package**

```bash
mkdir -p data tests
touch data/.gitkeep tests/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Verify: `python -c "import pandas, requests, rich, tqdm; print('ok')"` should print `ok`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.py data/.gitkeep tests/__init__.py
git commit -m "chore: bootstrap project dependencies and config"
```

---

### Task 2: Scoring engine

**Files:**
- Create: `score.py`
- Create: `tests/test_score.py`

**Interfaces:**
- Consumes: `config.SCORING_WEIGHTS`, `config.STALENESS_THRESHOLD_YEARS`, `config.FRESHNESS_RECENT_MONTHS`, `config.SMALL_RETURN`, `config.SMALL_POOL`, `config.BIG_RETURN`, `config.BIG_POOL`
- Produces:
  - `filter_games(df: pd.DataFrame) -> pd.DataFrame`
  - `freshness_raw(achievements_pct: float, last_played_ts: int, now: datetime) -> float`
  - `compute_scores(df: pd.DataFrame, now: datetime = None) -> pd.DataFrame` — adds `score` column, drops intermediate columns
  - `select_games(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]` — returns `(small, big)`
  - `print_recommendations(small: pd.DataFrame, big: pd.DataFrame) -> None`
  - `main() -> None`

- [ ] **Step 1: Write failing tests for `filter_games`**

Create `tests/test_score.py`:

```python
import pandas as pd
import pytest
from datetime import datetime, timedelta


def make_df(**kwargs):
    defaults = {
        "app_id": [1],
        "name": ["Test Game"],
        "playtime_hours": [1.0],
        "last_played": [int(datetime(2024, 1, 1).timestamp())],
        "achievements_total": [10],
        "achievements_unlocked": [5],
        "achievements_pct": [0.5],
        "avg_global_unlock_pct": [50.0],
        "rarity_floor": [10.0],
        "has_multiplayer_achievement": [False],
        "hltb_main_hours": [5.0],
        "hltb_completionist_hours": [15.0],
        "completionist_ratio": [3.0],
        "hltb_found": [True],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


def test_filter_removes_zero_achievements():
    from score import filter_games
    df = make_df(achievements_total=[0])
    assert len(filter_games(df)) == 0


def test_filter_removes_fully_completed():
    from score import filter_games
    df = make_df(achievements_pct=[1.0])
    assert len(filter_games(df)) == 0


def test_filter_keeps_partial_progress():
    from score import filter_games
    df = make_df(achievements_pct=[0.5])
    assert len(filter_games(df)) == 1


def test_filter_keeps_untouched_with_achievements():
    from score import filter_games
    df = make_df(achievements_total=[10], achievements_pct=[0.0])
    assert len(filter_games(df)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_score.py -v
```

Expected: `ModuleNotFoundError: No module named 'score'`

- [ ] **Step 3: Implement `filter_games` in `score.py`**

Create `score.py`:

```python
import pandas as pd
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table

from config import (
    SCORING_WEIGHTS,
    STALENESS_THRESHOLD_YEARS,
    FRESHNESS_RECENT_MONTHS,
    SMALL_RETURN,
    SMALL_POOL,
    BIG_RETURN,
    BIG_POOL,
)


def filter_games(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["achievements_total"] > 0) & (df["achievements_pct"] < 1.0)].copy()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_score.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Write failing tests for `freshness_raw`**

Append to `tests/test_score.py`:

```python
def test_freshness_untouched_game():
    from score import freshness_raw
    now = datetime(2026, 6, 24)
    assert freshness_raw(0.0, 0, now) == 1.0


def test_freshness_recently_played():
    from score import freshness_raw
    now = datetime(2026, 6, 24)
    ts = int((now - timedelta(days=30)).timestamp())
    assert freshness_raw(0.5, ts, now) == 1.0


def test_freshness_at_stale_threshold():
    from score import freshness_raw
    now = datetime(2026, 6, 24)
    ts = int((now - timedelta(days=730)).timestamp())
    assert freshness_raw(0.5, ts, now) == pytest.approx(0.0, abs=0.02)


def test_freshness_beyond_stale_threshold():
    from score import freshness_raw
    now = datetime(2026, 6, 24)
    ts = int((now - timedelta(days=1000)).timestamp())
    assert freshness_raw(0.5, ts, now) == 0.0


def test_freshness_midpoint_decays_linearly():
    from score import freshness_raw
    now = datetime(2026, 6, 24)
    recent_days = 6 * 30   # FRESHNESS_RECENT_MONTHS * 30
    stale_days = 2 * 365   # STALENESS_THRESHOLD_YEARS * 365
    mid_days = (recent_days + stale_days) // 2
    ts = int((now - timedelta(days=mid_days)).timestamp())
    result = freshness_raw(0.5, ts, now)
    assert 0.4 < result < 0.6
```

- [ ] **Step 6: Run freshness tests to verify they fail**

```bash
pytest tests/test_score.py::test_freshness_untouched_game -v
```

Expected: `ImportError` — `freshness_raw` not defined yet.

- [ ] **Step 7: Implement `freshness_raw` in `score.py`**

Add to `score.py` after `filter_games`:

```python
def freshness_raw(achievements_pct: float, last_played_ts: int, now: datetime) -> float:
    if achievements_pct == 0.0:
        return 1.0
    last_played = datetime.fromtimestamp(last_played_ts) if last_played_ts else datetime.min
    days_since = (now - last_played).days
    recent_days = FRESHNESS_RECENT_MONTHS * 30
    stale_days = STALENESS_THRESHOLD_YEARS * 365
    if days_since <= recent_days:
        return 1.0
    if days_since >= stale_days:
        return 0.0
    return 1.0 - (days_since - recent_days) / (stale_days - recent_days)
```

- [ ] **Step 8: Run all tests to verify they pass**

```bash
pytest tests/test_score.py -v
```

Expected: 9 tests pass.

- [ ] **Step 9: Write failing tests for `compute_scores`**

Append to `tests/test_score.py`:

```python
def test_compute_scores_adds_score_column():
    from score import compute_scores
    df = make_df()
    result = compute_scores(df, now=datetime(2026, 6, 24))
    assert "score" in result.columns
    assert len(result) == 1


def test_compute_scores_multiplayer_penalty():
    from score import compute_scores
    now = datetime(2026, 6, 24)
    df = pd.concat([
        make_df(app_id=[1], has_multiplayer_achievement=[False]),
        make_df(app_id=[2], has_multiplayer_achievement=[True]),
    ], ignore_index=True)
    result = compute_scores(df, now=now)
    no_mp = result.loc[result["app_id"] == 1, "score"].iloc[0]
    with_mp = result.loc[result["app_id"] == 2, "score"].iloc[0]
    # Both games have identical stats, so base scores are equal; diff is exactly the penalty
    assert no_mp - with_mp == pytest.approx(60.0)


def test_compute_scores_dropped_game_penalty():
    from score import compute_scores
    now = datetime(2026, 6, 24)
    recent_ts = int((now - timedelta(days=30)).timestamp())
    old_ts = int((now - timedelta(days=800)).timestamp())
    df = pd.concat([
        make_df(app_id=[1], achievements_pct=[0.5], last_played=[recent_ts]),
        make_df(app_id=[2], achievements_pct=[0.5], last_played=[old_ts]),
    ], ignore_index=True)
    result = compute_scores(df, now=now)
    recent_score = result.loc[result["app_id"] == 1, "score"].iloc[0]
    old_score = result.loc[result["app_id"] == 2, "score"].iloc[0]
    assert recent_score > old_score


def test_compute_scores_no_intermediate_columns():
    from score import compute_scores
    df = make_df()
    result = compute_scores(df, now=datetime(2026, 6, 24))
    for col in ["ease_raw", "size_raw", "difficulty_raw", "freshness_raw_val"]:
        assert col not in result.columns
```

- [ ] **Step 10: Run compute_scores tests to verify they fail**

```bash
pytest tests/test_score.py::test_compute_scores_adds_score_column -v
```

Expected: `ImportError` — `compute_scores` not defined yet.

- [ ] **Step 11: Implement `compute_scores` in `score.py`**

Add to `score.py` after `freshness_raw`:

```python
def _minmax(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(1.0, index=series.index)
    return (series - mn) / (mx - mn)


def compute_scores(df: pd.DataFrame, now: datetime = None) -> pd.DataFrame:
    if now is None:
        now = datetime.now()
    df = df.copy()

    df["ease_raw"] = 1.0 / df["completionist_ratio"].replace(0, float("inf"))
    df["size_raw"] = 1.0 / df["hltb_completionist_hours"].replace(0, float("inf"))
    df["difficulty_raw"] = df["rarity_floor"] / 100.0
    df["freshness_raw_val"] = df.apply(
        lambda r: freshness_raw(r["achievements_pct"], r["last_played"], now), axis=1
    )

    w = SCORING_WEIGHTS
    df["score"] = (
        w["ease"] * _minmax(df["ease_raw"])
        + w["size"] * _minmax(df["size_raw"])
        + w["difficulty"] * _minmax(df["difficulty_raw"])
        + w["freshness"] * _minmax(df["freshness_raw_val"])
    ) * 100

    df.loc[df["has_multiplayer_achievement"], "score"] -= 60

    stale_cutoff = int(
        (now - timedelta(days=STALENESS_THRESHOLD_YEARS * 365)).timestamp()
    )
    stale_mask = (df["achievements_pct"] > 0) & (df["last_played"] < stale_cutoff)
    df.loc[stale_mask, "score"] -= 15

    return df.drop(columns=["ease_raw", "size_raw", "difficulty_raw", "freshness_raw_val"])
```

- [ ] **Step 12: Run all tests to verify they pass**

```bash
pytest tests/test_score.py -v
```

Expected: 13 tests pass.

- [ ] **Step 13: Write failing tests for `select_games`**

Append to `tests/test_score.py`:

```python
def make_scored_df(n: int = 20) -> pd.DataFrame:
    return pd.DataFrame({
        "app_id": list(range(n)),
        "name": [f"Game {i}" for i in range(n)],
        "hltb_completionist_hours": [float(i + 1) for i in range(n)],
        "score": [float((i + 1) * 5) for i in range(n)],
    })


def test_select_returns_correct_counts():
    from score import select_games
    import config
    df = make_scored_df(20)
    small, big = select_games(df)
    assert len(small) == config.SMALL_RETURN
    assert len(big) == config.BIG_RETURN


def test_select_small_at_or_below_median():
    from score import select_games
    df = make_scored_df(20)
    small, _ = select_games(df)
    median = df["hltb_completionist_hours"].median()
    assert all(small["hltb_completionist_hours"] <= median)


def test_select_big_above_median():
    from score import select_games
    df = make_scored_df(20)
    _, big = select_games(df)
    median = df["hltb_completionist_hours"].median()
    assert all(big["hltb_completionist_hours"] > median)


def test_select_handles_pool_smaller_than_return():
    from score import select_games
    import config
    df = make_scored_df(4)
    small, big = select_games(df)
    assert len(small) <= config.SMALL_RETURN
    assert len(big) <= config.BIG_RETURN
```

- [ ] **Step 14: Run select_games tests to verify they fail**

```bash
pytest tests/test_score.py::test_select_returns_correct_counts -v
```

Expected: `ImportError` — `select_games` not defined yet.

- [ ] **Step 15: Implement `select_games` in `score.py`**

Add to `score.py` after `compute_scores`:

```python
def select_games(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    median_hours = df["hltb_completionist_hours"].median()
    small_pool = df[df["hltb_completionist_hours"] <= median_hours].nlargest(SMALL_POOL, "score")
    big_pool = df[df["hltb_completionist_hours"] > median_hours].nlargest(BIG_POOL, "score")

    def weighted_sample(pool: pd.DataFrame, n: int) -> pd.DataFrame:
        n = min(n, len(pool))
        if n == 0:
            return pool
        weights = pool["score"].clip(lower=0)
        total = weights.sum()
        if total == 0:
            return pool.sample(n=n)
        return pool.sample(n=n, weights=weights / total)

    return weighted_sample(small_pool, SMALL_RETURN), weighted_sample(big_pool, BIG_RETURN)
```

- [ ] **Step 16: Run all tests to verify they pass**

```bash
pytest tests/test_score.py -v
```

Expected: 17 tests pass.

- [ ] **Step 17: Implement `load_games`, `print_recommendations`, and `main` in `score.py`**

Append to `score.py`:

```python
def load_games(path: str = "data/games.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def print_recommendations(small: pd.DataFrame, big: pd.DataFrame) -> None:
    console = Console()

    def make_table(title: str, games: pd.DataFrame) -> Table:
        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name")
        table.add_column("Score", justify="right")
        table.add_column("Hours (comp)", justify="right")
        table.add_column("Ach %", justify="right")
        for i, (_, row) in enumerate(games.iterrows(), 1):
            table.add_row(
                str(i),
                row["name"],
                f"{row['score']:.1f}",
                f"{row['hltb_completionist_hours']:.1f}h",
                f"{row['achievements_pct'] * 100:.0f}%",
            )
        return table

    console.print(make_table("Small Games", small))
    console.print(make_table("Big Games", big))


def main() -> None:
    df = load_games()
    df = filter_games(df)
    df = compute_scores(df)
    small, big = select_games(df)
    print_recommendations(small, big)


if __name__ == "__main__":
    main()
```

- [ ] **Step 18: Commit**

```bash
git add score.py tests/test_score.py
git commit -m "feat: add scoring engine with TDD"
```

---

### Task 3: Fetch pipeline

**Files:**
- Create: `fetch.py`
- Create: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `config.STEAM_API_KEY`, `config.STEAM_ID`, `config.MULTIPLAYER_KEYWORDS`
- Produces:
  - `get_owned_games(api_key: str, steam_id: str) -> list[dict]`
  - `get_achievement_stats(api_key: str, steam_id: str, app_id: int) -> dict | None`
  - `detect_multiplayer(api_key: str, app_id: int) -> bool`
  - `lookup_hltb(app_id: int, name: str, cache: dict) -> dict`
  - `build_row(api_key: str, steam_id: str, game: dict, cache: dict) -> dict`
  - `save_data(rows: list[dict], cache: dict) -> None`
  - `main() -> None`

- [ ] **Step 1: Write failing tests for `detect_multiplayer`**

Create `tests/test_fetch.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def mock_get(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    return m


def test_detect_multiplayer_true():
    from fetch import detect_multiplayer
    schema = {
        "game": {
            "availableGameStats": {
                "achievements": [
                    {"name": "TeamPlayer", "displayName": "Play co-op with a friend", "description": ""},
                ]
            }
        }
    }
    with patch("requests.get", return_value=mock_get(schema)):
        assert detect_multiplayer("KEY", 123) is True


def test_detect_multiplayer_false():
    from fetch import detect_multiplayer
    schema = {
        "game": {
            "availableGameStats": {
                "achievements": [
                    {"name": "Explorer", "displayName": "Find all secrets", "description": "Solo challenge"},
                ]
            }
        }
    }
    with patch("requests.get", return_value=mock_get(schema)):
        assert detect_multiplayer("KEY", 123) is False


def test_detect_multiplayer_api_error_returns_false():
    from fetch import detect_multiplayer
    with patch("requests.get", side_effect=Exception("timeout")):
        assert detect_multiplayer("KEY", 123) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fetch.py -v
```

Expected: `ModuleNotFoundError: No module named 'fetch'`

- [ ] **Step 3: Implement `detect_multiplayer` in `fetch.py`**

Create `fetch.py`:

```python
import json
import os

import pandas as pd
import requests
from tqdm import tqdm
from howlongtobeatpy import HowLongToBeat

from config import STEAM_API_KEY, STEAM_ID, MULTIPLAYER_KEYWORDS

STEAM_BASE = "https://api.steampowered.com"
DATA_DIR = "data"
GAMES_CSV = f"{DATA_DIR}/games.csv"
HLTB_CACHE_PATH = f"{DATA_DIR}/hltb_cache.json"


def detect_multiplayer(api_key: str, app_id: int) -> bool:
    try:
        resp = requests.get(
            f"{STEAM_BASE}/ISteamUserStats/GetSchemaForGame/v2/",
            params={"key": api_key, "appid": app_id},
        )
        resp.raise_for_status()
        achs = (
            resp.json()
            .get("game", {})
            .get("availableGameStats", {})
            .get("achievements", [])
        )
        for ach in achs:
            text = " ".join([
                ach.get("name", ""),
                ach.get("displayName", ""),
                ach.get("description", ""),
            ]).lower()
            if any(kw in text for kw in MULTIPLAYER_KEYWORDS):
                return True
        return False
    except Exception:
        return False
```

- [ ] **Step 4: Run detect_multiplayer tests to verify they pass**

```bash
pytest tests/test_fetch.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Write failing tests for `lookup_hltb`**

Append to `tests/test_fetch.py`:

```python
def test_lookup_hltb_cache_hit():
    from fetch import lookup_hltb
    cache = {"123": {"hltb_main_hours": 10.0, "hltb_completionist_hours": 30.0, "hltb_found": True}}
    result = lookup_hltb(123, "Some Game", cache)
    assert result["hltb_found"] is True
    assert result["hltb_completionist_hours"] == 30.0


def test_lookup_hltb_not_found_returns_fallback():
    from fetch import lookup_hltb
    with patch("howlongtobeatpy.HowLongToBeat.search", return_value=[]):
        cache = {}
        result = lookup_hltb(456, "Unknown Game", cache)
    assert result["hltb_found"] is False


def test_lookup_hltb_found_populates_cache():
    from fetch import lookup_hltb
    mock_entry = MagicMock()
    mock_entry.similarity = 0.9
    mock_entry.main_story = 8.0
    mock_entry.completionist = 25.0
    with patch("howlongtobeatpy.HowLongToBeat.search", return_value=[mock_entry]):
        cache = {}
        result = lookup_hltb(789, "Real Game", cache)
    assert result["hltb_found"] is True
    assert result["hltb_completionist_hours"] == 25.0
    assert "789" in cache
```

- [ ] **Step 6: Run lookup_hltb tests to verify they fail**

```bash
pytest tests/test_fetch.py::test_lookup_hltb_cache_hit -v
```

Expected: `ImportError` — `lookup_hltb` not defined yet.

- [ ] **Step 7: Implement `lookup_hltb` in `fetch.py`**

Add to `fetch.py` after `detect_multiplayer`:

```python
def lookup_hltb(app_id: int, name: str, cache: dict) -> dict:
    key = str(app_id)
    if key in cache:
        return cache[key]
    try:
        results = HowLongToBeat().search(name)
        if results:
            best = max(results, key=lambda r: r.similarity)
            entry = {
                "hltb_main_hours": best.main_story or 0.0,
                "hltb_completionist_hours": best.completionist or 0.0,
                "hltb_found": True,
            }
        else:
            entry = {"hltb_found": False}
    except Exception:
        entry = {"hltb_found": False}
    cache[key] = entry
    return entry
```

- [ ] **Step 8: Run all fetch tests to verify they pass**

```bash
pytest tests/test_fetch.py -v
```

Expected: 6 tests pass.

- [ ] **Step 9: Write failing tests for `get_achievement_stats`**

Append to `tests/test_fetch.py`:

```python
def test_get_achievement_stats_success():
    from fetch import get_achievement_stats
    pa_response = {
        "playerstats": {
            "success": True,
            "achievements": [
                {"achieved": 1, "apiname": "ach1"},
                {"achieved": 0, "apiname": "ach2"},
                {"achieved": 1, "apiname": "ach3"},
            ],
        }
    }
    gr_response = {
        "achievementpercentages": {
            "achievements": [
                {"name": "ach1", "percent": 80.0},
                {"name": "ach2", "percent": 10.0},
                {"name": "ach3", "percent": 50.0},
            ]
        }
    }
    with patch("requests.get", side_effect=[mock_get(pa_response), mock_get(gr_response)]):
        result = get_achievement_stats("KEY", "SID", 123)
    assert result["achievements_total"] == 3
    assert result["achievements_unlocked"] == 2
    assert result["achievements_pct"] == pytest.approx(2 / 3)
    assert result["avg_global_unlock_pct"] == pytest.approx(46.67, rel=0.01)
    assert result["rarity_floor"] == 10.0


def test_get_achievement_stats_no_success_returns_none():
    from fetch import get_achievement_stats
    pa_response = {"playerstats": {"success": False}}
    with patch("requests.get", return_value=mock_get(pa_response)):
        result = get_achievement_stats("KEY", "SID", 999)
    assert result is None


def test_get_achievement_stats_api_error_returns_none():
    from fetch import get_achievement_stats
    with patch("requests.get", side_effect=Exception("timeout")):
        result = get_achievement_stats("KEY", "SID", 999)
    assert result is None
```

- [ ] **Step 10: Run get_achievement_stats tests to verify they fail**

```bash
pytest tests/test_fetch.py::test_get_achievement_stats_success -v
```

Expected: `ImportError` — `get_achievement_stats` not defined yet.

- [ ] **Step 11: Implement `get_achievement_stats` in `fetch.py`**

Add to `fetch.py` after `lookup_hltb`:

```python
def get_achievement_stats(api_key: str, steam_id: str, app_id: int) -> dict | None:
    try:
        pa_resp = requests.get(
            f"{STEAM_BASE}/ISteamUserStats/GetPlayerAchievements/v1/",
            params={"key": api_key, "steamid": steam_id, "appid": app_id},
        )
        pa_resp.raise_for_status()
        pa_data = pa_resp.json().get("playerstats", {})
        if not pa_data.get("success", False):
            return None
        achievements = pa_data.get("achievements", [])
        if not achievements:
            return None

        unlocked = sum(1 for a in achievements if a["achieved"])
        total = len(achievements)

        gr_resp = requests.get(
            f"{STEAM_BASE}/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/",
            params={"gameid": app_id},
        )
        gr_resp.raise_for_status()
        rates = [
            a["percent"]
            for a in gr_resp.json()["achievementpercentages"]["achievements"]
        ]

        return {
            "achievements_total": total,
            "achievements_unlocked": unlocked,
            "achievements_pct": unlocked / total,
            "avg_global_unlock_pct": sum(rates) / len(rates) if rates else 0.0,
            "rarity_floor": min(rates) if rates else 0.0,
        }
    except Exception:
        return None
```

- [ ] **Step 12: Run all tests to verify they pass**

```bash
pytest tests/ -v
```

Expected: all 26 tests pass.

- [ ] **Step 13: Implement `get_owned_games`, `build_row`, `save_data`, and `main` in `fetch.py`**

Append to `fetch.py`:

```python
def get_owned_games(api_key: str, steam_id: str) -> list[dict]:
    resp = requests.get(
        f"{STEAM_BASE}/IPlayerService/GetOwnedGames/v1/",
        params={
            "key": api_key,
            "steamid": steam_id,
            "include_appinfo": 1,
            "format": "json",
        },
    )
    resp.raise_for_status()
    return resp.json()["response"].get("games", [])


def build_row(api_key: str, steam_id: str, game: dict, cache: dict) -> dict:
    app_id = game["appid"]
    name = game.get("name", f"App {app_id}")
    playtime_hours = game.get("playtime_forever", 0) / 60.0
    last_played = game.get("rtime_last_played", 0)

    stats = get_achievement_stats(api_key, steam_id, app_id)
    if stats is None:
        stats = {
            "achievements_total": 0,
            "achievements_unlocked": 0,
            "achievements_pct": 0.0,
            "avg_global_unlock_pct": 0.0,
            "rarity_floor": 0.0,
        }

    has_mp = detect_multiplayer(api_key, app_id)
    hltb = lookup_hltb(app_id, name, cache)

    if not hltb.get("hltb_found", False):
        proxy = stats["achievements_total"] * 0.167
        hltb_main = proxy
        hltb_completionist = proxy
        hltb_found = False
    else:
        hltb_main = hltb.get("hltb_main_hours") or 0.0
        hltb_completionist = hltb.get("hltb_completionist_hours") or 0.0
        hltb_found = True

    completionist_ratio = hltb_completionist / hltb_main if hltb_main > 0 else 1.0

    return {
        "app_id": app_id,
        "name": name,
        "playtime_hours": playtime_hours,
        "last_played": last_played,
        **stats,
        "has_multiplayer_achievement": has_mp,
        "hltb_main_hours": hltb_main,
        "hltb_completionist_hours": hltb_completionist,
        "completionist_ratio": completionist_ratio,
        "hltb_found": hltb_found,
    }


def save_data(rows: list[dict], cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(GAMES_CSV, index=False)
    with open(HLTB_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def main() -> None:
    games = get_owned_games(STEAM_API_KEY, STEAM_ID)

    cache: dict = {}
    if os.path.exists(HLTB_CACHE_PATH):
        with open(HLTB_CACHE_PATH) as f:
            cache = json.load(f)

    rows: list[dict] = []
    skipped = 0
    for game in tqdm(games, desc="Fetching game data", unit="game"):
        try:
            rows.append(build_row(STEAM_API_KEY, STEAM_ID, game, cache))
        except Exception:
            skipped += 1

    if skipped:
        print(f"Warning: {skipped} games skipped due to unexpected errors.")

    save_data(rows, cache)
    print(f"Done. {len(rows)} games written to {GAMES_CSV}.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 14: Run all tests one final time**

```bash
pytest tests/ -v
```

Expected: all 26 tests pass with no warnings.

- [ ] **Step 15: Commit**

```bash
git add fetch.py tests/test_fetch.py
git commit -m "feat: add fetch pipeline with Steam API and HLTB integration"
```

---

## End-to-end smoke test

After both tasks are complete, verify the full workflow:

```bash
# Fetch data (takes 5–15 min on first run)
python fetch.py

# Get recommendations
python score.py

# Re-roll for a fresh draw
python score.py
```

`fetch.py` should show a tqdm progress bar over your game library and finish with:
`Done. N games written to data/games.csv.`

`score.py` should print two rich tables — **Small Games** and **Big Games** — each with columns: `#`, `Name`, `Score`, `Hours (comp)`, `Ach %`.
