from dataclasses import dataclass
from datetime import datetime


@dataclass
class Game:
    id: int
    date: datetime
    time: str
    status: str
    home_team_id: int
    away_team_id: int
    home_score: int | None = None
    away_score: int | None = None
    venue: str | None = None