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


def test_lookup_hltb_cache_hit():
    from fetch import lookup_hltb
    cache = {"123": {"hltb_main_hours": 10.0, "hltb_completionist_hours": 30.0, "hltb_found": True}}
    result = lookup_hltb(123, "Some Game", cache)
    assert result["hltb_found"] is True
    assert result["hltb_completionist_hours"] == 30.0


def test_lookup_hltb_not_found_returns_fallback():
    from fetch import lookup_hltb
    with patch("howlongtobeatpy.HowLongToBeat.HowLongToBeat.search", return_value=[]):
        cache = {}
        result = lookup_hltb(456, "Unknown Game", cache)
    assert result["hltb_found"] is False


def test_lookup_hltb_found_populates_cache():
    from fetch import lookup_hltb
    mock_entry = MagicMock()
    mock_entry.similarity = 0.9
    mock_entry.main_story = 8.0
    mock_entry.completionist = 25.0
    with patch("howlongtobeatpy.HowLongToBeat.HowLongToBeat.search", return_value=[mock_entry]):
        cache = {}
        result = lookup_hltb(789, "Real Game", cache)
    assert result["hltb_found"] is True
    assert result["hltb_completionist_hours"] == 25.0
    assert "789" in cache


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
