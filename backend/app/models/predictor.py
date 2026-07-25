import logging
import numpy as np
from pathlib import Path
import joblib

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
_model = None


def _init():
    global _model
    if _model is None:
        model_path = MODEL_DIR / "nhl_predictor.joblib"
        if model_path.exists():
            try:
                _model = joblib.load(model_path)
                logger.info("Model loaded from %s", model_path)
            except Exception as e:
                logger.error("Failed to load model: %s", e)
        else:
            logger.info("No model found at %s", model_path)


def predict(home_features: list[float], away_features: list[float]) -> dict | None:
    _init()
    if _model is None:
        logger.warning("Model not loaded, cannot predict")
        return None

    try:
        features = np.array([home_features + away_features]).reshape(1, -1)
        prob = _model.predict_proba(features)[0]
        home_prob = float(prob[1]) if len(prob) > 1 else float(prob[0])
        away_prob = 1.0 - home_prob

        return {
            "home_win_probability": round(home_prob, 4),
            "away_win_probability": round(away_prob, 4),
            "model": "logistic-regression",
        }
    except Exception as e:
        logger.warning("Model prediction failed: %s", e)
        return None


def predict_game(home_team: str, away_team: str,
                 home_stats: dict | None = None,
                 away_stats: dict | None = None,
                 home_recent: list[float] | None = None,
                 away_recent: list[float] | None = None) -> dict:
    from app.services.prediction import _expected_score, _score_probs

    hs = home_stats or {}
    aws = away_stats or {}
    hr = home_recent or [3.0] * 5
    ar = away_recent or [3.0] * 5

    ELO_HOME = 55
    home_elo = hs.get("elo", 1500) + ELO_HOME
    away_elo = aws.get("elo", 1500)
    elo_home = _expected_score(home_elo, away_elo)
    elo_away = 1.0 - elo_home

    features_h = [
        float(sum(hr) / len(hr)),
        hs.get("avgGoalsAgainst", 3.0),
        elo_home,
        hs.get("rest_days", 3),
    ]
    features_a = [
        float(sum(ar) / len(ar)),
        aws.get("avgGoalsAgainst", 3.0),
        elo_away,
        aws.get("rest_days", 3),
    ]

    ml = predict(features_h, features_a)
    if ml is not None:
        hp = ml["home_win_probability"]
        ap = ml["away_win_probability"]
        hs_, as_, ot, conf = _score_probs(hp, ap)
        return {
            "home_win_probability": hp, "away_win_probability": ap,
            "overtime_probability": ot,
            "predicted_home_score": hs_, "predicted_away_score": as_,
            "confidence": conf, "model": "logistic-regression",
        }

    hs_, as_, ot, conf = _score_probs(elo_home, elo_away)
    return {
        "home_win_probability": round(elo_home, 4),
        "away_win_probability": round(elo_away, 4),
        "overtime_probability": ot,
        "predicted_home_score": hs_, "predicted_away_score": as_,
        "confidence": conf, "model": "elo-simple",
    }