"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";

interface RosterPlayer {
  id: number;
  first_name: string;
  last_name: string;
  position_code: string;
  sweater_number: number | null;
  birth_date: string | null;
  birth_country: string | null;
  headshot: string | null;
  height_inches: number | null;
  weight_pounds: number | null;
  shoots_catches: string | null;
}

interface RosterData {
  team_abbrev: string;
  season: string;
  forwards: RosterPlayer[];
  defensemen: RosterPlayer[];
  goalies: RosterPlayer[];
}

function PlayerRow({ player }: { player: RosterPlayer }) {
  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="p-2">{player.sweater_number ?? "—"}</td>
      <td className="p-2 flex items-center gap-2">
        {player.headshot && (
          <img src={player.headshot} alt="" className="w-8 h-8 rounded-full" />
        )}
        <span className="font-medium">
          {player.first_name} {player.last_name}
        </span>
      </td>
      <td className="p-2">{player.position_code}</td>
      <td className="p-2 text-sm text-gray-500">
        {player.shoots_catches || "—"}
      </td>
      <td className="p-2 text-sm text-gray-500">
        {player.height_inches ? `${Math.floor(player.height_inches / 12)}'${player.height_inches % 12}"` : "—"} / {player.weight_pounds ?? "—"} lbs
      </td>
    </tr>
  );
}

function PositionGroup({
  title,
  players,
}: {
  title: string;
  players: RosterPlayer[];
}) {
  if (!players.length) return null;
  return (
    <div className="mb-6">
      <h3 className="text-lg font-semibold text-gray-700 mb-2">
        {title} ({players.length})
      </h3>
      <table className="w-full bg-white rounded-lg shadow overflow-hidden text-sm">
        <thead className="bg-nhl-dark text-white">
          <tr>
            <th className="p-2 text-left">#</th>
            <th className="p-2 text-left">Player</th>
            <th className="p-2 text-left">Pos</th>
            <th className="p-2 text-left">S/C</th>
            <th className="p-2 text-left">Ht / Wt</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <PlayerRow key={p.id} player={p} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function RostersPage() {
  const [data, setData] = useState<RosterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [team, setTeam] = useState("BOS");
  const [teams, setTeams] = useState<string[]>([]);

  const fetchRoster = async (t: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/rosters/${t}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch("/api/teams")
      .then((r) => r.json())
      .then((json) => {
        if (json.teams) setTeams(json.teams.map((t: any) => t.abbrev));
      })
      .catch(console.error);
    fetchRoster(team);
  }, []);

  useEffect(() => {
    fetchRoster(team);
  }, [team]);

  return (
    <div>
      <Navbar />
      <h1 className="text-3xl font-bold mb-4">Rosters</h1>
      <div className="flex gap-2 mb-6">
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          className="border rounded px-3 py-2"
        >
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>
      {loading && <p>Loading roster...</p>}
      {data && (
        <div>
          <p className="text-gray-500 mb-4">
            {data.team_abbrev} — Season {data.season}
          </p>
          <PositionGroup title="Forwards" players={data.forwards} />
          <PositionGroup title="Defensemen" players={data.defensemen} />
          <PositionGroup title="Goalies" players={data.goalies} />
        </div>
      )}
    </div>
  );
}