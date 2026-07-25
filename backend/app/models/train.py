import httpx
import asyncio
import logging
import joblib
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

STATS_API = "https://api.nhle.com/stats/rest/en"


async def _fetch(url: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"Fetch error for {url}: {e}")
        return None


async def build_team_map() -> dict[int, str]:
    data = await _fetch(f"{STATS_API}/team")
    mapping: dict[int, str] = {}
    if data and "data" in data:
        for t in data["data"]:
            if t.get("id") and t.get("triCode"):
                mapping[t["id"]] = t["triCode"]
    return mapping


async def fetch_games(season: str) -> list[dict]:
    data = await _fetch(f"{STATS_API}/game?cayenneExp=season={season}")
    return data.get("data", []) if data else []


async def build_training_data(seasons: list[str]) -> pd.DataFrame:
    rows = []
    for season in seasons:
        games = await fetch_games(season)
        logger.info(f"  Season {season}: {len(games)} games fetched")
        for g in games:
            if g.get("gameStateId") != 7:
                continue
            gt = g.get("gameType")
            if gt not in (2, 3):
                continue
            rows.append({
                "game_id": g["id"],
                "season": g["season"],
                "game_date": g["gameDate"],
                "game_type": gt,
                "home_team_id": g["homeTeamId"],
                "away_team_id": g["visitingTeamId"],
                "home_score": g["homeScore"],
                "away_score": g["visitingScore"],
                "home_win": 1 if g["homeScore"] > g["visitingScore"] else 0,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)
    logger.info(f"  Total games collected: {len(df)}")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    team_games: list[pd.DataFrame] = []
    for tid in pd.concat([df["home_team_id"], df["away_team_id"]]).unique():
        mask = (df["home_team_id"] == tid) | (df["away_team_id"] == tid)
        tg = df[mask].copy()
        tg = tg.sort_values("game_date")
        tg["is_home"] = (tg["home_team_id"] == tid).astype(int)
        tg["goals_for"] = np.where(tg["is_home"], tg["home_score"], tg["away_score"])
        tg["goals_against"] = np.where(tg["is_home"], tg["away_score"], tg["home_score"])
        tg["team_win"] = np.where(tg["is_home"], tg["home_win"], 1 - tg["home_win"])

        tg = tg.sort_values(["game_date", "game_id"])
        tg["gf_roll5"] = tg["goals_for"].rolling(5, min_periods=1).mean().shift(1)
        tg["ga_roll5"] = tg["goals_against"].rolling(5, min_periods=1).mean().shift(1)
        tg["win_roll5"] = tg["team_win"].rolling(5, min_periods=1).mean().shift(1)
        tg["rest_days"] = tg["game_date"].diff().dt.days.fillna(3)

        tg["team_id"] = tid
        team_games.append(
            tg[["game_id", "team_id", "is_home", "gf_roll5", "ga_roll5", "win_roll5", "rest_days"]]
        )

    if not team_games:
        return pd.DataFrame()

    all_team_stats = pd.concat(team_games, ignore_index=True)

    home_stats = all_team_stats[all_team_stats["is_home"] == 1].rename(
        columns={c: f"home_{c}" for c in ["gf_roll5", "ga_roll5", "win_roll5", "rest_days", "team_id"]}
    ).drop(columns=["is_home"])
    away_stats = all_team_stats[all_team_stats["is_home"] == 0].rename(
        columns={c: f"away_{c}" for c in ["gf_roll5", "ga_roll5", "win_roll5", "rest_days", "team_id"]}
    ).drop(columns=["is_home"])

    result = df.merge(home_stats, on="game_id", how="left").merge(
        away_stats, on="game_id", how="left"
    )

    fill_cols = [
        "home_gf_roll5", "home_ga_roll5", "home_win_roll5",
        "away_gf_roll5", "away_ga_roll5", "away_win_roll5",
        "home_rest_days", "away_rest_days",
    ]
    for c in fill_cols:
        if c in result.columns:
            result[c] = result[c].fillna(result[c].median())

    return result


def train_model(df: pd.DataFrame) -> tuple[Pipeline, float]:
    feature_cols = [
        "home_gf_roll5", "home_ga_roll5", "home_win_roll5",
        "away_gf_roll5", "away_ga_roll5", "away_win_roll5",
        "home_rest_days", "away_rest_days",
    ]
    available = [c for c in feature_cols if c in df.columns]
    df = df.dropna(subset=available + ["home_win"])

    X = df[available].values
    y = df["home_win"].values

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)),
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline.fit(X_train, y_train)

    test_acc = accuracy_score(y_test, pipeline.predict(X_test))
    test_auc = 0.0
    try:
        test_auc = roc_auc_score(y_test, pipeline.predict_proba(X_test)[:, 1])
    except Exception:
        pass

    logger.info(f"  Train size: {len(X_train)}, Test size: {len(X_test)}")
    logger.info(f"  Test accuracy: {test_acc:.4f}")
    logger.info(f"  Test AUC: {test_auc:.4f}")

    return pipeline, test_auc


def save_model(pipeline: Pipeline) -> Path:
    path = MODEL_DIR / "nhl_predictor.joblib"
    joblib.dump(pipeline, path)
    logger.info(f"Model saved to {path}")
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
        logger.error("No training data collected")
        return None

    logger.info("Engineering features...")
    df = engineer_features(df)
    if df.empty:
        logger.error("No features engineered")
        return None

    logger.info("Training model...")
    pipeline, auc = train_model(df)
    save_model(pipeline)
    logger.info(f"Model trained successfully (AUC={auc:.4f})")
    return pipeline


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(retrain())