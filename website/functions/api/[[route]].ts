import { buildFeaturesForGame } from "../_features";
import { predict } from "../_predict";
import {
  fetchGamecenterLanding, fetchGamecenterBoxscore, fetchScoreboardNow,
  fetchTeamRoster, fetchTeamsList,
} from "../_nhl";

const STATS_API = "https://api.nhle.com/stats/rest/en";
const WEB_API = "https://api-web.nhle.com/v1";

export async function onRequest(context: any): Promise<Response> {
  const url = new URL(context.request.url);
  const path = url.pathname;

  try {
    // ---- Predictions ----
    if (path === "/api/predictions") {
      return handleBulkPredictions();
    }

    const predMatch = path.match(/^\/api\/predictions\/(\d+)$/);
    if (predMatch) {
      return handleSinglePrediction(parseInt(predMatch[1]));
    }

    // ---- Schedule (league) ----
    if (path === "/api/schedule") {
      return handleSchedule();
    }

    // ---- Schedule (team) ----
    const schedTeamMatch = path.match(/^\/api\/schedule\/team\/([A-Za-z]+)$/);
    if (schedTeamMatch) {
      return handleTeamSchedule(schedTeamMatch[1]);
    }

    // ---- Rosters ----
    const rosterMatch = path.match(/^\/api\/rosters\/([A-Za-z]+)$/);
    if (rosterMatch) {
      return handleRoster(rosterMatch[1]);
    }

    // ---- Teams ----
    if (path === "/api/teams") {
      return handleTeams();
    }

    // ---- Lineups ----
    const lineupMatch = path.match(/^\/api\/lineups\/game\/(\d+)$/);
    if (lineupMatch) {
      return handleLineups(parseInt(lineupMatch[1]));
    }

    // ---- Stats ----
    const statsMatch = path.match(/^\/api\/stats\/(.+)$/);
    if (statsMatch) {
      return proxyJson(`${STATS_API}/${statsMatch[1]}${url.search}`);
    }

    return json({ error: "Not found" }, 404);
  } catch (e: any) {
    console.error("Pages Function error:", e);
    return json({ error: e.message ?? "Internal error" }, 500);
  }
}

function json(data: any, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function proxyJson(targetUrl: string): Promise<Response> {
  const resp = await fetch(targetUrl, {
    headers: { "Accept": "application/json", "User-Agent": "nhl-ml-lab/1.0" },
  });
  const data = await resp.json();
  return json(data);
}

async function proxyFetch(targetUrl: string): Promise<any> {
  const resp = await fetch(targetUrl, {
    headers: { "Accept": "application/json", "User-Agent": "nhl-ml-lab/1.0" },
  });
  if (!resp.ok) return null;
  return resp.json();
}

function teamInfo(t: any) {
  return {
    id: t?.id ?? 0,
    abbrev: t?.abbrev ?? "",
    common_name: t?.commonName?.default ?? "",
    place_name: t?.placeName?.default ?? "",
    logo: t?.logo ?? "",
  };
}

function parseGame(g: any) {
  const ht = g.homeTeam ?? {};
  const at = g.awayTeam ?? {};
  return {
    id: g.id ?? 0,
    season: g.season ?? 0,
    game_type: g.gameType ?? 0,
    game_date: g.gameDate ?? "",
    start_time_utc: g.startTimeUTC ?? "",
    game_state: g.gameState ?? "",
    venue: g.venue?.default ?? "",
    home_team: { ...teamInfo(ht), score: ht.score ?? null },
    away_team: { ...teamInfo(at), score: at.score ?? null },
    home_score: ht.score ?? null,
    away_score: at.score ?? null,
    period: g.periodDescriptor?.number ?? null,
    clock: g.clock ?? null,
  };
}

function collectGames(data: any): any[] {
  if (data?.games?.length) {
    return data.games.map(parseGame);
  }
  if (data?.gameWeek) {
    const games: any[] = [];
    for (const day of data.gameWeek) {
      for (const g of day.games ?? []) {
        games.push(parseGame(g));
      }
    }
    return games;
  }
  return [];
}

// ---- Prediction handlers ----

async function handleSinglePrediction(gameId: number): Promise<Response> {
  const data = await fetchGamecenterLanding(gameId);
  if (!data) return json({ game_id: gameId, error: "Game not found" });

  const home = data.homeTeam ?? {};
  const away = data.awayTeam ?? {};
  const season = String(data.season ?? "20242025");
  const gameDate = data.gameDate ?? "";

  const homeTid = home.id;
  const awayTid = away.id;
  if (!homeTid || !awayTid) return json({ game_id: gameId, error: "Invalid team data" });

  const features = await buildFeaturesForGame(homeTid, awayTid, gameDate, season);
  const result = predict(features);

  return json({
    game_id: gameId,
    home_team: home.placeName?.default ?? "",
    away_team: away.placeName?.default ?? "",
    home_team_abbrev: home.abbrev ?? "",
    away_team_abbrev: away.abbrev ?? "",
    season,
    game_state: data.gameState ?? "",
    ...result,
  });
}

async function handleBulkPredictions(): Promise<Response> {
  const data = await fetchScoreboardNow();
  if (!data) return json({ predictions: [], count: 0 });

  const rawGames = data.games ?? [];
  const predictions = [];

  for (const g of rawGames) {
    if (g.gameState === "OFF" || g.gameState === "FINAL") continue;
    const homeTid = g.homeTeam?.id;
    const awayTid = g.awayTeam?.id;
    if (!homeTid || !awayTid) continue;

    try {
      const season = String(g.season ?? "20242025");
      const features = await buildFeaturesForGame(homeTid, awayTid, g.gameDate, season);
      const result = predict(features);
      predictions.push({
        game_id: g.id,
        home_team: g.homeTeam?.placeName?.default ?? "",
        away_team: g.awayTeam?.placeName?.default ?? "",
        home_team_abbrev: g.homeTeam?.abbrev ?? "",
        away_team_abbrev: g.awayTeam?.abbrev ?? "",
        game_date: g.gameDate,
        game_state: g.gameState,
        season,
        ...result,
      });
    } catch (e) {
      console.error(`Skipping game ${g.id}:`, e);
    }
  }

  return json({ predictions, count: predictions.length });
}

// ---- Schedule handlers ----

async function handleSchedule(): Promise<Response> {
  const [scoreData, schedData] = await Promise.all([
    fetchScoreboardNow(),
    proxyFetch(`${WEB_API}/schedule/now`),
  ]);
  const games = collectGames(scoreData ?? schedData);
  return json({
    prev_date: scoreData?.prevDate ?? schedData?.previousStartDate,
    current_date: scoreData?.currentDate,
    next_date: scoreData?.nextDate ?? schedData?.nextStartDate,
    games,
  });
}

async function handleTeamSchedule(abbrev: string): Promise<Response> {
  const raw = await proxyFetch(`${WEB_API}/club-schedule-season/${abbrev.toUpperCase()}/now`);
  const games = (raw?.games ?? []).map(parseGame);
  return json({ team_abbrev: abbrev.toUpperCase(), season: raw?.currentSeason, games });
}

// ---- Roster handler ----

async function handleRoster(teamAbbrev: string): Promise<Response> {
  const data = await fetchTeamRoster(teamAbbrev.toUpperCase(), "20252026");
  if (!data) return json({ error: "Team not found" }, 404);

  const mapPlayer = (p: any) => ({
    id: p.id,
    first_name: p.firstName?.default ?? "",
    last_name: p.lastName?.default ?? "",
    position_code: p.positionCode ?? "",
    sweater_number: p.sweaterNumber ?? null,
    birth_date: p.birthDate ?? null,
    birth_country: p.birthCountry ?? null,
    headshot: p.headshot ?? null,
    height_inches: p.heightInInches ?? null,
    weight_pounds: p.weightInPounds ?? null,
    shoots_catches: p.shootsCatches ?? null,
  });

  const sortBySweater = (arr: any[]) =>
    [...arr].sort((a: any, b: any) => (a.sweater_number ?? 99) - (b.sweater_number ?? 99));

  return json({
    team_abbrev: teamAbbrev.toUpperCase(),
    season: "20252026",
    forwards: sortBySweater((data.forwards ?? []).map(mapPlayer)),
    defensemen: sortBySweater((data.defensemen ?? []).map(mapPlayer)),
    goalies: sortBySweater((data.goalies ?? []).map(mapPlayer)),
  });
}

// ---- Teams handler ----

async function handleTeams(): Promise<Response> {
  const data = await fetchTeamsList();
  if (!data?.data) return json({ teams: [] });

  const activeIds = new Set([
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 25, 26,
    28, 29, 30, 52, 54, 55, 59,
  ]);

  const teams = data.data
    .filter((t: any) => activeIds.has(t.id) && t.triCode !== "TBD")
    .map((t: any) => ({ id: t.id, abbrev: t.triCode, name: t.fullName }));

  return json({ teams });
}

// ---- Lineups handler ----

async function handleLineups(gameId: number): Promise<Response> {
  const [landing, boxscore] = await Promise.all([
    fetchGamecenterLanding(gameId),
    fetchGamecenterBoxscore(gameId),
  ]);

  if (!landing) return json({ error: "Game not found" }, 404);

  const game = {
    id: gameId,
    game_date: landing.gameDate ?? "",
    game_state: landing.gameState ?? "",
    venue: landing.venue?.default ?? "",
    home_team: { id: landing.homeTeam?.id, abbrev: landing.homeTeam?.abbrev, place_name: landing.homeTeam?.placeName?.default ?? "" },
    away_team: { id: landing.awayTeam?.id, abbrev: landing.awayTeam?.abbrev, place_name: landing.awayTeam?.placeName?.default ?? "" },
  };

  function extractLeaders(side: any): Record<string, any> {
    const leaders: Record<string, any> = {};
    if (!side) return leaders;
    const categories = [
      { key: "goals", extract: (p: any) => p.goals ?? 0 },
      { key: "assists", extract: (p: any) => p.assists ?? 0 },
      { key: "points", extract: (p: any) => p.points ?? 0 },
      { key: "hits", extract: (p: any) => p.hits ?? 0 },
      { key: "blockedShots", extract: (p: any) => p.blockedShots ?? 0 },
      { key: "sog", extract: (p: any) => p.sog ?? 0 },
    ];
    const allPlayers = [...(side.forwards ?? []), ...(side.defense ?? []), ...(side.goalies ?? [])];

    for (const cat of categories) {
      let best: any = null;
      let bestVal = -1;
      for (const p of allPlayers) {
        const val = cat.extract(p);
        if (val > bestVal) { bestVal = val; best = p; }
      }
      if (best) {
        leaders[cat.key] = {
          player_id: best.playerId,
          name: best.name?.default ?? "",
          value: bestVal,
          position_code: best.position ?? "",
          sweater_number: best.sweaterNumber ?? null,
        };
      }
    }
    return leaders;
  }

  return json({
    game,
    home_leaders: extractLeaders(boxscore?.playerByGameStats?.homeTeam),
    away_leaders: extractLeaders(boxscore?.playerByGameStats?.awayTeam),
  });
}
