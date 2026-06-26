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
            float(a["percent"])
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


PROGRESS_PATH = f"{DATA_DIR}/progress.json"


def save_data(rows: list[dict], cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(GAMES_CSV, index=False)
    with open(HLTB_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def save_progress(rows: list[dict], cache: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROGRESS_PATH, "w") as f:
        json.dump(rows, f)
    with open(HLTB_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def load_progress() -> list[dict]:
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return []


def main() -> None:
    games = get_owned_games(STEAM_API_KEY, STEAM_ID)

    cache: dict = {}
    if os.path.exists(HLTB_CACHE_PATH):
        with open(HLTB_CACHE_PATH) as f:
            cache = json.load(f)

    rows = load_progress()
    done_ids = {r["app_id"] for r in rows}
    remaining = [g for g in games if g["appid"] not in done_ids]

    if rows:
        print(f"Resuming from {len(rows)}/{len(games)} games already processed.")

    skipped = 0
    for game in tqdm(remaining, desc="Fetching game data", unit="game"):
        try:
            rows.append(build_row(STEAM_API_KEY, STEAM_ID, game, cache))
        except Exception:
            skipped += 1
        save_progress(rows, cache)

    if skipped:
        print(f"Warning: {skipped} games skipped due to unexpected errors.")

    save_data(rows, cache)
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
    print(f"Done. {len(rows)} games written to {GAMES_CSV}.")


if __name__ == "__main__":
    main()
