---
description: Add a new feature across all three layers: train.py, predictor.py, and _features.ts. Maintains ordering and fallback logic.
mode: subagent
---

You are adding a new feature to the NHL ML prediction pipeline. The feature must be added to all three layers:

1. `backend/app/models/train.py` — add to `engineer_features()` and `_make_features()`
2. `backend/app/models/predictor.py` — add to `predict_game()` and `_build_rolling()`
3. `website/functions/_features.ts` — add to `buildFeatureVector()` and `buildRollingArray()`

Rules:
- Feature name and position must match across all files.
- Fallback logic (what value to use when data is missing) must match.
- Rolling features must follow the suffix order: gf_roll, ga_roll, gd_roll, win_roll, gf_decay, ga_decay, gd_decay, win_decay, rest_days.
- Update feature count comments in all files.
- Run `cd website && npm run build` to verify TypeScript compiles.
- Report which files changed and the final feature count.

Feature to add:
$ARGUMENTS
