---
description: Retrain the MLX ensemble model, export weights to TypeScript, then build the website.
mode: subagent
---

You are retraining the NHL ML model and deploying updated weights to the website.

Steps:
1. Activate venv: `source .venv/bin/activate`
2. Run: `python3 backend/app/models/train_mlx.py`
3. Copy weights: `cp backend/models/mlx_model.ts website/functions/_model.ts`
4. Verify (optional): run `cd website && npm run build` to check compilation
5. Report the AUC and any changes from the previous model.

Report the output metrics from training (AUC, log-loss).
