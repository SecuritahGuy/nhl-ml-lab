import math

TEAM_ABBREV_TO_ID = {
    "NJD": 1, "NYI": 2, "NYR": 3, "PHI": 4, "PIT": 5,
    "BOS": 6, "BUF": 7, "MTL": 8, "OTT": 9, "TOR": 10,
    "CAR": 12, "FLA": 13, "TBL": 14, "WSH": 15,
    "CHI": 16, "DET": 17, "NSH": 18, "STL": 19,
    "CGY": 20, "COL": 21, "EDM": 22, "VAN": 23,
    "ANA": 24, "DAL": 25, "LAK": 26,
    "SJS": 28, "CBJ": 29, "MIN": 30,
    "WPG": 52, "VGK": 54, "SEA": 55, "UTA": 59,
}

TEAM_LOCATIONS = {
    1: {"city": "Newark", "tz": "America/New_York", "utc_offset": -5, "lat": 40.7336, "lon": -74.1711, "alt_ft": 0},
    2: {"city": "Elmont", "tz": "America/New_York", "utc_offset": -5, "lat": 40.7117, "lon": -73.7269, "alt_ft": 0},
    3: {"city": "New York", "tz": "America/New_York", "utc_offset": -5, "lat": 40.7505, "lon": -73.9934, "alt_ft": 0},
    4: {"city": "Philadelphia", "tz": "America/New_York", "utc_offset": -5, "lat": 39.9012, "lon": -75.1712, "alt_ft": 0},
    5: {"city": "Pittsburgh", "tz": "America/New_York", "utc_offset": -5, "lat": 40.4396, "lon": -79.9973, "alt_ft": 0},
    6: {"city": "Boston", "tz": "America/New_York", "utc_offset": -5, "lat": 42.3663, "lon": -71.0623, "alt_ft": 0},
    7: {"city": "Buffalo", "tz": "America/New_York", "utc_offset": -5, "lat": 42.8750, "lon": -78.8767, "alt_ft": 0},
    8: {"city": "Montreal", "tz": "America/Montreal", "utc_offset": -5, "lat": 45.4952, "lon": -73.5771, "alt_ft": 0},
    9: {"city": "Ottawa", "tz": "America/Toronto", "utc_offset": -5, "lat": 45.2962, "lon": -75.6812, "alt_ft": 0},
    10: {"city": "Toronto", "tz": "America/Toronto", "utc_offset": -5, "lat": 43.6435, "lon": -79.3785, "alt_ft": 0},
    12: {"city": "Raleigh", "tz": "America/New_York", "utc_offset": -5, "lat": 35.7721, "lon": -78.6386, "alt_ft": 0},
    13: {"city": "Sunrise", "tz": "America/New_York", "utc_offset": -5, "lat": 26.1582, "lon": -80.3256, "alt_ft": 0},
    14: {"city": "Tampa", "tz": "America/New_York", "utc_offset": -5, "lat": 27.9428, "lon": -82.4518, "alt_ft": 0},
    15: {"city": "Washington", "tz": "America/New_York", "utc_offset": -5, "lat": 38.8981, "lon": -77.0208, "alt_ft": 0},
    16: {"city": "Chicago", "tz": "America/Chicago", "utc_offset": -6, "lat": 41.8806, "lon": -87.6321, "alt_ft": 0},
    17: {"city": "Detroit", "tz": "America/Detroit", "utc_offset": -5, "lat": 42.3333, "lon": -83.0484, "alt_ft": 0},
    18: {"city": "Nashville", "tz": "America/Chicago", "utc_offset": -6, "lat": 36.1591, "lon": -86.7784, "alt_ft": 0},
    19: {"city": "St. Louis", "tz": "America/Chicago", "utc_offset": -6, "lat": 38.6258, "lon": -90.2057, "alt_ft": 0},
    20: {"city": "Calgary", "tz": "America/Edmonton", "utc_offset": -7, "lat": 51.0375, "lon": -114.0524, "alt_ft": 3428},
    21: {"city": "Denver", "tz": "America/Denver", "utc_offset": -7, "lat": 39.7485, "lon": -104.9961, "alt_ft": 5280},
    22: {"city": "Edmonton", "tz": "America/Edmonton", "utc_offset": -7, "lat": 53.5449, "lon": -113.4909, "alt_ft": 2192},
    23: {"city": "Vancouver", "tz": "America/Vancouver", "utc_offset": -8, "lat": 49.2777, "lon": -123.1087, "alt_ft": 0},
    24: {"city": "Anaheim", "tz": "America/Los_Angeles", "utc_offset": -8, "lat": 33.8076, "lon": -117.8771, "alt_ft": 0},
    25: {"city": "Dallas", "tz": "America/Chicago", "utc_offset": -6, "lat": 32.7906, "lon": -96.8102, "alt_ft": 0},
    26: {"city": "Los Angeles", "tz": "America/Los_Angeles", "utc_offset": -8, "lat": 34.0430, "lon": -118.2670, "alt_ft": 0},
    28: {"city": "San Jose", "tz": "America/Los_Angeles", "utc_offset": -8, "lat": 37.3327, "lon": -121.9020, "alt_ft": 0},
    29: {"city": "Columbus", "tz": "America/New_York", "utc_offset": -5, "lat": 39.9692, "lon": -82.9985, "alt_ft": 0},
    30: {"city": "Saint Paul", "tz": "America/Chicago", "utc_offset": -6, "lat": 44.9438, "lon": -93.1011, "alt_ft": 0},
    52: {"city": "Winnipeg", "tz": "America/Winnipeg", "utc_offset": -6, "lat": 49.8076, "lon": -97.1434, "alt_ft": 0},
    54: {"city": "Las Vegas", "tz": "America/Los_Angeles", "utc_offset": -8, "lat": 36.1154, "lon": -115.1777, "alt_ft": 0},
    55: {"city": "Seattle", "tz": "America/Los_Angeles", "utc_offset": -8, "lat": 47.5917, "lon": -122.3309, "alt_ft": 0},
    59: {"city": "Salt Lake City", "tz": "America/Denver", "utc_offset": -7, "lat": 40.7683, "lon": -111.9012, "alt_ft": 4265},
}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def travel_distance_miles(home_team_id: int, away_team_id: int) -> float:
    hl = TEAM_LOCATIONS.get(home_team_id)
    al = TEAM_LOCATIONS.get(away_team_id)
    if not hl or not al:
        return 0.0
    return haversine_miles(hl["lat"], hl["lon"], al["lat"], al["lon"])


def tz_crossed(home_team_id: int, away_team_id: int) -> int:
    hl = TEAM_LOCATIONS.get(home_team_id)
    al = TEAM_LOCATIONS.get(away_team_id)
    if not hl or not al:
        return 0
    return abs(hl["utc_offset"] - al["utc_offset"])


def altitude_advantage_ft(home_team_id: int, away_team_id: int) -> int:
    hl = TEAM_LOCATIONS.get(home_team_id)
    al = TEAM_LOCATIONS.get(away_team_id)
    if not hl or not al:
        return 0
    return hl["alt_ft"] - al["alt_ft"]


def high_altitude_home(home_team_id: int) -> int:
    loc = TEAM_LOCATIONS.get(home_team_id)
    if not loc:
        return 0
    return 1 if loc["alt_ft"] >= 3000 else 0
