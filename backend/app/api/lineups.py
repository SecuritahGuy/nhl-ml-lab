from fastapi import APIRouter
from app.services.nhl import get_gamecenter_landing, get_gamecenter_boxscore

router = APIRouter()


@router.get("/game/{game_id}")
async def get_game_lineup(game_id: int):
    data = await get_gamecenter_landing(game_id)
    if not data:
        return {"game_id": game_id, "error": "Game not found"}

    game = {
        "id": data.get("id"),
        "game_date": data.get("gameDate"),
        "game_state": data.get("gameState"),
        "venue": data.get("venue", {}).get("default"),
        "home_team": {
            "id": data.get("homeTeam", {}).get("id", 0),
            "abbrev": data.get("homeTeam", {}).get("abbrev", ""),
            "common_name": data.get("homeTeam", {}).get("commonName", {}).get("default", ""),
            "place_name": data.get("homeTeam", {}).get("placeName", {}).get("default", ""),
        },
        "away_team": {
            "id": data.get("awayTeam", {}).get("id", 0),
            "abbrev": data.get("awayTeam", {}).get("abbrev", ""),
            "common_name": data.get("awayTeam", {}).get("commonName", {}).get("default", ""),
            "place_name": data.get("awayTeam", {}).get("placeName", {}).get("default", ""),
        },
    }

    matchup = data.get("matchup", {})
    home_leaders = {}
    away_leaders = {}
    for c in matchup.get("skaterComparison", {}).get("leaders", []):
        cat = c.get("category")
        away_leader = c.get("awayLeader", {})
        home_leader = c.get("homeLeader", {})
        if cat:
            away_leaders[cat] = {
                "player_id": away_leader.get("playerId"),
                "name": away_leader.get("name", {}).get("default"),
                "value": away_leader.get("value"),
                "position_code": away_leader.get("positionCode"),
                "sweater_number": away_leader.get("sweaterNumber"),
            }
            home_leaders[cat] = {
                "player_id": home_leader.get("playerId"),
                "name": home_leader.get("name", {}).get("default"),
                "value": home_leader.get("value"),
                "position_code": home_leader.get("positionCode"),
                "sweater_number": home_leader.get("sweaterNumber"),
            }

    return {
        "game": game,
        "home_leaders": home_leaders,
        "away_leaders": away_leaders,
    }