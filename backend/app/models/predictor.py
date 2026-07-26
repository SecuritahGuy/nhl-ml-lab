import logging
import json
import numpy as np
from pathlib import Path
import joblib

ROLLING_WINDOWS = [3, 5, 10, 20]
DECAY_FACTORS = [0.7, 0.8, 0.9]
ROLLING_SUFFIXES = (
    [f"gf_roll{w}" for w in ROLLING_WINDOWS]
    + [f"ga_roll{w}" for w in ROLLING_WINDOWS]
    + [f"win_roll{w}" for w in ROLLING_WINDOWS]
    + [f"gf_decay{str(d).replace('.', '')}" for d in DECAY_FACTORS]
    + [f"ga_decay{str(d).replace('.', '')}" for d in DECAY_FACTORS]
    + [f"win_decay{str(d).replace('.', '')}" for d in DECAY_FACTORS]
    + ["rest_days"]
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
_model = None
_model_type = "unknown"


def _init():
    global _model, _model_type
    if _model is None:
        model_path = MODEL_DIR / "nhl_predictor.joblib"
        if model_path.exists():
            try:
                _model = joblib.load(model_path)
                logger.info("Model loaded from %s", model_path)
                meta_path = MODEL_DIR / "model_meta.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        meta = json.load(f)
                    _model_type = meta.get("model_type", "unknown")
                else:
                    _model_type = "unknown"
            except Exception as e:
                logger.error("Failed to load model: %s", e)
        else:
            logger.info("No model found at %s", model_path)


def predict(features: list[float]) -> dict | None:
    _init()
    if _model is None:
        logger.warning("Model not loaded, cannot predict")
        return None

    try:
        X = np.array([features]).reshape(1, -1)
        prob = _model.predict_proba(X)[0]
        home_prob = float(prob[1]) if len(prob) > 1 else float(prob[0])
        away_prob = 1.0 - home_prob
        return {"home_win_probability": round(home_prob, 4), "away_win_probability": round(away_prob, 4)}
    except Exception as e:
        logger.warning("Model prediction failed: %s", e)
        return None


def _expected_score(rating_a: float, rating_b: float) -> float:
    import math
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


def _safe(s: dict, key: str, default: float) -> float:
    v = s.get(key)
    return float(v) if v is not None else default


def predict_game(home_team: str, away_team: str,
                 home_stats: dict | None = None,
                 away_stats: dict | None = None) -> dict:
    hs = home_stats or {}
    aws = away_stats or {}

    home_elo = _safe(hs, "elo", 1500) + 55
    away_elo = _safe(aws, "elo", 1500)
    elo_home = _expected_score(home_elo, away_elo)
    elo_away = 1.0 - elo_home

    # ---- extract base stats ----
    h_gf = _safe(hs, "gf_per_game", 3.0)
    h_ga = _safe(hs, "ga_per_game", 3.0)
    h_pp = _safe(hs, "pp_pct", 0.20)
    h_pk = _safe(hs, "pk_pct", 0.80)
    h_fo = _safe(hs, "fo_pct", 0.50)
    h_sf = _safe(hs, "sf_per_game", 30.0)
    h_sa = _safe(hs, "sa_per_game", 30.0)
    h_pt = _safe(hs, "point_pct", elo_home)

    a_gf = _safe(aws, "gf_per_game", 3.0)
    a_ga = _safe(aws, "ga_per_game", 3.0)
    a_pp = _safe(aws, "pp_pct", 0.20)
    a_pk = _safe(aws, "pk_pct", 0.80)
    a_fo = _safe(aws, "fo_pct", 0.50)
    a_sf = _safe(aws, "sf_per_game", 30.0)
    a_sa = _safe(aws, "sa_per_game", 30.0)
    a_pt = _safe(aws, "point_pct", elo_away)

    # win percentages
    def _wp(s):
        w = _safe(s, "wins", 0)
        l = _safe(s, "losses", 0)
        ot = _safe(s, "ot_losses", 0)
        t = w + l + ot
        return w / t if t > 0 else 0.5
    h_wp = _wp(hs)
    a_wp = _wp(aws)

    # ---- matchup differentials ----
    gf_diff = h_gf - a_ga
    ga_diff = h_ga - a_gf
    net_diff = (h_gf - h_ga) - (a_gf - a_ga)
    st_diff = h_pp - a_pk
    shot_diff = (h_sf - h_sa) - (a_sf - a_sa)
    denom_h = h_sf + h_sa
    denom_a = a_sf + a_sa
    corsi_diff = ((h_sf - h_sa) / denom_h if denom_h > 0 else 0) - (
        (a_sf - a_sa) / denom_a if denom_a > 0 else 0
    )
    fo_diff = h_fo - a_fo
    pp_diff = h_pp - a_pp
    pk_diff = h_pk - a_pk

    # ---- rolling features from stats dict (fall back to season averages) ----
    def _build_rolling(stats: dict, gf_fb: float, ga_fb: float, wp_fb: float) -> list[float]:
        out = []
        for sfx in ROLLING_SUFFIXES:
            if sfx == "rest_days":
                out.append(_safe(stats, sfx, 3))
                continue
            stat_type = sfx.split("_")[0]
            if stat_type == "gf":
                out.append(_safe(stats, sfx, gf_fb))
            elif stat_type == "ga":
                out.append(_safe(stats, sfx, ga_fb))
            else:
                out.append(_safe(stats, sfx, wp_fb))
        return out

    h_rolling = _build_rolling(hs, h_gf, h_ga, h_wp)
    a_rolling = _build_rolling(aws, a_gf, a_ga, a_wp)

    features = [h_gf, h_ga, h_pp, h_pk, h_fo, h_sf, h_sa, h_pt,
                a_gf, a_ga, a_pp, a_pk, a_fo, a_sf, a_sa, a_pt,
                h_wp, a_wp,
                gf_diff, ga_diff, net_diff, st_diff, shot_diff,
                corsi_diff, fo_diff, pp_diff, pk_diff] + h_rolling + a_rolling

    ml = predict(features)
    if ml is not None:
        hp = ml["home_win_probability"]
        ap = ml["away_win_probability"]
        hs_, as_, ot, conf = _score_probs(hp, ap)
        return {
            "home_win_probability": hp, "away_win_probability": ap,
            "overtime_probability": ot,
            "predicted_home_score": hs_, "predicted_away_score": as_,
            "confidence": conf, "model": _model_type,
        }

    hs_, as_, ot, conf = _score_probs(elo_home, elo_away)
    return {
        "home_win_probability": round(elo_home, 4),
        "away_win_probability": round(elo_away, 4),
        "overtime_probability": ot,
        "predicted_home_score": hs_, "predicted_away_score": as_,
        "confidence": conf, "model": "elo",
    }