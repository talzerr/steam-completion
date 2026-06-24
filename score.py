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
