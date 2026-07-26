// Feature count: 52 base + 29 rolling×2 = 110 features
import { TeamStats, GameInfo, fetchTeamStats, fetchSeasonGames, fetchGoalieStats, fetchSkaterStats } from "./_nhl";
import { TEAM_ABBREV_TO_ID } from "./_locations";
import { travelDistanceMiles, tzCrossed, altitudeAdvantageFt, highAltitudeHome } from "./_locations";

const ROLLING_WINDOWS = [3, 5, 10, 20];
const DECAY_FACTORS = [0.7, 0.8, 0.9];

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

  const homeRoll = computeRollingForTeam(homeTid, gd, games);
  const awayRoll = computeRollingForTeam(awayTid, gd, games);

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
}

function computeRollingForTeam(teamId: number, gameDate: Date, games: GameInfo[]): Record<string, number> {
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
      prior.push({ date: gd, gf, ga, gd: gf - ga, win });
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

  for (const [statKey, key] of [["gf", "gf"], ["ga", "ga"], ["gd", "gd"], ["win", "win"]] as const) {
    const vals = prior.map(r => statKey === "gf" ? r.gf : statKey === "ga" ? r.ga : statKey === "gd" ? r.gd : r.win);

    for (const w of ROLLING_WINDOWS) {
      const window = vals.slice(0, w);
      result[`${key}_roll${w}`] = window.reduce((a, b) => a + b, 0) / window.length;
    }

    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      result[`${key}_decay${label}`] = expWeighted(vals, d);
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

  const fts: number[] = [
    hGfPerGame, hGaPerGame, hs.pp_pct, hs.pk_pct,
    hs.fo_pct, hs.sf_per_game, hs.sa_per_game, hs.point_pct,
    aws.gf_per_game, aws.ga_per_game, aws.pp_pct, aws.pk_pct,
    aws.fo_pct, aws.sf_per_game, aws.sa_per_game, aws.point_pct,
    hWp, aWp,
    gfDiff, gaDiff, netDiff, stDiff, shotDiff,
    corsiDiff, foDiff, ppDiff, pkDiff,
    homeB2b, awayB2b, travelMiles, tz, altAdv, highAlt,
    hg.goalie_sv_pct, ag.goalie_sv_pct,
    hg.goalie_gaa, ag.goalie_gaa,
    hsk.top_scorer_ppg, ask.top_scorer_ppg,
    hsk.team_avg_ppg, ask.team_avg_ppg,
    hs.sat_pct, aws.sat_pct,
    hs.pp_opp_per_game, aws.pp_opp_per_game,
    hs.tsh_per_game, aws.tsh_per_game,
    hs.es_gf_per_game, aws.es_gf_per_game,
    homeRc, awayRc, dos,
  ];

  function buildRollingArray(stats: TeamStats, roll: Record<string, number>, wp: number): number[] {
    const out: number[] = [];
    const allPrefixes: string[] = [];
    for (const w of ROLLING_WINDOWS) allPrefixes.push(`gf_roll${w}`);
    for (const w of ROLLING_WINDOWS) allPrefixes.push(`ga_roll${w}`);
    for (const w of ROLLING_WINDOWS) allPrefixes.push(`gd_roll${w}`);
    for (const w of ROLLING_WINDOWS) allPrefixes.push(`win_roll${w}`);
    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      allPrefixes.push(`gf_decay${label}`);
    }
    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      allPrefixes.push(`ga_decay${label}`);
    }
    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      allPrefixes.push(`gd_decay${label}`);
    }
    for (const d of DECAY_FACTORS) {
      const label = String(d).replace(".", "");
      allPrefixes.push(`win_decay${label}`);
    }
    allPrefixes.push("rest_days");

    for (const sfx of allPrefixes) {
      if (sfx === "rest_days") {
        out.push(roll[sfx] ?? 3);
        continue;
      }
      const val = roll[sfx];
      if (val !== undefined) {
        out.push(val);
        continue;
      }
      if (sfx.startsWith("gf_")) out.push(stats.gf_per_game);
      else if (sfx.startsWith("ga_")) out.push(stats.ga_per_game);
      else if (sfx.startsWith("gd_")) out.push(stats.gf_per_game - stats.ga_per_game);
      else out.push(wp);
    }
    return out;
  }

  fts.push(...buildRollingArray(hs, homeRoll, hWp));
  fts.push(...buildRollingArray(aws, awayRoll, aWp));

  return fts;
}

function winPct(s: TeamStats): number {
  const total = s.wins + s.losses + s.ot_losses;
  return total > 0 ? s.wins / total : 0.5;
}
