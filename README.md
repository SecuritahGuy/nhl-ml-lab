# NHL ML Lab

NHL ML/AI lab for game predictions and a website with schedule, rosters, lineups, and stats.

## Project Structure

```
nhl-ml-lab/
├── backend/                  # FastAPI API server
│   ├── app/
│   │   ├── main.py               # FastAPI entry point
│   │   ├── api/                  # Route handlers
│   │   │   ├── predictions.py    # Game prediction endpoints
│   │   │   ├── schedule.py       # Daily/weekly schedule
│   │   │   ├── rosters.py        # Team rosters
│   │   │   ├── lineups.py        # Game lineups
│   │   │   ├── teams.py          # Team info
│   │   │   ├── standings.py      # Standings
│   │   │   └── stats.py          # Team/skater/goalie stats
│   │   ├── models/
│   │   │   ├── predictor.py      # Live prediction engine
│   │   │   └── train.py          # Model training pipeline
│   │   └── services/
│   │       └── nhl.py            # NHL API client
│   ├── models/                   # Trained models (gitignored)
│   │   ├── nhl_predictor.joblib
│   │   └── model_meta.json
│   ├── requirements.txt
│   └── pyproject.toml
├── website/                  # Next.js 14 frontend
├── data/
└── notebooks/
```

## Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd website
npm install
npm run dev
```

## ML Model

The backend trains a **Logistic Regression with L1 regularization** on 7,763 historical games (2019–2025).

### Features (71 total, 30 active after L1 pruning)

| Category | Count | Description |
|---|---|---|
| Team season stats | 16 | GF/G, GA/G, PP%, PK%, FO%, SF/G, SA/G, Pt% for home & away |
| Matchup differentials | 11 | gf_diff, ga_diff, net_diff, st_diff, shot_diff, corsi_diff, fo_diff, pp_diff, pk_diff, win% |
| Rolling features | 44 | Multi-window rolling averages (3/5/10/20 games) + exponential decay (0.7/0.8/0.9) for GF, GA, win rate |

### Key findings from rolling window exploration

- **Win rate**: 20-game rolling window is most predictive
- **Goals for/against**: 5-game rolling window captures recent scoring trends
- **Exponential decay**: Slow decay (0.9) for win rate; medium decay (0.8) for goals against
- Short windows (3-game) and fast decay (0.7) were pruned by L1 regularization as redundant

### Training

```bash
cd backend
python -m app.models.train
```

The best model is auto-selected and saved to `backend/models/nhl_predictor.joblib`.

### Performance

| Metric | Value |
|---|---|
| Test accuracy | 61.2% |
| Test AUC | 0.656 |
| CV AUC (5-fold) | 0.681 ± 0.017 |
| Active features | 30 of 71 |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Root status |
| `GET /api/schedule` | Daily schedule |
| `GET /api/rosters/{team}` | Team roster |
| `GET /api/lineups/game/{id}` | Game lineup |
| `GET /api/predictions` | Bulk predictions for upcoming games |
| `GET /api/predictions/{id}` | Single game prediction |
| `GET /api/stats/teams?season=` | Team season stats (summary/realtime/powerplay/penaltykill) |
| `GET /api/stats/skaters?season=&limit=` | Skater stats (summary/realtime/faceoff/bios) |
| `GET /api/stats/goalies?season=&limit=` | Goalie stats (summary/advanced/saves/bios) |
| `GET /api/stats/leaders` | Current skater & goalie leaders |
| `GET /api/stats/game/{id}` | Game right-rail stats |
| `GET /api/teams` | All teams |
| `GET /api/standings` | NHL standings |

### Prediction Response

```json
{
  "game_id": 2024020835,
  "home_team": "Buffalo",
  "away_team": "New Jersey",
  "home_win_probability": 0.40,
  "away_win_probability": 0.60,
  "overtime_probability": 0.10,
  "predicted_home_score": 1.69,
  "predicted_away_score": 4.11,
  "confidence": 0.66,
  "model": "LogisticRegression"
}
```

## NHL Data Sources

- `api-web.nhle.com/v1` — live schedule, rosters, gamecenter, scoreboard
- `api.nhle.com/stats/rest/en` — team, skater, goalie season stats via cayenneExp queries
- `api-web.nhle.com/v1/gamecenter/{id}/landing` — game details, team records
- `api-web.nhle.com/v1/gamecenter/{id}/right-rail` — game officials, season series
