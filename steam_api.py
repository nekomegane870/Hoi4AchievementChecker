"""
Steam Web API wrapper for HoI4 Achievement Checker.

Uses three endpoints:
- GetSchemaForGame       → achievement names, descriptions, icons
- GetPlayerAchievements  → player's unlock status per achievement
- GetGlobalAchievementPercentagesForApp → global completion rates
"""

import time
import requests
from typing import Optional

HOI4_APP_ID = 394360
BASE_URL = "https://api.steampowered.com"


class SteamAPIError(Exception):
    """Raised when a Steam API call fails."""
    pass


class SteamAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: dict = {}   # (endpoint, kwargs) -> (timestamp, data)
        self.cache_ttl: int = 1800  # 30 minutes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get(self, url: str, params: dict) -> dict:
        cache_key = (url, str(sorted(params.items())))
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if time.time() - ts < self.cache_ttl:
                return data

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise SteamAPIError(f"HTTP request failed: {e}") from e

        data = resp.json()
        self._cache[cache_key] = (time.time(), data)
        return data

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------
    def get_schema(self, lang: str = "japanese") -> list[dict]:
        """
        Fetch the achievement schema for HoI4.
        Returns a list of dicts with keys:
            name, displayName, description, icon, icongray, hidden
        """
        url = f"{BASE_URL}/ISteamUserStats/GetSchemaForGame/v2/"
        data = self._get(url, {
            "key": self.api_key,
            "appid": HOI4_APP_ID,
            "l": lang,
        })
        game = data.get("game", {})
        available = game.get("availableGameStats", {})
        achievements = available.get("achievements", [])
        return achievements

    def get_player_achievements(self, steam_id: str, lang: str = "japanese") -> list[dict]:
        """
        Fetch a player's achievement unlock status.
        Returns a list of dicts with keys:
            apiname, achieved (0/1), unlocktime
        Raises SteamAPIError if the profile is private or steam_id is invalid.
        """
        url = f"{BASE_URL}/ISteamUserStats/GetPlayerAchievements/v1/"
        data = self._get(url, {
            "key": self.api_key,
            "steamid": steam_id,
            "appid": HOI4_APP_ID,
            "l": lang,
        })
        pstats = data.get("playerstats", {})
        if not pstats.get("success", False):
            error_msg = pstats.get("error", "Unknown error")
            raise SteamAPIError(f"GetPlayerAchievements failed: {error_msg}")
        return pstats.get("achievements", [])

    def get_global_percentages(self) -> dict[str, float]:
        """
        Fetch global achievement completion percentages.
        Returns a dict mapping achievement API name -> percentage (0‑100).
        """
        url = f"{BASE_URL}/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
        data = self._get(url, {"gameid": HOI4_APP_ID})
        achievements = data.get("achievementpercentages", {}).get("achievements", [])
        return {a["name"]: float(a.get("percent", 0.0)) for a in achievements}

    def get_all_data(self, steam_id: str, lang: str = "japanese") -> dict:
        """
        Convenience method that fetches schema, player status, and global
        percentages and merges them into a unified list.

        Each item in the returned list contains:
            name          – API name
            displayName   – Localised display name
            description   – Localised description
            icon          – URL of the colour icon
            icongray      – URL of the grey icon
            hidden        – 1 if hidden, 0 if public
            achieved      – True/False
            unlocktime    – Unix timestamp (0 if not achieved)
            global_pct    – float, global achievement rate (0‑100)
        """
        schema = self.get_schema(lang)
        player = self.get_player_achievements(steam_id, lang)
        global_pct = self.get_global_percentages()

        player_map = {a["apiname"]: a for a in player}

        merged = []
        for ach in schema:
            name = ach.get("name", "")
            player_data = player_map.get(name, {})
            merged.append({
                "name": name,
                "displayName": ach.get("displayName", name),
                "description": ach.get("description", ""),
                "icon": ach.get("icon", ""),
                "icongray": ach.get("icongray", ""),
                "hidden": ach.get("hidden", 0),
                "achieved": bool(player_data.get("achieved", 0)),
                "unlocktime": player_data.get("unlocktime", 0),
                "global_pct": global_pct.get(name, 0.0),
            })

        # Sort by global completion rate descending (easiest first)
        merged.sort(key=lambda x: x["global_pct"], reverse=True)
        return {
            "achievements": merged,
            "total": len(merged),
            "achieved_count": sum(1 for a in merged if a["achieved"]),
        }
