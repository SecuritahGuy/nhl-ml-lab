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
  sat_pct: number;
  pp_opp_per_game: number;
  tsh_per_game: number;
  es_gf_per_game: number;
}

async function fetchTeamReport(season: string, report: string): Promise<Record<number, any>> {
  const data = await nhlFetch(
    `${STATS_API}/team/${report}?cayenneExp=seasonId=${season}%20and%20gameTypeId=2&limit=100`
  );
  const map: Record<number, any> = {};
  if (data?.data) {
    for (const t of data.data) {
      const tid = t.teamId;
      if (!tid) continue;
      map[tid] = t;
    }
  }
  return map;
}

export async function fetchTeamStats(season: string): Promise<Record<number, TeamStats>> {
  const [summaryMap, rtMap, ppMap, pkMap, gfbsMap] = await Promise.all([
    fetchTeamReport(season, "summary"),
    fetchTeamReport(season, "realtime"),
    fetchTeamReport(season, "powerplay"),
    fetchTeamReport(season, "penaltykill"),
    fetchTeamReport(season, "goalsforbystrength"),
  ]);

  const allTids = new Set([...Object.keys(summaryMap), ...Object.keys(rtMap)].map(Number));
  const map: Record<number, TeamStats> = {};
  for (const tid of allTids) {
    const s = summaryMap[tid] ?? {};
    const rt = rtMap[tid] ?? {};
    const pp = ppMap[tid] ?? {};
    const pk = pkMap[tid] ?? {};
    const gfbs = gfbsMap[tid] ?? {};
    const gp = Math.max(s.gamesPlayed ?? rt.gamesPlayed ?? 82, 1);
    map[tid] = {
      gf_per_game: s.goalsForPerGame ?? 3.0,
      ga_per_game: s.goalsAgainstPerGame ?? 3.0,
      pp_pct: s.powerPlayPct ?? 0.20,
      pk_pct: s.penaltyKillPct ?? 0.80,
      fo_pct: s.faceoffWinPct ?? 0.50,
      sf_per_game: s.shotsForPerGame ?? 30.0,
      sa_per_game: s.shotsAgainstPerGame ?? 30.0,
      point_pct: s.pointPct ?? 0.50,
      wins: s.wins ?? 0,
      losses: s.losses ?? 0,
      ot_losses: s.otLosses ?? 0,
      goals_for: s.goalsFor ?? 0,
      goals_against: s.goalsAgainst ?? 0,
      sat_pct: rt.satPct ?? 0.50,
      pp_opp_per_game: pp.ppOpportunitiesPerGame ?? 2.5,
      tsh_per_game: pk.timesShorthandedPerGame ?? 3.0,
      es_gf_per_game: (gfbs.goalsFor5On5 ?? 150) / gp,
    };
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
