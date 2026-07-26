import httpx
import asyncio
import logging
import joblib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss
import xgboost as xgb

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

STATS_API = "https://api.nhle.com/stats/rest/en"
WEB_API = "https://api-web.nhle.com/v1"

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


async def _fetch(url: str, client: httpx.AsyncClient | None = None) -> dict | None:
    async def _get(c: httpx.AsyncClient) -> dict | None:
        try:
            resp = await c.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Fetch error for {url}: {e}")
            return None
    if client:
        return await _get(client)
    async with httpx.AsyncClient(timeout=30.0) as c:
        return await _get(c)


async def fetch_games(season: str) -> list[dict]:
    data = await _fetch(f"{STATS_API}/game?cayenneExp=season={season}")
    return data.get("data", []) if data else []


async def fetch_team_stats(season: str) -> dict[str, dict]:
    data = await _fetch(
        f"{STATS_API}/team/summary?cayenneExp=seasonId={season}%20and%20gameTypeId=2&limit=100"
    )
    stats_map: dict[str, dict] = {}
    if data and "data" in data:
        for t in data["data"]:
            fields = {
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
            stats_map[str(t.get("teamId"))] = fields
    return stats_map


async def build_training_data(seasons: list[str]) -> pd.DataFrame:
    rows = []
    for season in seasons:
        games = await fetch_games(season)
        logger.info(f"  Season {season}: {len(games)} games fetched")
        ts = await fetch_team_stats(season)
        for g in games:
            if g.get("gameStateId") != 7:
                continue
            gt = g.get("gameType")
            if gt not in (2, 3):
                continue
            home_tid = str(g["homeTeamId"])
            away_tid = str(g["visitingTeamId"])
            row = {
                "game_id": g["id"],
                "season": g["season"],
                "game_date": g["gameDate"],
                "game_type": gt,
                "home_team_id": g["homeTeamId"],
                "away_team_id": g["visitingTeamId"],
                "home_score": g["homeScore"],
                "away_score": g["visitingScore"],
                "home_win": 1 if g["homeScore"] > g["visitingScore"] else 0,
            }
            hs = ts.get(home_tid, {})
            aws = ts.get(away_tid, {})
            for prefix, s in [("home", hs), ("away", aws)]:
                for k in ["gf_per_game", "ga_per_game", "pp_pct", "pk_pct", "fo_pct",
                          "sf_per_game", "sa_per_game", "point_pct",
                          "wins", "losses", "ot_losses", "goals_for", "goals_against"]:
                    if prefix == "home":
                        default = 3.0 if "gf" in k or "ga" in k or "sf" in k or "sa" in k else 0.20 if "pct" in k else 0.5 if "point" in k else 0
                        row[f"home_{k}"] = s.get(k, default)
                    else:
                        default = 3.0 if "gf" in k or "ga" in k or "sf" in k or "sa" in k else 0.20 if "pct" in k else 0.5 if "point" in k else 0
                        row[f"away_{k}"] = s.get(k, default)

            home_w = hs.get("wins", 0)
            home_l = hs.get("losses", 0)
            home_otl = hs.get("ot_losses", 0)
            home_total = home_w + home_l + home_otl
            away_w = aws.get("wins", 0)
            away_l = aws.get("losses", 0)
            away_otl = aws.get("ot_losses", 0)
            away_total = away_w + away_l + away_otl

            home_gf = hs.get("goals_for", 0)
            home_ga = hs.get("goals_against", 0)
            home_games = hs.get("wins", 0) + hs.get("losses", 0) + hs.get("ot_losses", 0)
            home_avg_gf = home_gf / home_games if home_games > 0 else 3.0
            home_avg_ga = home_ga / home_games if home_games > 0 else 3.0

            away_gf = aws.get("goals_for", 0)
            away_ga = aws.get("goals_against", 0)
            away_games = aws.get("wins", 0) + aws.get("losses", 0) + aws.get("ot_losses", 0)
            away_avg_gf = away_gf / away_games if away_games > 0 else 3.0
            away_avg_ga = away_ga / away_games if away_games > 0 else 3.0

            home_win_pct = home_w / home_total if home_total > 0 else 0.5
            away_win_pct = away_w / away_total if away_total > 0 else 0.5

            row["home_win_pct"] = home_win_pct
            row["away_win_pct"] = away_win_pct
            row["gf_diff"] = home_avg_gf - away_avg_ga
            row["ga_diff"] = home_avg_ga - away_avg_gf
            row["net_diff"] = (home_avg_gf - home_avg_ga) - (away_avg_gf - away_avg_ga)
            row["st_diff"] = hs.get("pp_pct", 0.20) - aws.get("pk_pct", 0.80)
            row["shot_diff"] = (hs.get("sf_per_game", 30) - hs.get("sa_per_game", 30)) - (aws.get("sf_per_game", 30) - aws.get("sa_per_game", 30))
            home_corsi = (hs.get("sf_per_game", 30) - hs.get("sa_per_game", 30)) / (hs.get("sf_per_game", 30) + hs.get("sa_per_game", 30)) if (hs.get("sf_per_game", 30) + hs.get("sa_per_game", 30)) > 0 else 0
            away_corsi = (aws.get("sf_per_game", 30) - aws.get("sa_per_game", 30)) / (aws.get("sf_per_game", 30) + aws.get("sa_per_game", 30)) if (aws.get("sf_per_game", 30) + aws.get("sa_per_game", 30)) > 0 else 0
            row["corsi_diff"] = home_corsi - away_corsi
            row["fo_diff"] = hs.get("fo_pct", 0.50) - aws.get("fo_pct", 0.50)
            row["pp_diff"] = hs.get("pp_pct", 0.20) - aws.get("pp_pct", 0.20)
            row["pk_diff"] = hs.get("pk_pct", 0.80) - aws.get("pk_pct", 0.80)

            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Game context features
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    from app.services.locations import travel_distance_miles, tz_crossed, altitude_advantage_ft, high_altitude_home

    df["travel_miles"] = df.apply(lambda r: travel_distance_miles(int(r["home_team_id"]), int(r["away_team_id"])), axis=1)
    df["tz_crossed"] = df.apply(lambda r: tz_crossed(int(r["home_team_id"]), int(r["away_team_id"])), axis=1)
    df["alt_advantage"] = df.apply(lambda r: altitude_advantage_ft(int(r["home_team_id"]), int(r["away_team_id"])), axis=1)
    df["high_alt_home"] = df.apply(lambda r: high_altitude_home(int(r["home_team_id"])), axis=1)

    # Back-to-back: check if each team played the previous day
    team_dates: dict[int, set] = {}
    for _, r in df.iterrows():
        for tid in [int(r["home_team_id"]), int(r["away_team_id"])]:
            if tid not in team_dates:
                team_dates[tid] = set()
            team_dates[tid].add(r["game_date"].strftime("%Y-%m-%d"))

    home_b2b, away_b2b = [], []
    from datetime import timedelta
    for _, r in df.iterrows():
        prev = (r["game_date"] - timedelta(days=1)).strftime("%Y-%m-%d")
        home_b2b.append(1 if prev in team_dates.get(int(r["home_team_id"]), set()) else 0)
        away_b2b.append(1 if prev in team_dates.get(int(r["away_team_id"]), set()) else 0)
    df["home_b2b"] = home_b2b
    df["away_b2b"] = away_b2b

    logger.info(f"  Total games: {len(df)}")
    return df


def _exp_weighted_rolling(series: pd.Series, decay: float, max_window: int = 20) -> pd.Series:
    def _ewm(x):
        n = len(x)
        if n == 0:
            return np.nan
        weights = np.array([decay ** i for i in range(n)])
        return np.average(x, weights=weights)
    return series.rolling(max_window, min_periods=1).apply(_ewm, raw=True)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "home_gf_per_game", "home_ga_per_game", "home_pp_pct", "home_pk_pct",
        "home_fo_pct", "home_sf_per_game", "home_sa_per_game", "home_point_pct",
        "away_gf_per_game", "away_ga_per_game", "away_pp_pct", "away_pk_pct",
        "away_fo_pct", "away_sf_per_game", "away_sa_per_game", "away_point_pct",
        "home_win_pct", "away_win_pct",
        "gf_diff", "ga_diff", "net_diff", "st_diff", "shot_diff",
        "corsi_diff", "fo_diff", "pp_diff", "pk_diff",
        "home_b2b", "away_b2b", "travel_miles", "tz_crossed", "alt_advantage", "high_alt_home",
        "game_id", "game_date", "home_team_id", "away_team_id",
        "home_score", "away_score", "home_win", "season", "game_type",
    ]
    present = [c for c in base_cols if c in df.columns]

    team_games: list[pd.DataFrame] = []
    for tid in pd.concat([df["home_team_id"], df["away_team_id"]]).unique():
        mask = (df["home_team_id"] == tid) | (df["away_team_id"] == tid)
        tg = df[mask].copy().sort_values("game_date")
        tg["is_home"] = (tg["home_team_id"] == tid).astype(int)
        tg["goals_for"] = np.where(tg["is_home"], tg["home_score"], tg["away_score"])
        tg["goals_against"] = np.where(tg["is_home"], tg["away_score"], tg["home_score"])
        tg["team_win"] = np.where(tg["is_home"], tg["home_win"], 1 - tg["home_win"])

        # simple rolling averages
        for w in ROLLING_WINDOWS:
            tg[f"gf_roll{w}"] = tg["goals_for"].rolling(w, min_periods=1).mean().shift(1)
            tg[f"ga_roll{w}"] = tg["goals_against"].rolling(w, min_periods=1).mean().shift(1)
            tg[f"win_roll{w}"] = tg["team_win"].rolling(w, min_periods=1).mean().shift(1)

        # exponential decay rolling
        for d in DECAY_FACTORS:
            label = str(d).replace(".", "")
            tg[f"gf_decay{label}"] = _exp_weighted_rolling(tg["goals_for"], d).shift(1)
            tg[f"ga_decay{label}"] = _exp_weighted_rolling(tg["goals_against"], d).shift(1)
            tg[f"win_decay{label}"] = _exp_weighted_rolling(tg["team_win"], d).shift(1)

        tg["rest_days"] = tg["game_date"].diff().dt.days.fillna(3)
        tg["team_id"] = tid

        cols = ["game_id", "team_id", "is_home"] + ROLLING_SUFFIXES
        team_games.append(tg[cols])

    all_team_stats = pd.concat(team_games, ignore_index=True)

    home_roll = all_team_stats[all_team_stats["is_home"] == 1].drop(columns=["is_home", "team_id"])
    away_roll = all_team_stats[all_team_stats["is_home"] == 0].drop(columns=["is_home", "team_id"])
    for suffix in ROLLING_SUFFIXES:
        home_roll = home_roll.rename(columns={suffix: f"home_{suffix}"})
        away_roll = away_roll.rename(columns={suffix: f"away_{suffix}"})

    result = df[present].merge(home_roll, on="game_id", how="left").merge(
        away_roll, on="game_id", how="left"
    )

    # fill missing rolling values with season averages
    for side in ["home", "away"]:
        for sfx in ROLLING_SUFFIXES:
            col = f"{side}_{sfx}"
            if sfx == "rest_days":
                result[col] = result.get(col, 3).fillna(3)
                continue
            if col not in result.columns:
                result[col] = 0
                continue
            stat_type = sfx.split("_")[0]
            if stat_type == "gf":
                fallback = result.get(f"{side}_gf_per_game", 3.0)
            elif stat_type == "ga":
                fallback = result.get(f"{side}_ga_per_game", 3.0)
            elif stat_type == "win":
                fallback = result.get(f"{side}_win_pct", 0.5)
            else:
                fallback = 0
            result[col] = result[col].fillna(fallback)

    return result


def _make_features(df: pd.DataFrame) -> list[str]:
    fts = [
        "home_gf_per_game", "home_ga_per_game", "home_pp_pct", "home_pk_pct",
        "home_fo_pct", "home_sf_per_game", "home_sa_per_game", "home_point_pct",
        "away_gf_per_game", "away_ga_per_game", "away_pp_pct", "away_pk_pct",
        "away_fo_pct", "away_sf_per_game", "away_sa_per_game", "away_point_pct",
        "home_win_pct", "away_win_pct",
        "gf_diff", "ga_diff", "net_diff", "st_diff", "shot_diff",
        "corsi_diff", "fo_diff", "pp_diff", "pk_diff",
        "home_b2b", "away_b2b",
        "travel_miles", "tz_crossed", "alt_advantage", "high_alt_home",
    ]
    for side in ["home", "away"]:
        for sfx in ROLLING_SUFFIXES:
            fts.append(f"{side}_{sfx}")
    return fts


def train_and_evaluate(df: pd.DataFrame) -> tuple[Pipeline, str, float]:
    feature_cols = _make_features(df)
    available = [c for c in feature_cols if c in df.columns]
    df = df.dropna(subset=available + ["home_win"])
    X = df[available].values
    y = df["home_win"].values

    logger.info(f"Features ({len(available)}): {available}")
    logger.info(f"Samples: {len(X)}, Home win rate: {y.mean():.3f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    results = {}

    # ---- LogisticRegression ----
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)),
    ])
    lr_pipe.fit(X_train, y_train)
    lr_acc = accuracy_score(y_test, lr_pipe.predict(X_test))
    lr_auc = roc_auc_score(y_test, lr_pipe.predict_proba(X_test)[:, 1])
    lr_brier = brier_score_loss(y_test, lr_pipe.predict_proba(X_test)[:, 1])
    cv_scores = cross_val_score(lr_pipe, X_train, y_train, cv=StratifiedKFold(5), scoring="roc_auc")
    results["LogisticRegression"] = {
        "test_acc": lr_acc, "test_auc": lr_auc, "test_brier": lr_brier,
        "cv_auc_mean": cv_scores.mean(), "cv_auc_std": cv_scores.std(),
    }
    logger.info(f"  LogisticRegression: test_acc={lr_acc:.4f}, test_auc={lr_auc:.4f}, cv_auc={cv_scores.mean():.4f}±{cv_scores.std():.4f}")

    # ---- XGBoost ----
    scale_pos_weight = (len(y_train) - y_train.sum()) / y_train.sum() if y_train.sum() > 0 else 1.0
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
    )
    xgb_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", xgb_model),
    ])
    xgb_pipe.fit(X_train, y_train)
    xgb_acc = accuracy_score(y_test, xgb_pipe.predict(X_test))
    xgb_auc = roc_auc_score(y_test, xgb_pipe.predict_proba(X_test)[:, 1])
    xgb_brier = brier_score_loss(y_test, xgb_pipe.predict_proba(X_test)[:, 1])
    cv_scores_xgb = cross_val_score(xgb_pipe, X_train, y_train, cv=StratifiedKFold(5), scoring="roc_auc")
    results["XGBoost"] = {
        "test_acc": xgb_acc, "test_auc": xgb_auc, "test_brier": xgb_brier,
        "cv_auc_mean": cv_scores_xgb.mean(), "cv_auc_std": cv_scores_xgb.std(),
    }
    logger.info(f"  XGBoost: test_acc={xgb_acc:.4f}, test_auc={xgb_auc:.4f}, cv_auc={cv_scores_xgb.mean():.4f}±{cv_scores_xgb.std():.4f}")

    # Pick the best model by test AUC
    best_name = max(results, key=lambda n: results[n]["test_auc"])
    best_pipe = lr_pipe if best_name == "LogisticRegression" else xgb_pipe
    logger.info(f"  Best model: {best_name} (AUC={results[best_name]['test_auc']:.4f})")

    if best_name == "XGBoost":
        fi = best_pipe.named_steps["clf"].feature_importances_
        for name, imp in sorted(zip(available, fi), key=lambda x: -x[1])[:10]:
            logger.info(f"    {name}: {imp:.4f}")

    return best_pipe, best_name, results[best_name]["test_auc"]


def save_model(pipeline: Pipeline, name: str) -> Path:
    path = MODEL_DIR / "nhl_predictor.joblib"
    joblib.dump(pipeline, path)
    meta = {"model_type": name}
    meta_path = MODEL_DIR / "model_meta.json"
    import json
    with open(meta_path, "w") as f:
        json.dump(meta, f)
    logger.info(f"Model saved to {path} (type={name})")
    return path


def load_model() -> Pipeline | None:
    path = MODEL_DIR / "nhl_predictor.joblib"
    if path.exists():
        return joblib.load(path)
    return None


async def retrain() -> Pipeline | None:
    seasons = [f"{y}{y+1}" for y in range(2019, 2025)]
    logger.info(f"Training on seasons: {seasons}")
    df = await build_training_data(seasons)
    if df.empty:
        logger.error("No training data")
        return None

    logger.info("Engineering features...")
    df = engineer_features(df)
    if df.empty:
        logger.error("No features engineered")
        return None

    logger.info("Training models...")
    pipeline, name, auc = train_and_evaluate(df)
    save_model(pipeline, name)
    logger.info(f"Done. Best model={name}, AUC={auc:.4f}")
    return pipeline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(retrain())