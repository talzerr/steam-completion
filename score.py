import pandas as pd
from datetime import datetime, timedelta

from config import (
    SCORING_WEIGHTS,
    STALENESS_THRESHOLD_YEARS,
    FRESHNESS_RECENT_MONTHS,
)

TOP_N = 30
SHORTLIST_PATH = "data/shortlist.csv"

# Columns written to the shortlist, in display order.
SHORTLIST_COLUMNS = [
    "name",
    "score",
    "hltb_completionist_hours",
    "achievements_pct",
    "playtime_hours",
    "last_played",
    "has_multiplayer_achievement",
    "rarity_floor",
    "avg_global_unlock_pct",
    "hltb_found",
]


def filter_games(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["achievements_total"] > 0) & (df["achievements_pct"] < 1.0)].copy()


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


def _minmax(series: pd.Series) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(1.0, index=series.index)
    return (series - mn) / (mx - mn)


def compute_scores(df: pd.DataFrame, now: datetime = None) -> pd.DataFrame:
    if now is None:
        now = datetime.now()
    df = df.copy()

    # Ease is only meaningful when we have real HowLongToBeat times. When HLTB
    # has no data, completionist_ratio falls back to 1.0 (= max ease), which
    # would unfairly float those games to the top. Mark ease as missing here and
    # neutral-impute it below instead of rewarding the missing data.
    ease_valid = (
        df["hltb_found"]
        & (df["hltb_main_hours"] > 0)
        & (df["hltb_completionist_hours"] > 0)
    )
    df["ease_raw"] = 1.0 / df["completionist_ratio"].replace(0, float("inf"))
    df.loc[~ease_valid, "ease_raw"] = float("nan")

    df["size_raw"] = 1.0 / df["hltb_completionist_hours"].replace(0, float("inf"))
    df["difficulty_raw"] = df["rarity_floor"]  # already normalized to [0, 1] at load
    df["freshness_raw_val"] = df.apply(
        lambda r: freshness_raw(r["achievements_pct"], r["last_played"], now), axis=1
    )

    ease_norm = _minmax(df["ease_raw"])
    ease_norm = ease_norm.fillna(ease_norm.median())  # missing HLTB -> neutral, not max

    w = SCORING_WEIGHTS
    df["score"] = (
        w["ease"] * ease_norm
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


def load_games(path: str = "data/games.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["name"] = df["name"].str.strip()
    # Normalize percent-scale columns to [0, 1] so every fraction-like field
    # (achievements_pct, avg_global_unlock_pct, rarity_floor) lives on one scale.
    df["avg_global_unlock_pct"] = df["avg_global_unlock_pct"] / 100.0
    df["rarity_floor"] = df["rarity_floor"] / 100.0
    return df


def build_shortlist(df: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    shortlist = df.nlargest(top_n, "score")[SHORTLIST_COLUMNS].copy()
    shortlist.insert(0, "rank", range(1, len(shortlist) + 1))
    return shortlist


def main() -> None:
    df = load_games()
    df = filter_games(df)
    df = compute_scores(df)
    shortlist = build_shortlist(df)
    shortlist.to_csv(SHORTLIST_PATH, index=False)
    print(f"Wrote top {len(shortlist)} candidates to {SHORTLIST_PATH}")
    for _, r in shortlist.iterrows():
        print(
            f"{r['rank']:2}. {r['score']:5.1f}  {r['name'][:45]:45} "
            f"{r['hltb_completionist_hours']:6.1f}h  ach={r['achievements_pct']*100:3.0f}%"
        )


if __name__ == "__main__":
    main()
