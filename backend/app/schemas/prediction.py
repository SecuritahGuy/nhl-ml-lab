from pydantic import BaseModel


class PredictionInput(BaseModel):
    home_team_abbrev: str
    away_team_abbrev: str
    home_win_pct: float | None = None
    away_win_pct: float | None = None
    home_goals_for: float | None = None
    home_goals_against: float | None = None
    away_goals_for: float | None = None
    away_goals_against: float | None = None


class Prediction(BaseModel):
    game_id: int | None = None
    home_team: str
    away_team: str
    home_win_probability: float
    away_win_probability: float
    overtime_probability: float
    predicted_home_score: float
    predicted_away_score: float
    confidence: float
    model: str = "elo-simple"