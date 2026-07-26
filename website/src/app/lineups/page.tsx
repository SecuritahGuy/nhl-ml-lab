"use client";

import { useState } from "react";
import Navbar from "@/components/Navbar";

interface Leader {
  player_id: number;
  name: string;
  value: number;
  position_code: string;
  sweater_number: number | null;
}

interface GameSummary {
  id: number;
  game_date: string;
  game_state: string;
  venue: string;
  home_team: { id: number; abbrev: string; place_name: string };
  away_team: { id: number; abbrev: string; place_name: string };
}

interface LineupData {
  game: GameSummary;
  home_leaders: Record<string, Leader>;
  away_leaders: Record<string, Leader>;
}

const GREEN = { R: "#006847", L: "#006847", C: "#003f7f", D: "#9b870c", G: "#8B0000" };

export default function LineupsPage() {
  const [data, setData] = useState<LineupData | null>(null);
  const [gameId, setGameId] = useState("2026010013");
  const [loading, setLoading] = useState(false);

  const fetchLineup = async () => {
    if (!gameId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/lineups/game/${gameId}`);
      const json = await res.json();
      setData(json as LineupData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const stateBadge = (state: string) => {
    if (state === "FUT") return <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">Upcoming</span>;
    if (state === "LIVE") return <span className="bg-red-100 text-red-800 text-xs px-2 py-1 rounded animate-pulse">Live</span>;
    if (state === "OFF") return <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">Final</span>;
    return <span className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded">{state}</span>;
  };

  const renderLeaders = (leaders: Record<string, Leader>, title: string) => {
    const entries = Object.entries(leaders);
    if (!entries.length) return <p className="text-gray-400 text-sm">No matchup data</p>;
    return (
      <div>
        <h3 className="font-semibold text-gray-700 mb-2">{title}</h3>
        <div className="space-y-2">
          {entries.map(([cat, leader]) => (
            <div key={cat} className="flex justify-between items-center text-sm">
              <span className="capitalize text-gray-500 w-20">{cat}</span>
              <span>#{leader.sweater_number ?? "—"} {leader.name}</span>
              <span className="font-mono font-bold">{leader.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div>
      <Navbar />
      <h1 className="text-3xl font-bold mb-4">Game Matchups</h1>
      <div className="flex gap-2 mb-6">
        <input
          type="number"
          placeholder="Game ID"
          value={gameId}
          onChange={(e) => setGameId(e.target.value)}
          className="border rounded px-3 py-2 w-44"
        />
        <button
          onClick={fetchLineup}
          className="bg-nhl-red text-white px-4 py-2 rounded hover:bg-red-700 transition"
        >
          Load
        </button>
      </div>
      {loading && <p>Loading game data...</p>}
      {data && (
        <div>
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="text-center flex-1">
                <p className="text-2xl font-bold">{data.game.away_team.abbrev}</p>
                <p className="text-sm text-gray-500">{data.game.away_team.place_name}</p>
              </div>
              <div className="text-center px-6">
                <p className="text-sm text-gray-500">{data.game.venue}</p>
                <p className="text-xs text-gray-400">{data.game.game_date}</p>
                <div className="mt-2">{stateBadge(data.game.game_state)}</div>
              </div>
              <div className="text-center flex-1">
                <p className="text-2xl font-bold">{data.game.home_team.abbrev}</p>
                <p className="text-sm text-gray-500">{data.game.home_team.place_name}</p>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-xl font-bold mb-4">{data.game.away_team.abbrev} Leaders</h2>
              {renderLeaders(data.away_leaders, "Scoring Leaders")}
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-xl font-bold mb-4">{data.game.home_team.abbrev} Leaders</h2>
              {renderLeaders(data.home_leaders, "Scoring Leaders")}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}