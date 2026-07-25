from fastapi import APIRouter, Query
from app.services.nhl import get_scoreboard_now, get_schedule, get_club_schedule_season

router = APIRouter()


def _parse_game(g: dict) -> dict:
    return {
        "id": g.get("id", 0),
        "season": g.get("season", 0),
        "game_type": g.get("gameType", 0),
        "game_date": g.get("gameDate", ""),
        "start_time_utc": g.get("startTimeUTC", ""),
        "game_state": g.get("gameState", ""),
        "venue": g.get("venue", {}).get("default", ""),
        "home_team": {
            "id": g.get("homeTeam", {}).get("id", 0),
            "abbrev": g.get("homeTeam", {}).get("abbrev", ""),
            "common_name": g.get("homeTeam", {}).get("commonName", {}).get("default", ""),
            "place_name": g.get("homeTeam", {}).get("placeName", {}).get("default", ""),
            "logo": g.get("homeTeam", {}).get("logo", ""),
        },
        "away_team": {
            "id": g.get("awayTeam", {}).get("id", 0),
            "abbrev": g.get("awayTeam", {}).get("abbrev", ""),
            "common_name": g.get("awayTeam", {}).get("commonName", {}).get("default", ""),
            "place_name": g.get("awayTeam", {}).get("placeName", {}).get("default", ""),
            "logo": g.get("awayTeam", {}).get("logo", ""),
        },
        "home_score": g.get("homeTeam", {}).get("score"),
        "away_score": g.get("awayTeam", {}).get("score"),
        "period": g.get("periodDescriptor", {}).get("number"),
        "clock": g.get("clock"),
    }


def _collect_games(data: dict) -> list:
    games = []
    for day in data.get("gameWeek", []):
        for g in day.get("games") or []:
            games.append(_parse_game(g))
    return games


@router.get("")
async def get_daily_schedule(date: str | None = Query(default=None)):
    if date:
        data = await get_schedule(date)
        if data:
            games = _collect_games(data)
            return {"date": date, "games": games}
        return {"date": date, "games": []}

    data = await get_scoreboard_now()
    if not data:
        return {"games": []}

    return {
        "prev_date": data.get("prevDate"),
        "current_date": data.get("currentDate"),
        "next_date": data.get("nextDate"),
        "games": _collect_games(data),
    }


@router.get("/team/{team_abbrev}")
async def get_team_schedule(team_abbrev: str):
    data = await get_club_schedule_season(team_abbrev.upper())
    if not data:
        return {"team_abbrev": team_abbrev, "season": None, "games": []}

    games = [_parse_game(g) for g in data.get("games", [])]

    return {
        "team_abbrev": team_abbrev,
        "season": data.get("currentSeason"),
        "games": games,
    }