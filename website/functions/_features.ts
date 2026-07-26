// Feature count: 52 base + 50 rolling×2 - 10 pruned = 142 features
import { TeamStats, GameInfo, ShotStats, fetchTeamStats, fetchSeasonGames, fetchGoalieStats, fetchSkaterStats, fetchGameBoxscoreShots } from "./_nhl";
import { TEAM_ABBREV_TO_ID } from "./_locations";
import { travelDistanceMiles, tzCrossed, altitudeAdvantageFt, highAltitudeHome } from "./_locations";

const ROLLING_WINDOWS = [3, 5, 10, 20];
const DECAY_FACTORS = [0.7, 0.8, 0.9];

const EXCLUDED_FEATURES = new Set([
  "home_sf_per_game", "home_pk_pct", "home_goalie_sv_pct",
  "away_pk_pct", "tz_crossed",
  "home_cf_roll10", "home_cf_decay09",
  "away_cf_roll3", "away_ca_roll20", "away_cd_roll5",
]);

function checkRestCat(teamId: number, gameDate: Date, games: GameInfo[]): number {
  const dates: string[] = [];
  for (const g of games) {
    if (g.gameStateId !== 7) continue;
    if (g.gameType !== 2 && g.gameType !== 3) continue;
    if (g.homeTeamId === teamId || g.visitingTeamId === teamId) {
      dates.push(g.gameDate);
    }
  }
  if (dates.length === 0) return 4;
  const gdStr = gameDate.toISOString().slice(0, 10);
  const prev = new Date(gameDate);
  for (let d = 1; d <= 3; d++) {
    prev.setDate(gameDate.getDate() - d);
    const ps = prev.toISOString().slice(0, 10);
    if (dates.includes(ps)) return d - 1;
    prev.setDate(gameDate.getDate());
  }
  return 4;
}

function dayOfSeason(gameDate: string, season: string): number {
  const seasonYear = parseInt(season.slice(0, 4));
  const seasonStart = new Date(seasonYear, 9, 1); // Oct 1
  const gd = new Date(gameDate);
  return Math.round((gd.getTime() - seasonStart.getTime()) / (1000 * 60 * 60 * 24));
}

export async function buildFeaturesForGame(
  homeTid: number,
  awayTid: number,
  gameDate: string,
  season: string,
): Promise<number[]> {
  const [statsMap, games, goalieRaw, skaterRaw] = await Promise.all([
    fetchTeamStats(season),
    fetchSeasonGames(season),
    fetchGoalieStats(season),
    fetchSkaterStats(season),
  ]);

  const hs = statsMap[homeTid] ?? getDefaultStats();
  const aws = statsMap[awayTid] ?? getDefaultStats();

  const gd = new Date(gameDate);

  // Fetch boxscores for prior games to compute rolling Corsi
  const priorGames = games.filter(g => {
    if (g.gameStateId !== 7) return false;
    if (g.gameType !== 2 && g.gameType !== 3) return false;
    return new Date(g.gameDate) < gd;
  });
  const shotEntries = await Promise.all(
    priorGames.map(g => fetchGameBoxscoreShots(g.id).then(s => [g.id, s] as const))
  );
  const shotMap: Record<number, ShotStats> = {};
  for (const [id, s] of shotEntries) {
    if (s) shotMap[id] = s;
  }

  const homeRoll = computeRollingForTeam(homeTid, gd, games, shotMap);
  const awayRoll = computeRollingForTeam(awayTid, gd, games, shotMap);

  const homeB2b = checkBackToBack(homeTid, gd, games);
  const awayB2b = checkBackToBack(awayTid, gd, games);
  const homeRc = checkRestCat(homeTid, gd, games);
  const awayRc = checkRestCat(awayTid, gd, games);
  const dos = dayOfSeason(gameDate, season);

  const goalieMap = buildGoalieMap(goalieRaw);
  const skaterMap = buildSkaterMap(skaterRaw);

  const hg = goalieMap[homeTid] ?? { goalie_sv_pct: 0.900, goalie_gaa: 3.0 };
  const ag = goalieMap[awayTid] ?? { goalie_sv_pct: 0.900, goalie_gaa: 3.0 };
  const hsk = skaterMap[homeTid] ?? { top_scorer_ppg: 0.5, team_avg_ppg: 0.3 };
  const ask = skaterMap[awayTid] ?? { top_scorer_ppg: 0.5, team_avg_ppg: 0.3 };

  return buildFeatureVector(hs, aws, homeRoll, awayRoll, homeB2b, awayB2b, homeRc, awayRc, dos, homeTid, awayTid, hg, ag, hsk, ask);
}

function getDefaultStats(): TeamStats {
  return {
    gf_per_game: 3.0, ga_per_game: 3.0, pp_pct: 0.20, pk_pct: 0.80,
    fo_pct: 0.50, sf_per_game: 30.0, sa_per_game: 30.0, point_pct: 0.50,
    wins: 0, losses: 0, ot_losses: 0, goals_for: 0, goals_against: 0,
    sat_pct: 0.50, pp_opp_per_game: 2.5, tsh_per_game: 3.0, es_gf_per_game: 1.8,
  };
}

function checkBackToBack(teamId: number, gameDate: Date, games: GameInfo[]): number {
  const prev = new Date(gameDate);
  prev.setDate(prev.getDate() - 1);
  const prevStr = prev.toISOString().slice(0, 10);
  for (const g of games) {
    if (g.gameDate === prevStr && (g.homeTeamId === teamId || g.visitingTeamId === teamId)) {
      return 1;
    }
  }
  return 0;
}

interface PriorGame {
  date: Date;
  gf: number;
  ga: number;
  gd: number;
  win: number;
  cf: number;
  ca: number;
}

function computeRollingForTeam(teamId: number, gameDate: Date, games: GameInfo[], shotMap?: Record<number, ShotStats>): Record<string, number> {
  const prior: PriorGame[] = [];

  for (const g of games) {
    if (g.gameStateId !== 7) continue;
    const gt = g.gameType;
    if (gt !== 2 && gt !== 3) continue;
    const gd = new Date(g.gameDate);
    if (gd >= gameDate) continue;
    if (g.homeTeamId === teamId || g.visitingTeamId === teamId) {
      const gf = g.homeTeamId === teamId ? g.homeScore : g.visitingScore;
      const ga = g.homeTeamId === teamId ? g.visitingScore : g.homeScore;
      const win = gf > ga ? 1 : 0;
      let cf = 50, ca = 50;
      const sd = shotMap?.[g.id];
      if (sd) {
        cf = g.homeTeamId === teamId ? sd.home_corsi_for : sd.away_corsi_for;
        ca = g.homeTeamId === teamId ? sd.home_corsi_against : sd.away_corsi_against;
      }
      prior.push({ date: gd, gf, ga, gd: gf - ga, win, cf, ca });
    }
  }

  prior.sort((a, b) => b.date.getTime() - a.date.getTime());

  if (prior.length === 0) return {};

  const result: Record<string, number> = {};

  function expWeighted(values: number[], decay: number): number {
    if (values.length === 0) return 0;
    const n = values.length;
    const weights = values.map((_, i) => decay ** i);
    const totalWeight = weights.reduce((a, b) => a + b, 0);
    return values.reduce((sum, v, i) => sum + v * weights[i], 0) / totalWeight;
  }

  for (const [statKey, key] of [["gf", "gf"], ["ga", "ga"], ["gd", "gd"], ["win", "win"], ["cf", "cf"], ["ca", "ca"]] as const) {
    const vals = prior.map(r =>
      statKey === "gf" ? r.gf : statKey === "ga" ? r.ga : statKey === "gd" ? r.gd : statKey === "win" ? r.win : statKey === "cf" ? r.cf : r.ca
    );

    for (const w of ROLLING_WINDOWS) {
      const window = vals.slice(0, w);
      result[`${key}_roll${w}`] = window.reduce((a, b) => a + b, 0) / window.length;
    }

    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      result[`${key}_decay${label}`] = expWeighted(vals, d);
    }
  }

  // cd = cf - ca
  {
    const cfVals = prior.map(r => r.cf);
    const caVals = prior.map(r => r.ca);
    const cdVals = cfVals.map((v, i) => v - caVals[i]);
    for (const w of ROLLING_WINDOWS) {
      const window = cdVals.slice(0, w);
      result[`cd_roll${w}`] = window.reduce((a, b) => a + b, 0) / window.length;
    }
    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      result[`cd_decay${label}`] = expWeighted(cdVals, d);
    }
  }

  const dayDiff = Math.round((gameDate.getTime() - prior[0].date.getTime()) / (1000 * 60 * 60 * 24));
  result["rest_days"] = dayDiff;

  return result;
}

function buildGoalieMap(raw: any): Record<number, { goalie_sv_pct: number; goalie_gaa: number }> {
  const teamGoalies: Record<number, Array<{ gs: number; sv_pct: number; gaa: number }>> = {};
  if (raw?.data) {
    for (const g of raw.data) {
      const teams = (g.teamAbbrevs ?? "").split(",").map((s: string) => s.trim());
      for (const abbrev of teams) {
        const tid = TEAM_ABBREV_TO_ID[abbrev];
        if (!tid) continue;
        if (!teamGoalies[tid]) teamGoalies[tid] = [];
        teamGoalies[tid].push({ gs: g.gamesStarted ?? 0, sv_pct: g.savePct ?? 0.0, gaa: g.goalsAgainstAverage ?? 3.0 });
      }
    }
  }

  const result: Record<number, { goalie_sv_pct: number; goalie_gaa: number }> = {};
  for (const [tidStr, goalies] of Object.entries(teamGoalies)) {
    const tid = Number(tidStr);
    const eligible = goalies.filter(g => g.gs >= 10);
    if (eligible.length === 0) {
      result[tid] = { goalie_sv_pct: 0.900, goalie_gaa: 3.0 };
      continue;
    }
    eligible.sort((a, b) => b.gs - a.gs);
    result[tid] = { goalie_sv_pct: eligible[0].sv_pct, goalie_gaa: eligible[0].gaa };
  }
  return result;
}

function buildSkaterMap(raw: any): Record<number, { top_scorer_ppg: number; team_avg_ppg: number }> {
  const teamSkaters: Record<number, Array<{ gp: number; ppg: number; points: number }>> = {};
  if (raw?.data) {
    for (const s of raw.data) {
      const teams = (s.teamAbbrevs ?? "").split(",").map((a: string) => a.trim());
      for (const abbrev of teams) {
        const tid = TEAM_ABBREV_TO_ID[abbrev];
        if (!tid) continue;
        if (!teamSkaters[tid]) teamSkaters[tid] = [];
        teamSkaters[tid].push({ gp: s.gamesPlayed ?? 0, ppg: s.pointsPerGame ?? 0.0, points: s.points ?? 0 });
      }
    }
  }

  const result: Record<number, { top_scorer_ppg: number; team_avg_ppg: number }> = {};
  for (const [tidStr, skaters] of Object.entries(teamSkaters)) {
    const tid = Number(tidStr);
    const eligible = skaters.filter(s => s.gp >= 10);
    if (eligible.length === 0) {
      result[tid] = { top_scorer_ppg: 0.5, team_avg_ppg: 0.3 };
      continue;
    }
    eligible.sort((a, b) => b.ppg - a.ppg);
    const totalP = eligible.reduce((sum, s) => sum + s.points, 0);
    const totalGP = eligible.reduce((sum, s) => sum + s.gp, 0);
    result[tid] = { top_scorer_ppg: eligible[0].ppg, team_avg_ppg: totalGP > 0 ? totalP / totalGP : 0.3 };
  }
  return result;
}

function buildRollingPrefixes(): string[] {
  const p: string[] = [];
  for (const w of ROLLING_WINDOWS) p.push(`gf_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`ga_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`gd_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`win_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`cf_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`ca_roll${w}`);
  for (const w of ROLLING_WINDOWS) p.push(`cd_roll${w}`);
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`gf_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`ga_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`gd_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`win_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`cf_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`ca_decay${label}`);
  }
  for (const d of DECAY_FACTORS) {
    const label = String(d).replace(".", "");
    p.push(`cd_decay${label}`);
  }
  p.push("rest_days");
  return p;
}

const ROLLING_PREFIXES = buildRollingPrefixes();

function buildRollingRecord(stats: TeamStats, roll: Record<string, number>, wp: number, cf: number, ca: number): Record<string, number> {
  const result: Record<string, number> = {};
  for (const sfx of ROLLING_PREFIXES) {
    if (sfx === "rest_days") {
      result[sfx] = roll[sfx] ?? 3;
      continue;
    }
    const val = roll[sfx];
    if (val !== undefined) {
      result[sfx] = val;
      continue;
    }
    if (sfx.startsWith("gf_")) result[sfx] = stats.gf_per_game;
    else if (sfx.startsWith("ga_")) result[sfx] = stats.ga_per_game;
    else if (sfx.startsWith("gd_")) result[sfx] = stats.gf_per_game - stats.ga_per_game;
    else if (sfx.startsWith("cf_")) result[sfx] = cf;
    else if (sfx.startsWith("ca_")) result[sfx] = ca;
    else if (sfx.startsWith("cd_")) result[sfx] = cf - ca;
    else result[sfx] = wp;
  }
  return result;
}

function buildFeatureVector(
  hs: TeamStats, aws: TeamStats,
  homeRoll: Record<string, number>, awayRoll: Record<string, number>,
  homeB2b: number, awayB2b: number,
  homeRc: number, awayRc: number,
  dos: number,
  homeTid: number, awayTid: number,
  hg: { goalie_sv_pct: number; goalie_gaa: number },
  ag: { goalie_sv_pct: number; goalie_gaa: number },
  hsk: { top_scorer_ppg: number; team_avg_ppg: number },
  ask: { top_scorer_ppg: number; team_avg_ppg: number },
): number[] {
  const hWp = winPct(hs);
  const aWp = winPct(aws);

  const hGfPerGame = hs.gf_per_game;
  const hGaPerGame = hs.ga_per_game;
  const hAvgGf = hs.goals_for / Math.max(1, hs.wins + hs.losses + hs.ot_losses);
  const hAvgGa = hs.goals_against / Math.max(1, hs.wins + hs.losses + hs.ot_losses);
  const aAvgGf = aws.goals_for / Math.max(1, aws.wins + aws.losses + aws.ot_losses);
  const aAvgGa = aws.goals_against / Math.max(1, aws.wins + aws.losses + aws.ot_losses);

  const gfDiff = hAvgGf - aAvgGa;
  const gaDiff = hAvgGa - aAvgGf;
  const netDiff = (hAvgGf - hAvgGa) - (aAvgGf - aAvgGa);
  const stDiff = hs.pp_pct - aws.pk_pct;
  const hCorsi = (hs.sf_per_game - hs.sa_per_game) / Math.max(1, hs.sf_per_game + hs.sa_per_game);
  const aCorsi = (aws.sf_per_game - aws.sa_per_game) / Math.max(1, aws.sf_per_game + aws.sa_per_game);
  const shotDiff = (hs.sf_per_game - hs.sa_per_game) - (aws.sf_per_game - aws.sa_per_game);
  const corsiDiff = hCorsi - aCorsi;
  const foDiff = hs.fo_pct - aws.fo_pct;
  const ppDiff = hs.pp_pct - aws.pp_pct;
  const pkDiff = hs.pk_pct - aws.pk_pct;

  const travelMiles = travelDistanceMiles(homeTid, awayTid);
  const tz = tzCrossed(homeTid, awayTid);
  const altAdv = altitudeAdvantageFt(homeTid, awayTid);
  const highAlt = highAltitudeHome(homeTid);

  const homeRollRecord = buildRollingRecord(hs, homeRoll, hWp, 50, 50);
  const awayRollRecord = buildRollingRecord(aws, awayRoll, aWp, 50, 50);

  const featureDict: Record<string, number> = {
    "home_gf_per_game": hGfPerGame, "home_ga_per_game": hGaPerGame,
    "home_pp_pct": hs.pp_pct, "home_pk_pct": hs.pk_pct,
    "home_fo_pct": hs.fo_pct, "home_sf_per_game": hs.sf_per_game,
    "home_sa_per_game": hs.sa_per_game, "home_point_pct": hs.point_pct,
    "away_gf_per_game": aws.gf_per_game, "away_ga_per_game": aws.ga_per_game,
    "away_pp_pct": aws.pp_pct, "away_pk_pct": aws.pk_pct,
    "away_fo_pct": aws.fo_pct, "away_sf_per_game": aws.sf_per_game,
    "away_sa_per_game": aws.sa_per_game, "away_point_pct": aws.point_pct,
    "home_win_pct": hWp, "away_win_pct": aWp,
    "gf_diff": gfDiff, "ga_diff": gaDiff, "net_diff": netDiff,
    "st_diff": stDiff, "shot_diff": shotDiff,
    "corsi_diff": corsiDiff, "fo_diff": foDiff, "pp_diff": ppDiff,
    "pk_diff": pkDiff,
    "home_b2b": homeB2b, "away_b2b": awayB2b,
    "travel_miles": travelMiles, "tz_crossed": tz, "alt_advantage": altAdv,
    "high_alt_home": highAlt,
    "home_goalie_sv_pct": hg.goalie_sv_pct, "away_goalie_sv_pct": ag.goalie_sv_pct,
    "home_goalie_gaa": hg.goalie_gaa, "away_goalie_gaa": ag.goalie_gaa,
    "home_top_scorer_ppg": hsk.top_scorer_ppg, "away_top_scorer_ppg": ask.top_scorer_ppg,
    "home_team_avg_ppg": hsk.team_avg_ppg, "away_team_avg_ppg": ask.team_avg_ppg,
    "home_sat_pct": hs.sat_pct, "away_sat_pct": aws.sat_pct,
    "home_pp_opp_per_game": hs.pp_opp_per_game, "away_pp_opp_per_game": aws.pp_opp_per_game,
    "home_tsh_per_game": hs.tsh_per_game, "away_tsh_per_game": aws.tsh_per_game,
    "home_es_gf_per_game": hs.es_gf_per_game, "away_es_gf_per_game": aws.es_gf_per_game,
    "home_rest_cat": homeRc, "away_rest_cat": awayRc, "day_of_season": dos,
  };
  for (const sfx of ROLLING_PREFIXES) {
    featureDict[`home_${sfx}`] = homeRollRecord[sfx];
  }
  for (const sfx of ROLLING_PREFIXES) {
    featureDict[`away_${sfx}`] = awayRollRecord[sfx];
  }

  return Object.entries(featureDict)
    .filter(([k]) => !EXCLUDED_FEATURES.has(k))
    .map(([_, v]) => v);
}

function winPct(s: TeamStats): number {
  const total = s.wins + s.losses + s.ot_losses;
  return total > 0 ? s.wins / total : 0.5;
}
