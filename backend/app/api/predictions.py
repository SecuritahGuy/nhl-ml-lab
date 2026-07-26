import asyncio
from datetime import datetime, date
from fastapi import APIRouter, Query
from app.services.nhl import get_gamecenter_landing, get_team_stats, _fetch
from app.models.predictor import predict_game

ROLLING_WINDOWS = [3, 5, 10, 20]
DECAY_FACTORS = [0.7, 0.8, 0.9]

router = APIRouter()

_stats_cache: dict[str, dict[int, dict]] = {}
_games_cache: dict[str, list[dict]] = {}


async def _get_team_stats_map(season: str) -> dict[int, dict]:
    if season in _stats_cache:
        return _stats_cache[season]
    raw = await get_team_stats(season)
    mapping: dict[int, dict] = {}
    if raw:
        for t in raw:
            tid = t.get("teamId")
            if tid:
                mapping[tid] = {
                    "gf_per_game": t.get("goalsForPerGame", 3.0),
                    "ga_per_game": t.get("goalsAgainstPerGame", 3.0),
                    "pp_pct": t.get("powerPlayPct", 0.20),
                    "pk_pct": t.get("penaltyKillPct", 0.80),
                    "fo_pct": t.get("faceoffWinPct", 0.50),
                    "sf_per_game": t.get("shotsForPerGame", 30.0),
                    "sa_per_game": t.get("shotsAgainstPerGame", 30.0),
                    "point_pct": t.get("pointPct", 0.50),
                    "wins": t.get("wins", 0),
                    "losses": t.get("losses", 0),
                    "ot_losses": t.get("otLosses", 0),
                    "goals_for": t.get("goalsFor", 0),
                    "goals_against": t.get("goalsAgainst", 0),
                }
    _stats_cache[season] = mapping
    return mapping


async def _get_season_games(season: str) -> list[dict]:
    if season in _games_cache:
        return _games_cache[season]
    url = f"https://api.nhle.com/stats/rest/en/game?cayenneExp=season={season}"
    data = await _fetch(url)
    games = data.get("data", []) if data else []
    _games_cache[season] = games
    return games


def _compute_rolling_for_team(team_id: int, game_date: str, games: list[dict]) -> dict:
    gd = datetime.strptime(game_date, "%Y-%m-%d").date() if game_date else date.today()
    prior = []
    for g in games:
        if g.get("gameStateId") != 7:
            continue
        gt = g.get("gameType")
        if gt not in (2, 3):
            continue
        try:
            gd2 = datetime.strptime(g["gameDate"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            continue
        if gd2 >= gd:
            continue
        if g.get("homeTeamId") == team_id or g.get("visitingTeamId") == team_id:
            gf = g["homeScore"] if g["homeTeamId"] == team_id else g["visitingScore"]
            ga = g["visitingScore"] if g["homeTeamId"] == team_id else g["homeScore"]
            win = 1 if gf > ga else 0
            prior.append({"date": gd2, "gf": gf, "ga": ga, "win": win})

    prior.sort(key=lambda x: x["date"], reverse=True)

    if not prior:
        return {}

    result: dict = {}

    def _exp_weighted(values, decay):
        if not values:
            return 0
        n = len(values)
        weights = [decay ** i for i in range(n)]
        return sum(v * w for v, w in zip(values, weights)) / sum(weights)

    for stat, key in [("gf", "gf"), ("ga", "ga"), ("win", "win")]:
        vals = [r[stat] if stat != "win" else r["win"] for r in prior]

        for w in ROLLING_WINDOWS:
            window = vals[:w]
            result[f"{key}_roll{w}"] = sum(window) / len(window)

        for d in DECAY_FACTORS:
            label = str(d).replace(".", "")
            result[f"{key}_decay{label}"] = _exp_weighted(vals, d)

    result["rest_days"] = (gd - prior[0]["date"]).days

    return result


async def _predict_for_game(game_id: int, home_data: dict, away_data: dict,
                            season: str = "20242025", game_date: str | None = None):
    home_abbrev = home_data.get("abbrev", "")
    away_abbrev = away_data.get("abbrev", "")
    home_tid = home_data.get("id")
    away_tid = away_data.get("id")

    stats_map = await _get_team_stats_map(season)

    hs = dict(stats_map.get(home_tid, {}))
    aws = dict(stats_map.get(away_tid, {}))

    def _elo(s: dict) -> int:
        w = s.get("wins", 0)
        l = s.get("losses", 0)
        ot = s.get("ot_losses", 0)
        total = w + l + ot
        wp = w / total if total > 0 else 0.5
        return 1500 + int((wp - 0.5) * 200)

    home_elo = _elo(hs)
    away_elo = _elo(aws)

    if game_date and home_tid and away_tid:
        season_games = await _get_season_games(season)
        home_roll = _compute_rolling_for_team(home_tid, game_date, season_games)
        away_roll = _compute_rolling_for_team(away_tid, game_date, season_games)
        hs.update(home_roll)
        aws.update(away_roll)

        # back-to-back: check if team played previous day
        from datetime import datetime, timedelta
        from app.services.locations import travel_distance_miles, tz_crossed, altitude_advantage_ft, high_altitude_home
        gd_dt = datetime.strptime(game_date, "%Y-%m-%d") if game_date else datetime.today()
        prev = (gd_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        team_game_dates: dict[int, set] = {}
        for sg in season_games:
            for tid_ in [sg.get("homeTeamId"), sg.get("visitingTeamId")]:
                if tid_:
                    team_game_dates.setdefault(tid_, set()).add(sg.get("gameDate", ""))
        hs["b2b"] = 1 if prev in team_game_dates.get(home_tid, set()) else 0
        aws["b2b"] = 1 if prev in team_game_dates.get(away_tid, set()) else 0

        hs["travel_miles"] = travel_distance_miles(home_tid, away_tid)
        hs["tz_crossed"] = tz_crossed(home_tid, away_tid)
        hs["alt_advantage"] = altitude_advantage_ft(home_tid, away_tid)
        hs["high_alt_home"] = high_altitude_home(home_tid)

    result = predict_game(
        home_team=home_abbrev,
        away_team=away_abbrev,
        home_stats={**hs, "elo": home_elo},
        away_stats={**aws, "elo": away_elo},
    )
    return result


@router.get("/{game_id}")
async def get_prediction(game_id: int):
    data = await get_gamecenter_landing(game_id)
    if not data:
        return {"game_id": game_id, "error": "Game not found"}

    home = data.get("homeTeam", {})
    away = data.get("awayTeam", {})
    season = str(data.get("season", "20242025"))
    game_date = data.get("gameDate", "")

    result = await _predict_for_game(game_id, home, away, season, game_date)

    return {
        "game_id": game_id,
        "home_team": home.get("placeName", {}).get("default", ""),
        "away_team": away.get("placeName", {}).get("default", ""),
        "home_team_abbrev": home.get("abbrev", ""),
        "away_team_abbrev": away.get("abbrev", ""),
        "season": season,
        "game_state": data.get("gameState", ""),
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
        home = g.get("home_team", {})
        away = g.get("away_team", {})
        home_abbrev = home.get("abbrev", "")
        away_abbrev = away.get("abbrev", "")
        if not home_abbrev or not away_abbrev:
            continue

        season = str(g.get("season", "20242025"))
        home_data = {"abbrev": home_abbrev, "id": home.get("id", 0)}
        away_data = {"abbrev": away_abbrev, "id": away.get("id", 0)}
        game_date = g.get("game_date", "")

        result = await _predict_for_game(int(g["id"]), home_data, away_data, season, game_date)

        predictions.append({
            "game_id": g["id"],
            "home_team": home.get("place_name", ""),
            "away_team": away.get("place_name", ""),
            "home_team_abbrev": home_abbrev,
            "away_team_abbrev": away_abbrev,
            "game_date": game_date,
            "game_state": g.get("game_state"),
            "season": season,
            **result,
        })

    return {"predictions": predictions, "count": len(predictions)}
