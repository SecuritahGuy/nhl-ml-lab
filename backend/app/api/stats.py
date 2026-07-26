from fastapi import APIRouter, Query
from app.services.nhl import (
    get_team_stats, get_skater_stats, get_goalie_stats,
    get_skater_leaders, get_goalie_leaders, get_team_stats_full,
    get_game_right_rail,
)

router = APIRouter()

REPORTS_TEAM = [
    "summary", "realtime", "powerplay", "penaltykill",
    "goalsforbystrength", "faceoffpercentages",
]
REPORTS_SKATER = [
    "summary", "realtime", "faceoffpercentages", "goalsForAgainst",
    "powerplay", "penaltykill", "bios",
]
REPORTS_GOALIE = ["summary", "advanced", "savesByStrength", "bios"]


@router.get("/teams")
async def get_team_season_stats(
    season: str = Query(default="20242025"),
    report: str = Query(default="summary"),
):
    if report == "all":
        data = await get_team_stats_full(season)
        return data or {}
    data = await get_team_stats(season, game_type=2)
    return {"season": season, "teams": data or []}


@router.get("/skaters")
async def get_skater_season_stats(
    season: str = Query(default="20242025"),
    report: str = Query(default="summary"),
    limit: int = Query(default=100, le=500),
):
    if report not in REPORTS_SKATER:
        report = "summary"
    data = await get_skater_stats(season=season, report=report, limit=limit)
    return {"season": season, "report": report, "skaters": data or []}


@router.get("/goalies")
async def get_goalie_season_stats(
    season: str = Query(default="20242025"),
    report: str = Query(default="summary"),
    limit: int = Query(default=50, le=200),
):
    if report not in REPORTS_GOALIE:
        report = "summary"
    data = await get_goalie_stats(season=season, report=report, limit=limit)
    return {"season": season, "report": report, "goalies": data or []}


@router.get("/leaders")
async def get_stats_leaders():
    skaters = await get_skater_leaders()
    goalies = await get_goalie_leaders()
    return {
        "skaters": skaters or {},
        "goalies": goalies or {},
    }


@router.get("/game/{game_id}")
async def get_game_stats(game_id: int):
    return await get_game_right_rail(game_id) or {}