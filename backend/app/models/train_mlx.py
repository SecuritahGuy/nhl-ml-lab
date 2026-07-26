import asyncio
import logging
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten, tree_unflatten

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.models.train import (
    build_training_data, engineer_features,
    _make_features,
)

ALL_TEAM_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15,
                16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28,
                29, 30, 52, 54, 55, 59]
TEAM_ID_TO_IDX = {tid: i for i, tid in enumerate(ALL_TEAM_IDS)}
N_TEAMS = len(ALL_TEAM_IDS)
EMBED_DIM = 8


class MLXLogisticRegression(nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.linear = nn.Linear(n_features, 1)

    def __call__(self, x: mx.array) -> mx.array:
        return mx.sigmoid(self.linear(x)).squeeze()


class MLPClassifier(nn.Module):
    def __init__(self, n_features: int, hidden_dims: list[int], dropout: float = 0.0):
        super().__init__()
        layers = []
        prev = n_features
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def __call__(self, x: mx.array) -> mx.array:
        return mx.sigmoid(self.net(x)).squeeze()


class MLXEmbeddingLR(nn.Module):
    def __init__(self, n_features: int, n_teams: int, embed_dim: int):
        super().__init__()
        self.embedding = nn.Embedding(n_teams, embed_dim)
        self.linear = nn.Linear(n_features + 2 * embed_dim, 1)

    def __call__(self, features: mx.array, home_team: mx.array, away_team: mx.array) -> mx.array:
        h_emb = self.embedding(home_team)
        a_emb = self.embedding(away_team)
        x = mx.concatenate([features, h_emb, a_emb], axis=-1)
        return mx.sigmoid(self.linear(x)).squeeze()


class MLXEmbeddingMLP(nn.Module):
    def __init__(self, n_features: int, n_teams: int, embed_dim: int,
                 hidden_dims: list[int], dropout: float = 0.0):
        super().__init__()
        self.embedding = nn.Embedding(n_teams, embed_dim)
        layers = []
        prev = n_features + 2 * embed_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def __call__(self, features: mx.array, home_team: mx.array, away_team: mx.array) -> mx.array:
        h_emb = self.embedding(home_team)
        a_emb = self.embedding(away_team)
        x = mx.concatenate([features, h_emb, a_emb], axis=-1)
        return mx.sigmoid(self.net(x)).squeeze()


def prepare_data(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str], StandardScaler]:
    feature_cols = _make_features(df)
    available = [c for c in feature_cols if c in df.columns]
    df = df.dropna(subset=available + ["home_win"])
    X = df[available].values.astype(np.float32)
    y = df["home_win"].values.astype(np.float32)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logger.info(f"Data: {len(X)} samples, {len(available)} features, home_win_rate={y.mean():.3f}")
    return X_scaled, y, available, scaler


def prepare_data_with_teams(df: pd.DataFrame, scaler: StandardScaler | None = None
                            ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], StandardScaler]:
    feature_cols = _make_features(df)
    available = [c for c in feature_cols if c in df.columns]
    df = df.dropna(subset=available + ["home_win"])
    X = df[available].values.astype(np.float32)
    y = df["home_win"].values.astype(np.float32)
    if scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    else:
        X_scaled = scaler.transform(X)
    home_idx = np.array([TEAM_ID_TO_IDX.get(int(tid), 0) for tid in df["home_team_id"]], dtype=np.int32)
    away_idx = np.array([TEAM_ID_TO_IDX.get(int(tid), 0) for tid in df["away_team_id"]], dtype=np.int32)
    logger.info(f"Data: {len(X)} samples, {len(available)} features, {N_TEAMS} teams, embed_dim={EMBED_DIM}")
    return X_scaled, home_idx, away_idx, y, available, scaler


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, (y_prob >= 0.5).astype(int))),
        "auc": float(roc_auc_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
    }


def get_logits_fn(model) -> Callable:
    if isinstance(model, (MLXEmbeddingLR, MLXEmbeddingMLP)):
        def fn(m, X, h, a):
            return m.net(m.embedding(h) | m.embedding(a) | X) if isinstance(m, MLXEmbeddingMLP) else m.linear(
                mx.concatenate([X, m.embedding(h), m.embedding(a)], axis=-1)
            )
        return fn
    elif isinstance(model, MLPClassifier):
        return lambda m, X, *_: m.net(X)
    else:
        return lambda m, X, *_: m.linear(X)


def train_mlx_model(
    model: nn.Module,
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    lr: float = 1e-3,
    epochs: int = 500,
    batch_size: int = 64,
    patience: int = 30,
    l2_lambda: float = 1e-5,
    home_train: np.ndarray | None = None,
    away_train: np.ndarray | None = None,
    home_val: np.ndarray | None = None,
    away_val: np.ndarray | None = None,
) -> tuple[nn.Module, dict, int]:
    mx.eval(model.parameters())
    has_embeddings = home_train is not None and away_train is not None

    def _loss_fn(model: nn.Module, *args) -> mx.array:
        Xb = args[0]
        yb = args[-1]
        if has_embeddings:
            hb, ab = args[1], args[2]
            h_emb = model.embedding(hb)
            a_emb = model.embedding(ab)
            inp = mx.concatenate([Xb, h_emb, a_emb], axis=-1)
            logits = model.net(inp) if isinstance(model, MLXEmbeddingMLP) else model.linear(inp)
        else:
            logits = model.net(Xb) if isinstance(model, MLPClassifier) else model.linear(Xb)
        loss = nn.losses.binary_cross_entropy(logits.squeeze(), yb, reduction="mean")
        if l2_lambda > 0:
            flat = tree_flatten(model.parameters())
            l2 = sum((v * v).sum() for _, v in flat) * l2_lambda
            loss = loss + l2
        return loss

    loss_and_grad_fn = nn.value_and_grad(model, _loss_fn)
    n_train = len(X_train)
    steps_per_epoch = max(1, n_train // batch_size)
    scheduler = optim.cosine_decay(lr, epochs * steps_per_epoch)
    optimizer = optim.AdamW(learning_rate=scheduler, betas=[0.9, 0.999])

    best_val_loss = float("inf")
    best_params = None
    best_epoch = 0

    for epoch in range(epochs):
        perm = np.random.permutation(n_train)
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, n_train, batch_size):
            idx = perm[start:start + batch_size]
            Xb = mx.array(X_train[idx])
            yb = mx.array(y_train[idx])
            if has_embeddings:
                hb = mx.array(home_train[idx])
                ab = mx.array(away_train[idx])
                loss_val, grads = loss_and_grad_fn(model, Xb, hb, ab, yb)
            else:
                loss_val, grads = loss_and_grad_fn(model, Xb, yb)
            optimizer.update(model, grads)
            mx.eval(model.parameters(), optimizer.state)
            epoch_loss += loss_val.item()
            n_batches += 1

        # Validation
        Xv = mx.array(X_val)
        yv = mx.array(y_val)
        if has_embeddings:
            hv = mx.array(home_val)
            av = mx.array(away_val)
            h_emb = model.embedding(hv)
            a_emb = model.embedding(av)
            inp = mx.concatenate([Xv, h_emb, a_emb], axis=-1)
            val_logits = model.net(inp) if isinstance(model, MLXEmbeddingMLP) else model.linear(inp)
        else:
            val_logits = model.net(Xv) if isinstance(model, MLPClassifier) else model.linear(Xv)
        val_loss = nn.losses.binary_cross_entropy(val_logits.squeeze(), yv, reduction="mean").item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_params = tree_flatten(model.parameters())
            best_epoch = epoch

        if epoch % 50 == 0 or epoch == epochs - 1 or epoch - best_epoch == 0:
            train_loss = epoch_loss / max(n_batches, 1)
            logger.info(f"  Epoch {epoch:3d} | train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | best_val={best_val_loss:.4f} @ epoch {best_epoch}")

        if epoch - best_epoch > patience:
            logger.info(f"  Early stopping at epoch {epoch}")
            break

    if best_params:
        model.update(tree_unflatten(best_params))
        mx.eval(model.parameters())

    # Final validation metrics
    if has_embeddings:
        Xv = mx.array(X_val)
        hv = mx.array(home_val)
        av = mx.array(away_val)
        y_val_prob = np.array(model(Xv, hv, av))
    else:
        y_val_prob = np.array(model(Xv))
    val_metrics = compute_metrics(y_val, y_val_prob)
    logger.info(f"  Validation: acc={val_metrics['accuracy']:.4f} auc={val_metrics['auc']:.4f} brier={val_metrics['brier']:.4f}")

    return model, val_metrics, best_epoch


def export_mlx_weights(model: nn.Module, scaler: StandardScaler, feature_names: list[str],
                       metrics: dict, model_name: str, out_path: Path,
                       team_id_to_idx: dict | None = None):
    flat = tree_flatten(model.parameters())
    params = {}
    for key, val in flat:
        params[key] = np.asarray(val).tolist()
    logger.info(f"Exported params keys: {list(params.keys())}")

    export = {
        "model_type": model_name,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "feature_names": feature_names,
        "params": params,
        "metrics": metrics,
    }
    if team_id_to_idx:
        export["team_id_to_idx"] = team_id_to_idx
        export["embed_dim"] = EMBED_DIM
        export["n_teams"] = N_TEAMS
    with open(out_path, "w") as f:
        json.dump(export, f, indent=2)
    logger.info(f"Exported {model_name} weights to {out_path}")


def export_to_typescript(export_path: Path, ts_path: Path):
    with open(export_path) as f:
        data = json.load(f)

    model_type = data["model_type"]
    scaler_mean = data["scaler_mean"]
    scaler_scale = data["scaler_scale"]
    params = data["params"]

    if "ensemble" in model_type:
        coefs = []
        biases = []
        for i in range(5):
            w = params.get(f"model{i}_linear.weight", [])
            b = params.get(f"model{i}_linear.bias", [0])
            coefs.append(w[0] if w and isinstance(w[0], list) else w)
            biases.append(b[0] if isinstance(b, list) and len(b) > 0 else (b if isinstance(b, (int, float)) else 0))
        ts = f"""export const MODEL_PARAMS = {{
  type: "{model_type}",
  scaler_mean: {json.dumps(scaler_mean)},
  scaler_scale: {json.dumps(scaler_scale)},
  ensemble_coefs: {json.dumps(coefs)},
  ensemble_biases: {json.dumps(biases)},
}};
"""
    elif model_type.lower().startswith("mlx_lr"):
        coef = params.get("linear.weight", params.get("weight", []))
        bias = params.get("linear.bias", params.get("bias", [0]))
        coef_flat = coef[0] if coef and isinstance(coef[0], list) else coef
        intercept_val = bias[0] if isinstance(bias, list) and len(bias) > 0 else (bias if isinstance(bias, (int, float)) else 0)
        ts = f"""export const MODEL_PARAMS = {{
  type: "{model_type}",
  scaler_mean: {json.dumps(scaler_mean)},
  scaler_scale: {json.dumps(scaler_scale)},
  coef: {json.dumps(coef_flat)},
  intercept: {intercept_val},
}};
"""
    elif "embedding" in model_type:
        team_id_to_idx = data.get("team_id_to_idx", {})
        embed_dim = data.get("embed_dim", 8)
        ts = f"""export const MODEL_PARAMS = {{
  type: "{model_type}",
  scaler_mean: {json.dumps(scaler_mean)},
  scaler_scale: {json.dumps(scaler_scale)},
  params: {json.dumps(params)},
  team_id_to_idx: {json.dumps(team_id_to_idx)},
  embed_dim: {embed_dim},
}};
"""
    elif model_type.startswith("mlp"):
        ts = f"""export const MODEL_PARAMS = {{
  type: "{model_type}",
  scaler_mean: {json.dumps(scaler_mean)},
  scaler_scale: {json.dumps(scaler_scale)},
  params: {json.dumps(params)},
}};
"""
    else:
        ts = ""
        logger.warning(f"Unknown model type: {model_type}")

    with open(ts_path, "w") as f:
        f.write(ts)
    logger.info(f"TypeScript export written to {ts_path}")


def train_sklearn_baseline(X_train, y_train, X_test, y_test) -> dict:
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)),
    ])
    pipe.fit(X_train, y_train)
    y_prob = pipe.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, (y_prob >= 0.5).astype(int))
    auc = roc_auc_score(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)
    cv = StratifiedKFold(5)
    cv_scores = []
    for train_idx, val_idx in cv.split(X_train, y_train):
        X_cv_train, X_cv_val = X_train[train_idx], X_train[val_idx]
        y_cv_train, y_cv_val = y_train[train_idx], y_train[val_idx]
        cv_pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)),
        ])
        cv_pipe.fit(X_cv_train, y_cv_train)
        cv_scores.append(roc_auc_score(y_cv_val, cv_pipe.predict_proba(X_cv_val)[:, 1]))
    cv_mean = float(np.mean(cv_scores))
    cv_std = float(np.std(cv_scores))
    logger.info(f"  sklearn LR: acc={acc:.4f} auc={auc:.4f} brier={brier:.4f} cv_auc={cv_mean:.4f}+-{cv_std:.4f}")
    return {"accuracy": acc, "auc": auc, "brier": brier, "cv_auc_mean": cv_mean, "cv_auc_std": cv_std}


async def main():
    import time
    seasons = [f"{y}{y+1}" for y in range(2021, 2026)]
    logger.info(f"Fetching data for seasons: {seasons}")
    start = time.time()

    df = await build_training_data(seasons)
    logger.info(f"Fetched {len(df)} games in {time.time()-start:.1f}s")

    logger.info("Engineering features...")
    df = engineer_features(df)
    X_scaled, y, feature_names, scaler = prepare_data(df)

    X_scaled_t, home_idx, away_idx, y_t, feature_names_t, scaler_t = prepare_data_with_teams(df)
    logger.info(f"Feature engineering done in {time.time()-start:.1f}s")

    # Split (features only)
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42
    )

    # Split (with teams)
    X_train_t, X_test_t, home_train, home_test, away_train, away_test, y_train_t, y_test_t = train_test_split(
        X_scaled_t, home_idx, away_idx, y_t, test_size=0.2, random_state=42
    )

    # 1. sklearn baseline (features only)
    logger.info("\n=== sklearn LogisticRegression (baseline) ===")
    sklearn_metrics = train_sklearn_baseline(X_train, y_train, X_test, y_test)

    # 2. MLX LR (features only)
    logger.info("\n=== MLX LR (no embeddings) ===")
    lr_model = MLXLogisticRegression(X_scaled.shape[1])
    mx.eval(lr_model.parameters())
    lr_model, lr_val, lr_epochs = train_mlx_model(
        lr_model, X_train, y_train, X_test, y_test,
        lr=5e-3, epochs=300, batch_size=128, patience=30,
    )
    lr_test_prob = np.array(lr_model(mx.array(X_test)))
    lr_metrics = compute_metrics(y_test, lr_test_prob)
    logger.info(f"  MLX LR test: acc={lr_metrics['accuracy']:.4f} auc={lr_metrics['auc']:.4f}")

    # 3. MLX LR + Team Embeddings
    logger.info(f"\n=== MLX LR + Team Embeddings (dim={EMBED_DIM}) ===")
    emb_lr = MLXEmbeddingLR(X_scaled_t.shape[1], N_TEAMS, EMBED_DIM)
    mx.eval(emb_lr.parameters())
    emb_lr, emb_lr_val, emb_lr_epochs = train_mlx_model(
        emb_lr, X_train_t, y_train_t, X_test_t, y_test_t,
        lr=5e-3, epochs=300, batch_size=128, patience=30, l2_lambda=1e-5,
        home_train=home_train, away_train=away_train,
        home_val=home_test, away_val=away_test,
    )
    emb_lr_prob = np.array(emb_lr(mx.array(X_test_t), mx.array(home_test), mx.array(away_test)))
    emb_lr_metrics = compute_metrics(y_test_t, emb_lr_prob)
    logger.info(f"  LR+Emb test: acc={emb_lr_metrics['accuracy']:.4f} auc={emb_lr_metrics['auc']:.4f}")

    # 4. MLP Small + Team Embeddings
    logger.info(f"\n=== MLP Small + Team Embeddings (dim={EMBED_DIM}) ===")
    emb_mlp = MLXEmbeddingMLP(X_scaled_t.shape[1], N_TEAMS, EMBED_DIM, [32], dropout=0.15)
    mx.eval(emb_mlp.parameters())
    emb_mlp, emb_mlp_val, emb_mlp_epochs = train_mlx_model(
        emb_mlp, X_train_t, y_train_t, X_test_t, y_test_t,
        lr=3e-3, epochs=400, batch_size=64, patience=40, l2_lambda=1e-5,
        home_train=home_train, away_train=away_train,
        home_val=home_test, away_val=away_test,
    )
    emb_mlp_prob = np.array(emb_mlp(mx.array(X_test_t), mx.array(home_test), mx.array(away_test)))
    emb_mlp_metrics = compute_metrics(y_test_t, emb_mlp_prob)
    logger.info(f"  MLP+Emb test: acc={emb_mlp_metrics['accuracy']:.4f} auc={emb_mlp_metrics['auc']:.4f}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("MODEL COMPARISON")
    logger.info("=" * 70)
    all_results = {
        "sklearn_LR": sklearn_metrics,
        "MLX_LR": {**lr_metrics, "val": lr_val, "epochs": lr_epochs},
        "LR+Embedding": {**emb_lr_metrics, "val": emb_lr_val, "epochs": emb_lr_epochs},
        "MLP+Embedding": {**emb_mlp_metrics, "val": emb_mlp_val, "epochs": emb_mlp_epochs},
    }
    for name, m in all_results.items():
        val_info = m.get("val", {})
        logger.info(f"  {name:15s} | test_acc={m['accuracy']:.4f} test_auc={m['auc']:.4f} | val_auc={val_info.get('auc', 0):.4f}")

    best_name = max(all_results, key=lambda n: all_results[n]["auc"])
    best_data = all_results[best_name]
    logger.info(f"\nBest model: {best_name} (AUC={best_data['auc']:.4f})")

    # 5. Ensemble: train 5 MLX LRs with different seeds
    logger.info("\n=== MLX LR Ensemble (5 models) ===")
    n_ensemble = 5
    ensemble_models: list[nn.Module] = []
    ensemble_metrics_list: list[dict] = []
    for i in range(n_ensemble):
        seed = 42 + i * 10
        X_tr, X_te, y_tr, y_te = train_test_split(
            X_scaled, y, test_size=0.2, random_state=seed
        )
        m = MLXLogisticRegression(X_scaled.shape[1])
        mx.eval(m.parameters())
        m, val_m, _ = train_mlx_model(
            m, X_tr, y_tr, X_te, y_te,
            lr=5e-3, epochs=300, batch_size=128, patience=30, l2_lambda=1e-5,
        )
        ensemble_models.append(m)
        te_prob = np.array(m(mx.array(X_te)))
        te_m = compute_metrics(y_te, te_prob)
        ensemble_metrics_list.append(te_m)
        logger.info(f"  Ensemble model {i+1}: auc={te_m['auc']:.4f}")

    # Ensemble prediction: average probabilities from all models
    ensemble_probs = np.zeros(len(X_test))
    for m in ensemble_models:
        ensemble_probs += np.array(m(mx.array(X_test)))
    ensemble_probs /= n_ensemble
    ensemble_metrics = compute_metrics(y_test, ensemble_probs)
    logger.info(f"  Ensemble avg: acc={ensemble_metrics['accuracy']:.4f} auc={ensemble_metrics['auc']:.4f} brier={ensemble_metrics['brier']:.4f}")

    # Export ensemble weights
    team_id_to_idx_str = {str(k): v for k, v in TEAM_ID_TO_IDX.items()}
    all_results["Ensemble_LR"] = ensemble_metrics
    best_name = max(all_results, key=lambda n: all_results[n]["auc"])
    best_data = all_results[best_name]
    logger.info(f"\nBest model: {best_name} (AUC={best_data['auc']:.4f})")

    if best_name == "Ensemble_LR":
        ensemble_flat = {}
        for i, m in enumerate(ensemble_models):
            flat = tree_flatten(m.parameters())
            for key, val in flat:
                ensemble_flat[f"model{i}_{key}"] = np.asarray(val).tolist()
        export = {
            "model_type": "mlx_ensemble_5",
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "feature_names": feature_names,
            "params": ensemble_flat,
            "metrics": best_data,
        }
        with open(MODEL_DIR / "mlx_weights.json", "w") as f:
            json.dump(export, f, indent=2)
        logger.info(f"Exported ensemble weights to {MODEL_DIR / 'mlx_weights.json'}")
    elif best_name == "LR+Embedding":
        export_mlx_weights(emb_lr, scaler_t, feature_names_t, best_data,
                           "mlx_lr_embedding", MODEL_DIR / "mlx_weights.json", team_id_to_idx_str)
    elif best_name == "MLP+Embedding":
        export_mlx_weights(emb_mlp, scaler_t, feature_names_t, best_data,
                           "mlp_embedding", MODEL_DIR / "mlx_weights.json", team_id_to_idx_str)
    elif best_name == "MLX_LR":
        export_mlx_weights(lr_model, scaler, feature_names, best_data,
                           "mlx_LR", MODEL_DIR / "mlx_weights.json")
    else:
        export_mlx_weights(lr_model, scaler, feature_names, best_data,
                           "mlx_LR", MODEL_DIR / "mlx_weights.json")

    export_to_typescript(MODEL_DIR / "mlx_weights.json", MODEL_DIR / "mlx_model.ts")
    logger.info(f"\nTotal time: {time.time()-start:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
