"use client";

import { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/Navbar";

interface TeamInfo {
  abbrev: string;
  place_name: string;
  logo: string;
}

interface Game {
  id: number;
  game_date: string;
  game_state: string;
  home_team: TeamInfo;
  away_team: TeamInfo;
}

interface PredictionData {
  game_id: number;
  home_team: string;
  away_team: string;
  home_team_abbrev: string;
  away_team_abbrev: string;
  home_win_probability: number;
  away_win_probability: number;
  overtime_probability: number;
  predicted_home_score: number;
  predicted_away_score: number;
  confidence: number;
  model: string;
}

interface PredictionsResponse {
  predictions: PredictionData[];
  count: number;
}

export default function PredictionsPage() {
  const [gamePrediction, setGamePrediction] = useState<PredictionData | null>(null);
  const [bulkPredictions, setBulkPredictions] = useState<PredictionData[]>([]);
  const [gameId, setGameId] = useState("2026010013");
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"bulk" | "single">("bulk");

  const fetchBulk = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/predictions");
      const json = await res.json() as PredictionsResponse;
      setBulkPredictions(json.predictions || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBulk();
  }, [fetchBulk]);

  const fetchSingle = async () => {
    if (!gameId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/predictions/${gameId}`);
      const json = await res.json();
      setGamePrediction(json as PredictionData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const probBar = (homePct: number, awayPct: number) => (
    <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
      <div
        className="absolute left-0 top-0 h-full bg-nhl-red rounded-full transition-all"
        style={{ width: `${homePct * 100}%` }}
      />
      <div
        className="absolute top-0 h-full bg-blue-600 rounded-full transition-all"
        style={{ left: `${homePct * 100}%`, width: `${awayPct * 100}%` }}
      />
    </div>
  );

  const predictionCard = (p: PredictionData) => (
    <div key={p.game_id} className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-lg">{p.home_team_abbrev}</span>
        <span className="text-gray-400 text-sm">vs</span>
        <span className="font-semibold text-lg">{p.away_team_abbrev}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3 text-center">
        <div>
          <p className="text-2xl font-bold text-nhl-red">{(p.home_win_probability * 100).toFixed(0)}%</p>
          <p className="text-xs text-gray-500">Home Win</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-blue-600">{(p.away_win_probability * 100).toFixed(0)}%</p>
          <p className="text-xs text-gray-500">Away Win</p>
        </div>
      </div>
      {probBar(p.home_win_probability, p.away_win_probability)}
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{p.home_team_abbrev}</span>
        <span>{p.away_team_abbrev}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs text-gray-500">
        <div>
          <span className="font-semibold">{p.predicted_home_score} - {p.predicted_away_score}</span>
          <p className="text-gray-400">Predicted</p>
        </div>
        <div>
          <span className="font-semibold">{(p.overtime_probability * 100).toFixed(0)}%</span>
          <p className="text-gray-400">OT</p>
        </div>
        <div>
          <span className="font-semibold">{(p.confidence * 100).toFixed(0)}%</span>
          <p className="text-gray-400">Confidence</p>
        </div>
      </div>
    </div>
  );

  return (
    <div>
      <Navbar />
      <h1 className="text-3xl font-bold mb-4">Predictions</h1>
      <div className="flex gap-4 mb-6 items-center">
        <div className="flex gap-2 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setView("bulk")}
            className={`px-3 py-1 rounded ${view === "bulk" ? "bg-white shadow" : ""}`}
          >
            Upcoming Games
          </button>
          <button
            onClick={() => setView("single")}
            className={`px-3 py-1 rounded ${view === "single" ? "bg-white shadow" : ""}`}
          >
            Single Game
          </button>
        </div>
        {view === "single" && (
          <div className="flex gap-2">
            <input
              type="number"
              placeholder="Game ID"
              value={gameId}
              onChange={(e) => setGameId(e.target.value)}
              className="border rounded px-3 py-2 w-40"
            />
            <button
              onClick={fetchSingle}
              className="bg-nhl-red text-white px-4 py-2 rounded hover:bg-red-700 transition"
            >
              Predict
            </button>
          </div>
        )}
      </div>

      {loading && <p className="text-gray-500">Loading predictions...</p>}

      {view === "bulk" && (
        <>
          {!loading && bulkPredictions.length === 0 && (
            <p className="text-gray-500">No upcoming games to predict.</p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {bulkPredictions.map(predictionCard)}
          </div>
        </>
      )}

      {view === "single" && gamePrediction && (
        <div className="max-w-md mx-auto">
          {predictionCard(gamePrediction)}
        </div>
      )}
    </div>
  );
}