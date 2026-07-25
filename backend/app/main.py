import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import schedule, rosters, lineups, predictions, teams, standings

logging.basicConfig(level=logging.INFO)

from app.models.predictor import _init as _init_model
_init_model()

app = FastAPI(title="NHL ML Lab", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule.router, prefix="/api/schedule", tags=["schedule"])
app.include_router(rosters.router, prefix="/api/rosters", tags=["rosters"])
app.include_router(lineups.router, prefix="/api/lineups", tags=["lineups"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(standings.router, prefix="/api/standings", tags=["standings"])


@app.get("/")
def root():
    return {"status": "ok", "name": "NHL ML Lab"}


