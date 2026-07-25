from pydantic import BaseModel


class TeamInfo(BaseModel):
    id: int
    abbrev: str
    common_name: str
    place_name: str
    logo: str
    record: str | None = None


class Game(BaseModel):
    id: int
    season: int
    game_type: int
    game_date: str
    start_time_utc: str
    game_state: str
    venue: str
    home_team: TeamInfo
    away_team: TeamInfo
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    clock: dict | None = None


class ScoreboardResponse(BaseModel):
    prev_date: str | None = None
    current_date: str | None = None
    next_date: str | None = None
    games: list[Game]


class ClubScheduleResponse(BaseModel):
    team_abbrev: str
    season: int
    games: list[Game]