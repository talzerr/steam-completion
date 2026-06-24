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
