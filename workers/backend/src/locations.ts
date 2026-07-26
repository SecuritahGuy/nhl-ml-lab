export interface TeamLocation {
  city: string;
  utcOffset: number;
  lat: number;
  lon: number;
  altFt: number;
}

export const TEAM_LOCATIONS: Record<number, TeamLocation> = {
  1:  { city: "Newark",       utcOffset: -5, lat: 40.7336, lon: -74.1711, altFt: 0 },
  2:  { city: "Elmont",       utcOffset: -5, lat: 40.7117, lon: -73.7269, altFt: 0 },
  3:  { city: "New York",     utcOffset: -5, lat: 40.7505, lon: -73.9934, altFt: 0 },
  4:  { city: "Philadelphia", utcOffset: -5, lat: 39.9012, lon: -75.1712, altFt: 0 },
  5:  { city: "Pittsburgh",   utcOffset: -5, lat: 40.4396, lon: -79.9973, altFt: 0 },
  6:  { city: "Boston",       utcOffset: -5, lat: 42.3663, lon: -71.0623, altFt: 0 },
  7:  { city: "Buffalo",      utcOffset: -5, lat: 42.8750, lon: -78.8767, altFt: 0 },
  8:  { city: "Montreal",     utcOffset: -5, lat: 45.4952, lon: -73.5771, altFt: 0 },
  9:  { city: "Ottawa",       utcOffset: -5, lat: 45.2962, lon: -75.6812, altFt: 0 },
  10: { city: "Toronto",      utcOffset: -5, lat: 43.6435, lon: -79.3785, altFt: 0 },
  12: { city: "Raleigh",      utcOffset: -5, lat: 35.7721, lon: -78.6386, altFt: 0 },
  13: { city: "Sunrise",      utcOffset: -5, lat: 26.1582, lon: -80.3256, altFt: 0 },
  14: { city: "Tampa",        utcOffset: -5, lat: 27.9428, lon: -82.4518, altFt: 0 },
  15: { city: "Washington",   utcOffset: -5, lat: 38.8981, lon: -77.0208, altFt: 0 },
  16: { city: "Chicago",      utcOffset: -6, lat: 41.8806, lon: -87.6321, altFt: 0 },
  17: { city: "Detroit",      utcOffset: -5, lat: 42.3333, lon: -83.0484, altFt: 0 },
  18: { city: "Nashville",    utcOffset: -6, lat: 36.1591, lon: -86.7784, altFt: 0 },
  19: { city: "St. Louis",    utcOffset: -6, lat: 38.6258, lon: -90.2057, altFt: 0 },
  20: { city: "Calgary",      utcOffset: -7, lat: 51.0375, lon: -114.0524, altFt: 3428 },
  21: { city: "Denver",       utcOffset: -7, lat: 39.7485, lon: -104.9961, altFt: 5280 },
  22: { city: "Edmonton",     utcOffset: -7, lat: 53.5449, lon: -113.4909, altFt: 2192 },
  23: { city: "Vancouver",    utcOffset: -8, lat: 49.2777, lon: -123.1087, altFt: 0 },
  24: { city: "Anaheim",      utcOffset: -8, lat: 33.8076, lon: -117.8771, altFt: 0 },
  25: { city: "Dallas",       utcOffset: -6, lat: 32.7906, lon: -96.8102, altFt: 0 },
  26: { city: "Los Angeles",  utcOffset: -8, lat: 34.0430, lon: -118.2670, altFt: 0 },
  28: { city: "San Jose",     utcOffset: -8, lat: 37.3327, lon: -121.9020, altFt: 0 },
  29: { city: "Columbus",     utcOffset: -5, lat: 39.9692, lon: -82.9985, altFt: 0 },
  30: { city: "Saint Paul",   utcOffset: -6, lat: 44.9438, lon: -93.1011, altFt: 0 },
  52: { city: "Winnipeg",     utcOffset: -6, lat: 49.8076, lon: -97.1434, altFt: 0 },
  54: { city: "Las Vegas",    utcOffset: -8, lat: 36.1154, lon: -115.1777, altFt: 0 },
  55: { city: "Seattle",      utcOffset: -8, lat: 47.5917, lon: -122.3309, altFt: 0 },
  59: { city: "Salt Lake City", utcOffset: -7, lat: 40.7683, lon: -111.9012, altFt: 4265 },
};

export const TEAM_ABBREV_TO_ID: Record<string, number> = {
  NJD: 1, NYI: 2, NYR: 3, PHI: 4, PIT: 5,
  BOS: 6, BUF: 7, MTL: 8, OTT: 9, TOR: 10,
  CAR: 12, FLA: 13, TBL: 14, WSH: 15,
  CHI: 16, DET: 17, NSH: 18, STL: 19,
  CGY: 20, COL: 21, EDM: 22, VAN: 23,
  ANA: 24, DAL: 25, LAK: 26,
  SJS: 28, CBJ: 29, MIN: 30,
  WPG: 52, VGK: 54, SEA: 55, UTA: 59,
};

function haversineMiles(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 3958.8;
  const dlat = (lat2 - lat1) * Math.PI / 180;
  const dlon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dlat / 2) ** 2
    + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180)
    * Math.sin(dlon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function travelDistanceMiles(homeTeamId: number, awayTeamId: number): number {
  const hl = TEAM_LOCATIONS[homeTeamId];
  const al = TEAM_LOCATIONS[awayTeamId];
  if (!hl || !al) return 0;
  return haversineMiles(hl.lat, hl.lon, al.lat, al.lon);
}

export function tzCrossed(homeTeamId: number, awayTeamId: number): number {
  const hl = TEAM_LOCATIONS[homeTeamId];
  const al = TEAM_LOCATIONS[awayTeamId];
  if (!hl || !al) return 0;
  return Math.abs(hl.utcOffset - al.utcOffset);
}

export function altitudeAdvantageFt(homeTeamId: number, awayTeamId: number): number {
  const hl = TEAM_LOCATIONS[homeTeamId];
  const al = TEAM_LOCATIONS[awayTeamId];
  if (!hl || !al) return 0;
  return hl.altFt - al.altFt;
}

export function highAltitudeHome(homeTeamId: number): number {
  const loc = TEAM_LOCATIONS[homeTeamId];
  if (!loc) return 0;
  return loc.altFt >= 3000 ? 1 : 0;
}
