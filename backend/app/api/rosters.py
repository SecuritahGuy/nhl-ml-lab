from fastapi import APIRouter, Query
from app.services.nhl import get_team_roster, parse_roster, get_all_teams

router = APIRouter()


@router.get("/{team_abbrev}")
async def get_roster(
    team_abbrev: str,
    season: str = Query(default="20252026", description="NHL season (e.g. 20252026)"),
):
    data = await get_team_roster(team_abbrev.upper(), season)
    return parse_roster(data, team_abbrev.upper(), season)


@router.get("")
async def list_available_teams():
    teams = await get_all_teams()
    if not teams:
        return {"teams": []}
    current = [t for t in teams if t.get("id", 0) < 60 and t.get("triCode") and t.get("id", 0) <= 55]
    seen = set()
    result = []
    for t in sorted(current, key=lambda x: x.get("triCode", "")):
        code = t.get("triCode", "")
        if code and code not in seen:
            seen.add(code)
            result.append({
                "id": t.get("id"),
                "abbrev": code,
                "full_name": t.get("fullName"),
            })
    return {"teams": result}