from fastapi import APIRouter, Query
from app.services.nhl import get_standings, get_gamecenter_landing
from app.models.predictor import predict_game

router = APIRouter()

SEASON_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "VAN", "VGK", "WPG",
    "WSH", "UTA",
]


@router.get("/{game_id}")
async def get_prediction(game_id: int):
    data = await get_gamecenter_landing(game_id)
    if not data:
        return {"game_id": game_id, "error": "Game not found"}

    home = data.get("homeTeam", {})
    away = data.get("awayTeam", {})

    home_abbrev = home.get("abbrev", "")
    away_abbrev = away.get("abbrev", "")
    home_record = home.get("record", "0-0-0")
    away_record = away.get("record", "0-0-0")

    def parse_record(r: str):
        parts = r.split("-")
        return {"wins": int(parts[0]), "losses": int(parts[1]), "ot_losses": int(parts[2])} if len(parts) == 3 else {"wins": 0, "losses": 0, "ot_losses": 0}

    hr = parse_record(home_record)
    ar = parse_record(away_record)
    total_h = hr["wins"] + hr["losses"] + hr["ot_losses"]
    total_a = ar["wins"] + ar["losses"] + ar["ot_losses"]
    home_win_pct = hr["wins"] / total_h if total_h > 0 else 0.5
    away_win_pct = ar["wins"] / total_a if total_a > 0 else 0.5

    result = predict_game(
        home_team=home_abbrev,
        away_team=away_abbrev,
        home_stats={"avgGoalsFor": 3.2, "avgGoalsAgainst": 2.8, "elo": 1500 + int((home_win_pct - 0.5) * 200)},
        away_stats={"avgGoalsFor": 3.0, "avgGoalsAgainst": 3.0, "elo": 1500 + int((away_win_pct - 0.5) * 200)},
        home_recent=[home_win_pct * 6] * 5,
        away_recent=[away_win_pct * 6] * 5,
    )

    return {
        "game_id": game_id,
        "home_team": home.get("placeName", {}).get("default", ""),
        "away_team": away.get("placeName", {}).get("default", ""),
        "home_team_abbrev": home_abbrev,
        "away_team_abbrev": away_abbrev,
        **result,
    }


@router.get("")
async def get_bulk_predictions(date: str | None = Query(default=None)):
    from app.services.nhl import get_scoreboard_now, parse_scoreboard

    data = await get_scoreboard_now()
    parsed = parse_scoreboard(data)
    games = parsed.get("games", [])

    predictions = []
    for g in games:
        if g.get("game_state") in ("OFF", "FINAL"):
            continue
        home_abbrev = g.get("home_team", {}).get("abbrev", "")
        away_abbrev = g.get("away_team", {}).get("abbrev", "")
        if not home_abbrev or not away_abbrev:
            continue

        result = predict_game(
            home_team=home_abbrev,
            away_team=away_abbrev,
            home_stats={"avgGoalsFor": 3.2, "avgGoalsAgainst": 2.8},
            away_stats={"avgGoalsFor": 3.0, "avgGoalsAgainst": 3.0},
            home_recent=[3.2] * 5,
            away_recent=[3.0] * 5,
        )

        predictions.append({
            "game_id": g["id"],
            "home_team": g.get("home_team", {}).get("place_name", ""),
            "away_team": g.get("away_team", {}).get("place_name", ""),
            "home_team_abbrev": home_abbrev,
            "away_team_abbrev": away_abbrev,
            "game_date": g.get("game_date"),
            "game_state": g.get("game_state"),
            **result,
        })

    return {"predictions": predictions, "count": len(predictions)}