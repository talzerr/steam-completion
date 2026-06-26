from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    STEAM_API_KEY: str | None = None
    STEAM_ID: str | None = None


settings = Settings()
STEAM_API_KEY = settings.STEAM_API_KEY
STEAM_ID = settings.STEAM_ID

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
