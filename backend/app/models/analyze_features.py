import json
from pathlib import Path

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "mlx_weights.json"

with open(MODEL_PATH) as f:
    data = json.load(f)

feature_names = data["feature_names"]
params = data["params"]
metrics = data.get("metrics", {})

n_models = sum(1 for k in params if k.endswith(".weight"))
n_features = len(feature_names)
print(f"Ensemble: {n_models} models, {n_features} features")
if metrics:
    print(f"  AUC: {metrics['auc']:.4f}")
    print(f"  Accuracy: {metrics['accuracy']:.4f}")
    print(f"  Brier: {metrics['brier']:.4f}")
print()

coefs = []
for i in range(n_models):
    w = params[f"model{i}_linear.weight"]
    coefs.append(w[0])
    b = params[f"model{i}_linear.bias"]
    print(f"  Model {i}: bias={b[0]:.4f}")

avg_coefs = [sum(c[i] for c in coefs) / n_models for i in range(n_features)]
importance = [
    (abs(avg_coefs[i]), avg_coefs[i], feature_names[i], i)
    for i in range(n_features)
]
importance.sort(key=lambda x: -x[0])

print(f"\n{'Rank':<5} {'Importance':<11} {'Coef':<11}  Feature")
print("-" * 70)
for rank, (imp, coef, name, _) in enumerate(importance[:25], 1):
    print(f"{rank:<5} {imp:<11.4f} {coef:<+11.4f}  {name}")

print("\n--- Bottom 10 (least important) ---")
for rank, (imp, coef, name, _) in enumerate(importance[-10:], n_features - 9):
    print(f"{rank:<5} {imp:<11.4f} {coef:<+11.4f}  {name}")

ROLLING_SFX = {
    "gf_roll3", "gf_roll5", "gf_roll10", "gf_roll20",
    "ga_roll3", "ga_roll5", "ga_roll10", "ga_roll20",
    "gd_roll3", "gd_roll5", "gd_roll10", "gd_roll20",
    "win_roll3", "win_roll5", "win_roll10", "win_roll20",
    "cf_roll3", "cf_roll5", "cf_roll10", "cf_roll20",
    "ca_roll3", "ca_roll5", "ca_roll10", "ca_roll20",
    "cd_roll3", "cd_roll5", "cd_roll10", "cd_roll20",
    "gf_decay07", "gf_decay08", "gf_decay09",
    "ga_decay07", "ga_decay08", "ga_decay09",
    "gd_decay07", "gd_decay08", "gd_decay09",
    "win_decay07", "win_decay08", "win_decay09",
    "cf_decay07", "cf_decay08", "cf_decay09",
    "ca_decay07", "ca_decay08", "ca_decay09",
    "cd_decay07", "cd_decay08", "cd_decay09",
    "rest_days",
}

# Group by category
base_indices = [i for i, n in enumerate(feature_names)
                if not any(n == f"home_{sfx}" or n == f"away_{sfx}" for sfx in ROLLING_SFX)]
home_indices = [i for i, n in enumerate(feature_names) if n.startswith("home_") and n.removeprefix("home_") in ROLLING_SFX]
away_indices = [i for i, n in enumerate(feature_names) if n.startswith("away_") and n.removeprefix("away_") in ROLLING_SFX]

base_imp = sum(abs(avg_coefs[i]) for i in base_indices) / len(base_indices) if base_indices else 0
home_imp = sum(abs(avg_coefs[i]) for i in home_indices) / len(home_indices) if home_indices else 0
away_imp = sum(abs(avg_coefs[i]) for i in away_indices) / len(away_indices) if away_indices else 0

print(f"\n--- Category summary ---")
print(f"  Base features ({len(base_indices)}):     {base_imp:.4f} avg |coef|")
print(f"  Home rolling ({len(home_indices)}):      {home_imp:.4f} avg |coef|")
print(f"  Away rolling ({len(away_indices)}):      {away_imp:.4f} avg |coef|")

# Top rolling features
rolling_list = [(abs(avg_coefs[i]), avg_coefs[i], feature_names[i]) for i in home_indices + away_indices]
rolling_list.sort(key=lambda x: -x[0])

print(f"\n--- Top 10 rolling features ---")
for rank, (imp, coef, name) in enumerate(rolling_list[:10], 1):
    print(f"{rank:<5} {imp:<11.4f} {coef:<+11.4f}  {name}")

# Top base features
base_list_raw = [(abs(avg_coefs[i]), avg_coefs[i], feature_names[i]) for i in base_indices]
base_list_raw.sort(key=lambda x: -x[0])

print(f"\n--- Top 10 base features ---")
for rank, (imp, coef, name) in enumerate(base_list_raw[:10], 1):
    print(f"{rank:<5} {imp:<11.4f} {coef:<+11.4f}  {name}")

# Coefficient stability across ensemble
print(f"\n--- Coefficient stability (top 15 features) ---")
print(f"{'Feature':<30} {'Mean':<10} {'Std':<10} {'Signs agree':<13}")
print("-" * 65)
for imp, coef, name, idx in importance[:15]:
    vals = [c[idx] for c in coefs]
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    n_pos = sum(1 for v in vals if v > 0)
    n_neg = sum(1 for v in vals if v < 0)
    print(f"{name:<30} {mean:<+10.4f} {std:<10.4f} {max(n_pos, n_neg)}/{n_models}")
