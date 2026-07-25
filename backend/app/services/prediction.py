import math
import logging

logger = logging.getLogger(__name__)

ELO_HOME_ADVANTAGE = 55

_model_predict = None


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400))


def _score_probs(home_prob: float, away_prob: float) -> tuple[float, float, float, float]:
    expected_total = 5.8
    expected_spread = (home_prob - away_prob) * expected_total * 2

    home_score = max(0.0, round((expected_total + expected_spread) / 2, 2))
    away_score = max(0.0, round((expected_total - expected_spread) / 2, 2))

    spread = abs(home_score - away_score)
    ot_prob = round(0.28 if spread < 0.7 else 0.18 if spread < 1.2 else 0.10, 4)
    confidence = round(min(0.95, 0.50 + abs(home_prob - 0.5) * 1.5), 4)

    return home_score, away_score, ot_prob, confidence


def predict_game(
    home_team_stats: dict,
    away_team_stats: dict,
    home_recent: list[float],
    away_recent: list[float],
) -> dict:
    global _model_predict
    if _model_predict is None:
        from app.models.predictor import predict
        _model_predict = predict

    home_elo = home_team_stats.get("elo", 1500) + ELO_HOME_ADVANTAGE
    away_elo = away_team_stats.get("elo", 1500)
    elo_home_expected = _expected_score(home_elo, away_elo)
    elo_away_expected = 1.0 - elo_home_expected

    home_features = [
        float(sum(home_recent) / len(home_recent)) if home_recent else 3.0,
        home_team_stats.get("avgGoalsAgainst", 3.0),
        elo_home_expected,
        home_team_stats.get("rest_days", 3),
    ]
    away_features = [
        float(sum(away_recent) / len(away_recent)) if away_recent else 3.0,
        away_team_stats.get("avgGoalsAgainst", 3.0),
        elo_away_expected,
        away_team_stats.get("rest_days", 3),
    ]

    ml_prediction = _model_predict(home_features, away_features)
    if ml_prediction is not None:
        home_prob = ml_prediction["home_win_probability"]
        away_prob = ml_prediction["away_win_probability"]
        home_score, away_score, ot_prob, confidence = _score_probs(home_prob, away_prob)
        return {
            "home_win_probability": home_prob,
            "away_win_probability": away_prob,
            "overtime_probability": ot_prob,
            "predicted_home_score": home_score,
            "predicted_away_score": away_score,
            "confidence": confidence,
            "model": ml_prediction["model"],
        }

    home_score, away_score, ot_prob, confidence = _score_probs(elo_home_expected, elo_away_expected)
    return {
        "home_win_probability": round(elo_home_expected, 4),
        "away_win_probability": round(elo_away_expected, 4),
        "overtime_probability": ot_prob,
        "predicted_home_score": home_score,
        "predicted_away_score": away_score,
        "confidence": confidence,
        "model": "elo-simple",
    }