# NHL ML Lab

NHL ML/AI lab for predictions and a website with schedule, rosters, lineups, etc.

## Project Structure

```
nhl-ml-lab/
├── backend/          # FastAPI API server
│   ├── app/
│   │   ├── main.py       # FastAPI entry point
│   │   ├── api/          # Route handlers
│   │   ├── models/       # Data models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Data fetching & ML
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
├── website/          # Next.js frontend
├── data/             # Cached data
├── notebooks/        # Jupyter exploration
└── README.md
```

## NHL Data Sources

- `api-web.nhle.com/v1` — schedule, rosters, scores
- `api.nhle.com/stats/rest/en` — stats, standings, players
- `statsapi.web.nhl.com/api/v1` — legacy stats API

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

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Root status |
| `GET /api/schedule` | Daily schedule |
| `GET /api/rosters/{team}` | Team roster |
| `GET /api/lineups/game/{id}` | Game lineup |
| `GET /api/predictions/{id}` | Game prediction |