from pydantic import BaseModel


class LineupPlayer(BaseModel):
    id: int
    full_name: str
    first_name: str
    last_name: str
    position: str
    jersey_number: int | None = None


class GameTeam(BaseModel):
    id: int
    abbrev: str
    common_name: str
    place_name: str


class GameSummary(BaseModel):
    id: int
    game_date: str
    game_state: str
    venue: str
    home_team: GameTeam
    away_team: GameTeam


class LineupResponse(BaseModel):
    game: GameSummary
    home_lineup: list[LineupPlayer] | None = None
    away_lineup: list[LineupPlayer] | None = None