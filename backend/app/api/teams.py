from fastapi import APIRouter
from app.services.nhl import get_all_teams

router = APIRouter()

ACTIVE_NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
    "WPG", "WSH",
]


@router.get("")
async def list_teams():
    teams = await get_all_teams()
    if not teams:
        return {"teams": []}

    seen = set()
    result = []
    for t in teams:
        code = t.get("triCode", "")
        if not code:
            continue
        if code not in seen:
            seen.add(code)
            if code in ACTIVE_NHL_TEAMS:
                result.append({
                    "id": t.get("id"),
                    "abbrev": code,
                    "full_name": t.get("fullName"),
                })
    return {"teams": sorted(result, key=lambda x: x["abbrev"])}