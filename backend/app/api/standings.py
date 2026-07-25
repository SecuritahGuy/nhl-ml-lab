from fastapi import APIRouter, Query
from app.services.nhl import get_standings

router = APIRouter()


def _parse_team(entry: dict) -> dict:
    return {
        "team_abbrev": entry.get("teamAbbrev", {}).get("default", ""),
        "team_name": entry.get("teamName", {}).get("default", ""),
        "games_played": entry.get("gamesPlayed", 0),
        "wins": entry.get("wins", 0),
        "losses": entry.get("losses", 0),
        "ot_losses": entry.get("otLosses", 0),
        "points": entry.get("points", 0),
        "goals_for": entry.get("goalFor", 0),
        "goals_against": entry.get("goalAgainst", 0),
        "goal_differential": entry.get("goalDifferential", 0),
        "win_pct": entry.get("winPctg", 0),
        "points_pct": entry.get("pointPctg", 0),
        "conference_name": entry.get("conferenceName", ""),
        "conference_sequence": entry.get("conferenceSequence", 0),
        "division_name": entry.get("divisionName", ""),
        "division_sequence": entry.get("divisionSequence", 0),
        "streak": entry.get("streak", ""),
        "clinch_indicator": entry.get("clinchIndicator", ""),
        "home_record": f"{entry.get('homeWins', 0)}-{entry.get('homeLosses', 0)}-{entry.get('homeOtLosses', 0)}",
        "road_record": f"{entry.get('roadWins', 0)}-{entry.get('roadLosses', 0)}-{entry.get('roadOtLosses', 0)}",
        "l10": f"{entry.get('L10Wins', 0)}-{entry.get('L10Losses', 0)}-{entry.get('L10OtLosses', 0)}",
    }


def _group_by_division(standings: list) -> list:
    divisions = {}
    for entry in standings:
        div = entry.get("divisionName", "Unknown")
        if div not in divisions:
            divisions[div] = {
                "division_name": div,
                "conference_name": entry.get("conferenceName", ""),
                "teams": [],
            }
        divisions[div]["teams"].append(_parse_team(entry))

    for div in divisions.values():
        div["teams"].sort(key=lambda t: t.get("points", 0), reverse=True)

    return list(divisions.values())


@router.get("")
async def get_current_standings(
    date: str | None = Query(default=None),
    group_by_division: bool = Query(default=False, alias="group"),
):
    data = await get_standings(date)
    if not data:
        return {"standings": []}

    standings = data.get("standings", [])
    if not standings:
        return {"standings": []}

    return {
        "date": data.get("standingsDateTimeUtc", ""),
        "conferences": _group_by_division(standings) if group_by_division else standings,
    }