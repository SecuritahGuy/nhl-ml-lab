const STATS_API = "https://api.nhle.com/stats/rest/en";
const WEB_API = "https://api-web.nhle.com/v1";

async function nhlFetch(url: string): Promise<any> {
  const resp = await fetch(url, {
    headers: { "Accept": "application/json", "User-Agent": "nhl-ml-lab/1.0" },
  });
  if (!resp.ok) {
    console.warn(`NHL API error ${resp.status}: ${url}`);
    return null;
  }
  return resp.json();
}

export interface TeamStats {
  gf_per_game: number;
  ga_per_game: number;
  pp_pct: number;
  pk_pct: number;
  fo_pct: number;
  sf_per_game: number;
  sa_per_game: number;
  point_pct: number;
  wins: number;
  losses: number;
  ot_losses: number;
  goals_for: number;
  goals_against: number;
}

export async function fetchTeamStats(season: string): Promise<Record<number, TeamStats>> {
  const data = await nhlFetch(
    `${STATS_API}/team/summary?cayenneExp=seasonId=${season}%20and%20gameTypeId=2&limit=100`
  );
  const map: Record<number, TeamStats> = {};
  if (data?.data) {
    for (const t of data.data) {
      const tid = t.teamId;
      if (!tid) continue;
      map[tid] = {
        gf_per_game: t.goalsForPerGame ?? 3.0,
        ga_per_game: t.goalsAgainstPerGame ?? 3.0,
        pp_pct: t.powerPlayPct ?? 0.20,
        pk_pct: t.penaltyKillPct ?? 0.80,
        fo_pct: t.faceoffWinPct ?? 0.50,
        sf_per_game: t.shotsForPerGame ?? 30.0,
        sa_per_game: t.shotsAgainstPerGame ?? 30.0,
        point_pct: t.pointPct ?? 0.50,
        wins: t.wins ?? 0,
        losses: t.losses ?? 0,
        ot_losses: t.otLosses ?? 0,
        goals_for: t.goalsFor ?? 0,
        goals_against: t.goalsAgainst ?? 0,
      };
    }
  }
  return map;
}

export interface GameInfo {
  id: number;
  season: string;
  gameDate: string;
  gameType: number;
  gameStateId: number;
  homeTeamId: number;
  visitingTeamId: number;
  homeScore: number;
  visitingScore: number;
}

export async function fetchSeasonGames(season: string): Promise<GameInfo[]> {
  const data = await nhlFetch(
    `${STATS_API}/game?cayenneExp=season=${season}`
  );
  return data?.data ?? [];
}

export async function fetchGoalieStats(season: string): Promise<any> {
  return nhlFetch(
    `${STATS_API}/goalie/summary?cayenneExp=seasonId=${season}%20and%20gameTypeId=2&limit=200`
  );
}

export async function fetchSkaterStats(season: string): Promise<any> {
  return nhlFetch(
    `${STATS_API}/skater/summary?cayenneExp=seasonId=${season}%20and%20gameTypeId=2&limit=1000`
  );
}

export async function fetchGamecenterLanding(gameId: number): Promise<any> {
  return nhlFetch(`${WEB_API}/gamecenter/${gameId}/landing`);
}

export async function fetchGamecenterBoxscore(gameId: number): Promise<any> {
  return nhlFetch(`${WEB_API}/gamecenter/${gameId}/boxscore`);
}

export async function fetchScoreboardNow(): Promise<any> {
  return nhlFetch(`${WEB_API}/score/now`);
}

export async function fetchTeamRoster(teamAbbrev: string, season: string): Promise<any> {
  return nhlFetch(`${WEB_API}/roster/${teamAbbrev}/${season}`);
}

export async function fetchTeamsList(): Promise<any> {
  return nhlFetch(`${STATS_API}/team?limit=35`);
}
