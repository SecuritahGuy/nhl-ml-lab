import httpx
import logging
from app.services import cache

logger = logging.getLogger(__name__)

WEB = "https://api-web.nhle.com/v1"
STATS = "https://api.nhle.com/stats/rest/en"
LEGACY = "https://statsapi.web.nhl.com/api/v1"
CACHE_TTL = 300


async def _fetch(url: str, force_refresh: bool = False) -> dict | list | None:
    if not force_refresh:
        cached = await cache.get(url, ttl=CACHE_TTL)
        if cached:
            return cached

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            await cache.set(url, data)
            return data
        except httpx.HTTPError as e:
            logger.warning(f"HTTP {e.response.status_code if e.response else 'error'} for {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None


def _team_info(t: dict) -> dict:
    return {
        "id": t.get("id", 0),
        "abbrev": t.get("abbrev", ""),
        "common_name": t.get("commonName", {}).get("default", ""),
        "place_name": t.get("placeName", {}).get("default", ""),
        "logo": t.get("logo", ""),
        "record": t.get("record"),
    }


_POSITION_ORDER = {"C": 0, "R": 1, "L": 2, "D": 3, "G": 4}


def _sort_roster(players: list) -> list:
    return sorted(players, key=lambda p: _POSITION_ORDER.get(p.get("positionCode", "Z"), 9))


def _roster_player(p: dict) -> dict:
    return {
        "id": p.get("id", 0),
        "first_name": p.get("firstName", {}).get("default", ""),
        "last_name": p.get("lastName", {}).get("default", ""),
        "position_code": p.get("positionCode", ""),
        "sweater_number": p.get("sweaterNumber"),
        "birth_date": p.get("birthDate"),
        "birth_city": p.get("birthCity", {}).get("default") if isinstance(p.get("birthCity"), dict) else None,
        "birth_state_province": p.get("birthStateProvince", {}).get("default") if isinstance(p.get("birthStateProvince"), dict) else None,
        "birth_country": p.get("birthCountry"),
        "height_inches": p.get("heightInInches"),
        "weight_pounds": p.get("weightInPounds"),
        "headshot": p.get("headshot"),
        "shoots_catches": p.get("shootsCatches"),
    }


async def get_scoreboard_now() -> dict | None:
    return await _fetch(f"{WEB}/score/now")


async def get_schedule(date: str | None = None) -> dict | None:
    endpoint = f"schedule/{date}" if date else "schedule/now"
    return await _fetch(f"{WEB}/{endpoint}")


async def get_club_schedule_season(team_abbr: str) -> dict | None:
    return await _fetch(f"{WEB}/club-schedule-season/{team_abbr}/now")


async def get_team_roster(team_abbr: str, season: str = "20252026") -> dict | None:
    return await _fetch(f"{WEB}/roster/{team_abbr}/{season}")


async def get_gamecenter_landing(game_id: int) -> dict | None:
    return await _fetch(f"{WEB}/gamecenter/{game_id}/landing")


async def get_game_right_rail(game_id: int) -> dict | None:
    return await _fetch(f"{WEB}/gamecenter/{game_id}/right-rail")


async def get_gamecenter_boxscore(game_id: int) -> dict | None:
    return await _fetch(f"{WEB}/gamecenter/{game_id}/boxscore")


async def get_standings(date: str | None = None) -> dict | None:
    endpoint = "standings/now" if date is None else f"standings/{date}"
    return await _fetch(f"{WEB}/{endpoint}")


async def get_all_teams() -> list | None:
    data = await _fetch(f"{STATS}/team")
    if data and isinstance(data, dict):
        return data.get("data", [])
    return None


async def get_team_stats(season: str = "20242025", game_type: int = 2) -> list | None:
    cayenne = f"cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
    data = await _fetch(f"{STATS}/team/summary?{cayenne}&limit=100")
    if data and isinstance(data, dict):
        return data.get("data", [])
    return None


async def get_team_stats_full(season: str = "20242025") -> dict | None:
    result = {}
    for report in ["summary", "realtime", "powerplay", "penaltykill", "goalsforbystrength", "faceoffpercentages"]:
        cayenne = f"cayenneExp=seasonId={season}%20and%20gameTypeId=2"
        data = await _fetch(f"{STATS}/team/{report}?{cayenne}&limit=100")
        if data and isinstance(data, dict):
            result[report] = data.get("data", [])
    return result


async def get_skater_stats(season: str = "20242025", game_type: int = 2,
                           report: str = "summary", limit: int = 50) -> list | None:
    cayenne = f"cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
    data = await _fetch(f"{STATS}/skater/{report}?{cayenne}&limit={limit}")
    if data and isinstance(data, dict):
        return data.get("data", [])
    return None


async def get_goalie_stats(season: str = "20242025", game_type: int = 2,
                           report: str = "summary", limit: int = 50) -> list | None:
    cayenne = f"cayenneExp=seasonId={season}%20and%20gameTypeId={game_type}"
    data = await _fetch(f"{STATS}/goalie/{report}?{cayenne}&limit={limit}")
    if data and isinstance(data, dict):
        return data.get("data", [])
    return None


async def get_skater_leaders() -> dict | None:
    return await _fetch(f"{WEB}/skater-stats-leaders/current")


async def get_goalie_leaders() -> dict | None:
    return await _fetch(f"{WEB}/goalie-stats-leaders/current")


async def get_player_landing(player_id: int) -> dict | None:
    return await _fetch(f"{WEB}/player/{player_id}/landing")


async def get_search_players(query: str, limit: int = 20) -> list | None:
    url = f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit={limit}&q={query}"
    data = await _fetch(url)
    return data if isinstance(data, list) else None


def parse_scoreboard(data: dict | None) -> dict:
    if not data:
        return {"prev_date": None, "current_date": None, "next_date": None, "game_week": [], "games": []}

    games = []
    for day in data.get("gameWeek", []):
        for g in day.get("games", []):
            games.append({
                "id": g.get("id", 0),
                "season": g.get("season", 0),
                "game_type": g.get("gameType", 0),
                "game_date": g.get("gameDate", ""),
                "start_time_utc": g.get("startTimeUTC", ""),
                "game_state": g.get("gameState", ""),
                "venue": g.get("venue", {}).get("default", ""),
                "home_team": _team_info(g.get("homeTeam", {})),
                "away_team": _team_info(g.get("awayTeam", {})),
                "home_score": g.get("homeTeam", {}).get("score"),
                "away_score": g.get("awayTeam", {}).get("score"),
                "period": g.get("periodDescriptor", {}).get("number"),
                "clock": g.get("clock"),
            })

    return {
        "prev_date": data.get("prevDate"),
        "current_date": data.get("currentDate"),
        "next_date": data.get("nextDate"),
        "game_week": data.get("gameWeek", []),
        "games": games,
    }


def parse_roster(data: dict | None, team_abbr: str, season: str) -> dict:
    if not data:
        return {"team_abbrev": team_abbr, "season": season, "forwards": [], "defensemen": [], "goalies": []}

    return {
        "team_abbrev": team_abbr,
        "season": season,
        "forwards": sorted(
            [_roster_player(p) for p in data.get("forwards", [])],
            key=lambda p: p.get("position_code", "Z"),
        ),
        "defensemen": sorted(
            [_roster_player(p) for p in data.get("defensemen", [])],
            key=lambda p: (p.get("sweater_number") or 99, p.get("last_name", "")),
        ),
        "goalies": sorted(
            [_roster_player(p) for p in data.get("goalies", [])],
            key=lambda p: (p.get("sweater_number") or 99, p.get("last_name", "")),
        ),
    }


def parse_standings(data: dict | None) -> list:
    if not data:
        return []
    return data.get("standings", [])


def parse_gamecenter_landing(data: dict | None) -> dict | None:
    if not data:
        return None

    game = {
        "id": data.get("id"),
        "season": data.get("season"),
        "game_type": data.get("gameType"),
        "game_date": data.get("gameDate"),
        "start_time_utc": data.get("startTimeUTC"),
        "game_state": data.get("gameState"),
        "venue": data.get("venue", {}).get("default"),
        "venue_location": data.get("venueLocation", {}).get("default"),
        "away_team": _team_info(data.get("awayTeam", {})),
        "home_team": _team_info(data.get("homeTeam", {})),
        "game_center_link": data.get("gameCenterLink"),
    }

    matchup = data.get("matchup")
    if matchup:
        game["matchup"] = matchup

    return game