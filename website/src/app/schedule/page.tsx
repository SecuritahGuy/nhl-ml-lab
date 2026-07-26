"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import { apiUrl } from "@/lib/api";

interface TeamInfo {
  abbrev: string;
  common_name: string;
  place_name: string;
  logo: string;
}

interface Game {
  id: number;
  game_date: string;
  game_state: string;
  game_type: number;
  venue: string;
  home_team: TeamInfo;
  away_team: TeamInfo;
  home_score: number | null;
  away_score: number | null;
  period: number | null;
}

interface ScheduleData {
  current_date?: string;
  prev_date?: string;
  next_date?: string;
  date?: string;
  games: Game[];
}

interface Prediction {
  game_id: number;
  home_win_probability: number;
  away_win_probability: number;
  predicted_home_score: number;
  predicted_away_score: number;
  confidence: number;
}

function stateLabel(state: string, gameType: number): string {
  if (state === "FUT") return gameType === 1 ? "Preseason" : "Scheduled";
  if (state === "LIVE") return "Live";
  if (state === "OFF" || state === "FINAL") return "Final";
  return state;
}

export default function SchedulePage() {
  const [data, setData] = useState<ScheduleData | null>(null);
  const [teamData, setTeamData] = useState<ScheduleData | null>(null);
  const [predictions, setPredictions] = useState<Map<number, Prediction>>(new Map());
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"daily" | "team">("daily");
  const [selectedTeam, setSelectedTeam] = useState("BOS");
  const [teams, setTeams] = useState<string[]>([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [scheduleRes, predsRes] = await Promise.all([
        fetch(apiUrl(mode === "team" ? `/api/schedule/team/${selectedTeam}` : "/api/schedule")),
        fetch(apiUrl("/api/predictions")),
      ]);
      const scheduleJson = await scheduleRes.json();
      if (mode === "team") setTeamData(scheduleJson);
      else setData(scheduleJson);

      const predsJson = await predsRes.json();
      const predMap = new Map<number, Prediction>();
      if (predsJson.predictions) {
        for (const p of predsJson.predictions) {
          predMap.set(p.game_id, {
            game_id: p.game_id,
            home_win_probability: p.home_win_probability,
            away_win_probability: p.away_win_probability,
            predicted_home_score: p.predicted_home_score,
            predicted_away_score: p.predicted_away_score,
            confidence: p.confidence,
          });
        }
      }
      setPredictions(predMap);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeams();
    fetchData();
  }, []);

  useEffect(() => {
    if (mode === "team") fetchData();
  }, [selectedTeam, mode]);

  const fetchTeams = async () => {
    try {
      const res = await fetch(apiUrl("/api/teams"));
      const json = await res.json();
      if (json.teams) setTeams(json.teams.map((t: any) => t.abbrev));
    } catch (e) {
      console.error(e);
    }
  };

  const games = mode === "team" ? teamData?.games ?? [] : data?.games ?? [];
  const headerDate = mode === "team"
    ? `${selectedTeam} Schedule`
    : data?.current_date || data?.date || "Today";

  const ProbBar = ({ gameId }: { gameId: number }) => {
    const p = predictions.get(gameId);
    if (!p) return null;
    const hp = p.home_win_probability;

    if (hp === 0 && p.away_win_probability === 1) {
      return <div className="text-xs text-gray-400 italic">Model unavailable</div>;
    }

    return (
      <div className="w-28">
        <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="absolute left-0 top-0 h-full bg-nhl-red rounded-full"
            style={{ width: `${hp * 100}%` }}
          />
          <div
            className="absolute top-0 h-full bg-blue-600 rounded-full"
            style={{ left: `${hp * 100}%`, width: `${(1 - hp) * 100}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-0.5">
          <span>{(hp * 100).toFixed(0)}%</span>
          <span>{((1 - hp) * 100).toFixed(0)}%</span>
        </div>
      </div>
    );
  };

  return (
    <div>
      <Navbar />
      <h1 className="text-3xl font-bold mb-4">Schedule</h1>
      <div className="flex gap-4 mb-6 items-center">
        <div className="flex gap-2 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setMode("daily")}
            className={`px-3 py-1 rounded ${mode === "daily" ? "bg-white shadow" : ""}`}
          >
            League
          </button>
          <button
            onClick={() => setMode("team")}
            className={`px-3 py-1 rounded ${mode === "team" ? "bg-white shadow" : ""}`}
          >
            Team
          </button>
        </div>
        {mode === "team" && (
          <select
            value={selectedTeam}
            onChange={(e) => setSelectedTeam(e.target.value)}
            className="border rounded px-3 py-2"
          >
            {teams.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        )}
      </div>
      {loading && <p className="text-gray-500">Loading schedule...</p>}
      {!loading && games.length === 0 && (
        <p className="text-gray-500">No games scheduled.</p>
      )}
      <ul className="space-y-2">
        {games.map((game) => (
          <li
            key={game.id}
            className="bg-white rounded-lg shadow p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-4 flex-1">
              <img
                src={game.away_team.logo}
                alt={game.away_team.abbrev}
                className="w-8 h-8"
              />
              <span className="font-semibold w-8 text-right">{game.away_team.abbrev}</span>
              <span className="text-gray-400">@</span>
              <span className="font-semibold w-8">{game.home_team.abbrev}</span>
              <img
                src={game.home_team.logo}
                alt={game.home_team.abbrev}
                className="w-8 h-8"
              />
            </div>
            <div className="flex items-center gap-4">
              {(game.game_state === "FUT" || game.game_state === "PRE") ? (
                <ProbBar gameId={game.id} />
              ) : (
                <span className="text-lg font-mono w-16 text-center">
                  {game.away_score ?? "-"} - {game.home_score ?? "-"}
                </span>
              )}
              <span
                className={`text-xs px-2 py-1 rounded ${
                  game.game_state === "OFF" || game.game_state === "FINAL"
                    ? "bg-green-100 text-green-800"
                    : game.game_state === "LIVE"
                    ? "bg-red-100 text-red-800 animate-pulse"
                    : "bg-blue-100 text-blue-800"
                }`}
              >
                {stateLabel(game.game_state, game.game_type)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
