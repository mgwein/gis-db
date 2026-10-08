"""Generate the gis-db practice data set and its independent answer key.

Practice material only: nothing here is part of the service. The script stands in for the
files an interview would provide, and it computes the answers a correct build must reproduce.
The design is in practice/DESIGN.md section 7 (recipe 7.4, scenarios 7.5, expected results
7.6, answer key and method 7.7).

Run it from the repository root:

    uv run --no-project --with geographiclib python practice/generate_sample_data.py

It writes exactly four files, overwriting them, and nothing else:

    data/flights.json                 15 flight records: 10 valid, 1 exact duplicate, 4 invalid
    data/zones.json                   11 circular zones (GeoJSON points + radius), 1 invalid
    practice/redelivery/flights.json  the 10 valid flights with 2 changes (ingestion run 3)
    practice/answer_key.json          expected ingestion, metrics, passes and intersections

Stdout is a self-check report: one line per scenario (D1-D7 data gotchas, S1-S10 flight x
zone geometry, X1-X8 flight x flight geometry), one line comparing the whole found result set
with the expected one, and the last line "SELF-CHECK OK (25 scenarios)". Any FAIL exits 1.

Part 1 builds the data. Flights fly great circles between real airport coordinates at
constant speed and report a position every few minutes, with [lon, lat] rounded to 6 decimals
and times truncated to whole seconds. The geometry is planted on purpose: starts and ends
inside zones, a reporting gap whose great-circle arc bulges into one zone while a straight
lat/lon line would hit another, polar and antimeridian zones, a zone touched at one point,
zones missed by 5 m and entered 5 m deep, a vertex exactly on a boundary, a route flown both
ways, a shared waypoint and a shared endpoint. The only randomness is the shuffle of FLT-1006's
positions, seeded with SEED, so every run writes byte-identical files.

Part 2 reads the written files back and computes the key with its own code. It never imports
the service package (gisdb) and uses no closed-form circle or arc intersection formula, so it
checks the service's geometry instead of repeating it:
  - normalization: [lon, lat] order, UTC, feet and nautical miles, sorting, duplicate
    removal, and the rejection reason codes;
  - ingestion runs 1-3 replayed with the accounting
    seen = inserted + updated + unchanged + duplicates + rejected;
  - lengths from geographiclib on an exact sphere, checked against an n-vector sum;
  - zone passes by sampling every segment at most 0.5 km apart, bisecting boundary
    crossings and refining every closest approach by golden-section search;
  - intersections by testing every vertex against the other track's arcs, then sampling
    each nearby segment pair and bisecting sign changes of the distance to the other
    track's great circle.

The model is the one the brief states: a sphere of radius 6371.0088 km; between two reports
a flight follows the shorter great-circle arc at constant speed; a zone is a closed disc;
1 m is the tolerance for every boundary, touch, same-point and merge decision.
"""

import copy
import hashlib
import json
import math
import random
import sys
from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

from geographiclib.geodesic import Geodesic

# ------------------------------------------------------------------------------ constants

SEED = 20240501  # used only to shuffle FLT-1006's positions
EARTH_RADIUS_KM = 6371.0088  # mean Earth radius: the data and the key both live on this sphere
NM_TO_KM = 1.852
FT_TO_M = 0.3048
TOL_KM = 0.001  # 1 m: touch band, same-point rule, on-arc test and merging
SAMPLE_KM = 0.5  # brute-force sampling step along every segment
SPHERE = Geodesic(EARTH_RADIUS_KM * 1000.0, 0.0)  # geographiclib on an exact sphere (metres)
DAY = datetime(2024, 5, 1, tzinfo=UTC)

REPO = Path(__file__).resolve().parent.parent
FLIGHTS_FILE = "data/flights.json"
ZONES_FILE = "data/zones.json"
REDELIVERY_FILE = "practice/redelivery/flights.json"
KEY_FILE = "practice/answer_key.json"

# ----------------------------------------------------------------------- n-vector helpers
# A position is a unit 3-vector (an "n-vector"). Points along an arc come from slerp; raw
# latitude/longitude is never interpolated or averaged.


def to_nvec(lat, lon):
    phi, lam = math.radians(lat), math.radians(lon)
    c = math.cos(phi)
    return (c * math.cos(lam), c * math.sin(lam), math.sin(phi))


def normalize_lon(lon):
    return (lon + 180.0) % 360.0 - 180.0


def from_nvec(v):
    x, y, z = v
    lat = math.degrees(math.atan2(z, math.hypot(x, y)))
    return lat, normalize_lon(math.degrees(math.atan2(y, x)))


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def angle(a, b):
    """Angle between two n-vectors in radians, accurate from 0 to pi (never acos of a dot)."""
    c = cross(a, b)
    return math.atan2(math.sqrt(dot(c, c)), dot(a, b))


def slerp(a, b, f):
    """The point at fraction f of the arc length along the minor great-circle arc a -> b."""
    theta = angle(a, b)
    if theta < 1e-12:
        return a
    u = cross(unit(cross(a, b)), a)  # unit tangent at a, pointing towards b
    ct, st = math.cos(f * theta), math.sin(f * theta)
    return (a[0] * ct + u[0] * st, a[1] * ct + u[1] * st, a[2] * ct + u[2] * st)


def gc_km(p, q):
    """Great-circle distance in km between two (lat, lon) points."""
    return EARTH_RADIUS_KM * angle(to_nvec(*p), to_nvec(*q))


# ==========================================================================================
# Part 1: the data (DESIGN.md section 7.4)
# ==========================================================================================

AIRPORTS = {  # (lat, lon)
    "EGLL": (51.4700, -0.4543),  # London Heathrow
    "KJFK": (40.6413, -73.7781),  # New York JFK
    "LFPG": (49.0097, 2.5479),  # Paris Charles de Gaulle
    "KORD": (41.9742, -87.9073),  # Chicago O'Hare
    "EDDF": (50.0379, 8.5622),  # Frankfurt
    "CYYZ": (43.6777, -79.6248),  # Toronto Pearson
    "BIKF": (63.9850, -22.6056),  # Keflavik
    "PANC": (61.1743, -149.9982),  # Anchorage
    "PAFA": (64.8151, -147.8564),  # Fairbanks
    "RJTT": (35.5494, 139.7798),  # Tokyo Haneda
    "RKSI": (37.4602, 126.4407),  # Seoul Incheon
    "ENSB": (78.2461, 15.4656),  # Longyearbyen, Svalbard
    "PABR": (71.2854, -156.7660),  # Utqiagvik, Alaska
    "CYLT": (82.5178, -62.2806),  # Alert, Nunavut
    "UEST": (71.6977, 128.9030),  # Tiksi, Siberia
}
WPT = (55.0, -45.0)  # oceanic waypoint flown by both FLT-1008 and FLT-1009
CLIMB_MIN = 20  # altitude climbs linearly to cruise over the first 20 minutes ...
DESCENT_MIN = 25  # ... and descends linearly over the last 25 minutes


def fly(route, dep, speed_kmh, step_min, cruise_ft):
    """Fly a list of (lat, lon) waypoints along great circles at constant speed.

    Reports a position every step_min minutes from departure, at each intermediate waypoint
    and at the destination. Returns [(time, lat, lon, alt_ft)]; time and coordinates are not
    rounded yet (format_ts and flight_record do that).
    """
    vecs = [to_nvec(*p) for p in route]
    legs = [EARTH_RADIUS_KM * angle(vecs[i], vecs[i + 1]) for i in range(len(vecs) - 1)]
    total_km = sum(legs)
    duration_min = total_km / speed_kmh * 60
    distances = set()
    k = 0
    while k * step_min < duration_min:
        distances.add(k * step_min * speed_kmh / 60)
        k += 1
    leg_end = 0.0
    for length in legs:
        leg_end += length
        distances.add(leg_end)  # every waypoint is a reported position
    distances.add(total_km)
    reports = []
    for s in sorted(distances):
        leg, leg_start = 0, 0.0
        while s > leg_start + legs[leg] and leg < len(legs) - 1:
            leg_start += legs[leg]
            leg += 1
        f = max(0.0, min(1.0, (s - leg_start) / legs[leg]))
        lat, lon = from_nvec(slerp(vecs[leg], vecs[leg + 1], f))
        minutes = s / speed_kmh * 60
        if minutes < CLIMB_MIN:
            alt = cruise_ft * minutes / CLIMB_MIN
        elif minutes > duration_min - DESCENT_MIN:
            alt = cruise_ft * max(0.0, (duration_min - minutes) / DESCENT_MIN)
        else:
            alt = cruise_ft
        reports.append((dep + timedelta(minutes=minutes), lat, lon, round(alt / 100) * 100))
    return reports


def format_ts(t, form):
    """Truncate to whole seconds, then write in the record's time form."""
    t = t.replace(microsecond=0)
    if form == "epoch":
        return int(t.timestamp())
    hours = {"Z": 0, "+02:00": 2, "-08:00": -8}[form]
    return t.astimezone(timezone(timedelta(hours=hours))).isoformat().replace("+00:00", "Z")


def flight_record(flight_id, callsign, icao_type, origin, destination, reports, form="Z",
                  null_alt=(), extra=None):
    """One flight record. flight_id None leaves the key out; extra adds record-level fields."""
    record = {} if flight_id is None else {"flight_id": flight_id}
    record.update(callsign=callsign, aircraft={"icao_type": icao_type}, origin=origin,
                  destination=destination)
    record.update(extra or {})
    record["positions"] = [
        {"ts": format_ts(t, form), "coord": [round(lon, 6), round(lat, 6)],
         "alt_ft": None if i in null_alt else alt}
        for i, (t, lat, lon, alt) in enumerate(reports)
    ]
    return record


def survey_reports():
    """FLT-1010: a survey pattern around ZN-SURVEY with one vertex exactly on its boundary.

    lon_b is the longitude on latitude 51.0, west of the centre (51.0, -3.0), at exactly
    9.26 km from it (200 bisection steps). Each vertex time = previous time + distance at
    220 km/h.
    """
    centre, radius_km = (51.0, -3.0), 9.26
    lo, hi = -3.2, -3.0  # outside ... centre
    for _ in range(200):
        mid = (lo + hi) / 2
        if gc_km((51.0, mid), centre) > radius_km:
            lo = mid
        else:
            hi = mid
    lon_b = (lo + hi) / 2
    vertices = [(50.95, -3.2), (50.95, -2.8), (51.0, -2.8), (51.0, lon_b), (51.0, -3.2),
                (51.05, -3.2), (51.05, -2.8)]
    t = DAY + timedelta(hours=8)
    reports = []
    for i, p in enumerate(vertices):
        if i:
            t = t + timedelta(minutes=gc_km(vertices[i - 1], p) / 220 * 60)
        reports.append((t, p[0], p[1], 1500))
    return reports


def perp_centre(reports, i, offset_km):
    """Zone centre offset_km to the right of the midpoint of segment i of a flight.

    The segment's endpoints are rounded to 6 decimals first (as written to the file), so the
    planted distance holds for the data the service reads.
    """
    a = (round(reports[i][1], 6), round(reports[i][2], 6))
    b = (round(reports[i + 1][1], 6), round(reports[i + 1][2], 6))
    m = from_nvec(slerp(to_nvec(*a), to_nvec(*b), 0.5))
    azi = SPHERE.Inverse(m[0], m[1], b[0], b[1])["azi1"]
    d = SPHERE.Direct(m[0], m[1], azi + 90.0, offset_km * 1000.0)
    return round(d["lat2"], 6), round(normalize_lon(d["lon2"]), 6)


def zone_feature(zone_id, name, lat, lon, radius, unit):
    return {
        "type": "Feature",
        "id": zone_id,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"name": name, "radius": radius, "radius_unit": unit},
    }


def build_data():
    """Return the three data documents: flights, zones and the redelivery for run 3."""
    ap = AIRPORTS

    def at(hour, minute=0):
        return DAY + timedelta(hours=hour, minutes=minute)

    # --- The ten valid flights (route, departure UTC, km/h, report step in minutes, cruise ft).
    # FLT-1001 London -> New York starts at the centre of ZN-LHR (S1) and ends at the centre
    # of ZN-JFK (S2). Its first coord [-0.4543, 51.47] is the [lon, lat] landmark (D1).
    f1001 = fly([ap["EGLL"], ap["KJFK"]], at(9), 880, 15, 37000)
    # FLT-1002 flies the same great circle back: starts inside ZN-JFK, ends inside ZN-LHR
    # (S2), and with FLT-1001 forms one shared stretch, reported as an overlap pair (X1).
    f1002 = fly([ap["KJFK"], ap["EGLL"]], at(13, 5), 900, 15, 38000)
    # FLT-1003 Keflavik -> Anchorage loses its reports between 12:00 and 15:00. The 2,550 km
    # gap segment bulges north over ZN-PITUFFIK with no report inside it (S3), while a
    # straight lat/lon line between the gap's ends would cross ZN-BAFFIN instead (S4).
    # Positions 2 and 3 get null altitudes (D6). It ends at Anchorage, where FLT-1007
    # starts (X6).
    f1003 = [r for r in fly([ap["BIKF"], ap["PANC"]], at(11), 850, 15, 36000)
             if not at(12) < r[0] < at(15)]
    # FLT-1004 Svalbard -> Utqiagvik and FLT-1005 Alert -> Tiksi both cross the North Pole
    # zone (S5) and each other near the pole (X3). FLT-1004 uses epoch seconds (D3).
    f1004 = fly([ap["ENSB"], ap["PABR"]], at(6), 820, 20, 35000)
    f1005 = fly([ap["CYLT"], ap["UEST"]], at(5, 30), 820, 20, 34000)
    # FLT-1006 Fairbanks -> Tokyo and FLT-1007 Anchorage -> Seoul report hourly, so their
    # segments span the antimeridian through ZN-DATELINE (S6) and cross there (X4).
    f1006 = fly([ap["PAFA"], ap["RJTT"]], at(2), 870, 60, 39000)
    f1007 = fly([ap["PANC"], ap["RKSI"]], at(2, 40), 860, 60, 37000)
    # FLT-1008 Paris -> WPT -> Chicago and FLT-1009 Frankfurt -> WPT -> Toronto share the
    # waypoint, which FLT-1009 reaches exactly 30 s after FLT-1008 (X2): FLT-1009's
    # departure is solved for that. FLT-1008 crosses FLT-1001 and FLT-1002 west of Ireland
    # (X5) and the survey pattern (X7), and passes 0.236 km outside ZN-SURVEY (an unplanted
    # near miss: no pass). FLT-1009 never comes within 139 km of FLT-1001 (X8).
    f1008 = fly([ap["LFPG"], WPT, ap["KORD"]], at(10), 880, 15, 36000)
    t_wp_1008 = at(10) + timedelta(minutes=gc_km(ap["LFPG"], WPT) / 880 * 60)
    dep_1009 = (t_wp_1008 + timedelta(seconds=30)
                - timedelta(minutes=gc_km(ap["EDDF"], WPT) / 870 * 60))
    f1009 = fly([ap["EDDF"], WPT, ap["CYYZ"]], dep_1009, 870, 15, 37000)
    # FLT-1010 flies a survey pattern with one vertex on the boundary of ZN-SURVEY (S10).
    f1010 = survey_reports()

    flights = [
        flight_record("FLT-1001", "PRAC101", "B77W", "EGLL", "KJFK", f1001),
        flight_record("FLT-1002", "PRAC102", "B772", "KJFK", "EGLL", f1002),
        flight_record("FLT-1003", "PRAC103", "B38M", "BIKF", "PANC", f1003, null_alt=(2, 3)),
        flight_record("FLT-1004", "PRAC104", "A332", "ENSB", "PABR", f1004, form="epoch"),
        flight_record("FLT-1005", "PRAC105", "B763", "CYLT", "UEST", f1005),
        flight_record("FLT-1006", "PRAC106", "B788", "PAFA", "RJTT", f1006),
        flight_record("FLT-1007", "PRAC107", "B748", "PANC", "RKSI", f1007, form="-08:00"),
        flight_record("FLT-1008", "PRAC108", "A359", "LFPG", "KORD", f1008,
                      extra={"squawk": "7000"}),  # an unknown field (D5)
        flight_record("FLT-1009", "PRAC109", "A346", "EDDF", "CYYZ", f1009, form="+02:00"),
        flight_record("FLT-1010", "PRAC110", "C208", "EGFF", "EGFF", f1010),
    ]
    # D4: FLT-1005 repeats its position 3 exactly (at index 4); FLT-1006's positions are
    # shuffled.
    flights[4]["positions"].insert(4, copy.deepcopy(flights[4]["positions"][3]))
    random.Random(SEED).shuffle(flights[5]["positions"])

    # --- Invalid records and the duplicate (D7, D4). Each has exactly one problem.
    # FLT-1011: a single position (too few points).
    flights.append(flight_record("FLT-1011", "PRAC111", "GLF5", "KJFK", "KJFK",
                                 [(at(16), 40.65, -73.79, 0)]))
    # FLT-1012: FLT-1001's first 4 positions, with an impossible latitude in position 2.
    flights.append(flight_record("FLT-1012", "PRAC112", "B738", "EGLL", "LFPG", f1001[:4]))
    flights[-1]["positions"][2]["coord"][1] = 91.2
    # FLT-1013: FLT-1008's first 3 positions, with an impossible time in position 1.
    flights.append(flight_record("FLT-1013", "PRAC113", "B738", "LFPG", "EGLL", f1008[:3]))
    flights[-1]["positions"][1]["ts"] = "2024-05-01T25:61:00Z"
    # A record without flight_id: FLT-1009's first 3 positions, times written with Z.
    flights.append(flight_record(None, "PRAC114", "A320", "EDDF", "LFPG", f1009[:3]))
    # Record 14 repeats FLT-1004 exactly: an exact duplicate, kept once.
    flights.append(copy.deepcopy(flights[3]))

    # --- Zones, in feature order. Radii are NM except ZN-SURVEY (km). Each TFR centre sits
    # beside the midpoint of one flight segment, at a planted distance from it: TFR-101
    # exactly its 20 NM radius from FLT-1008 segment 6 (a single touch, S7); TFR-102
    # 10 NM + 5 m from FLT-1009 segment 8 (5 m outside: no pass, S8); TFR-103 10 NM - 5 m
    # from FLT-1009 segment 10 (5 m inside: a 0.86 km pass between two reports, S9).
    tfr101 = perp_centre(f1008, 6, 20 * NM_TO_KM)
    tfr102 = perp_centre(f1009, 8, 10 * NM_TO_KM + 0.005)
    tfr103 = perp_centre(f1009, 10, 10 * NM_TO_KM - 0.005)
    zones = [
        zone_feature("ZN-LHR", "London Heathrow control zone", 51.47, -0.4543, 25, "NM"),
        zone_feature("ZN-JFK", "New York JFK terminal core", 40.6413, -73.7781, 30, "NM"),
        zone_feature("ZN-PITUFFIK", "Pituffik restricted area", 76.5312, -68.7032, 25, "NM"),
        # 0.13 km from the lat/lon average of FLT-1003's gap ends: only planar code hits it.
        zone_feature("ZN-BAFFIN", "Baffin Bay exercise area", 72.58, -75.12, 60, "NM"),
        zone_feature("ZN-POLE", "North Pole advisory area", 90.0, 0.0, 75, "NM"),
        zone_feature("ZN-DATELINE", "Dateline operations area", 61.7, -179.95, 30, "NM"),
        zone_feature("ZN-SURVEY", "Bristol Channel survey block", 51.0, -3.0, 9.26, "km"),
        zone_feature("TFR-101", "Temporary flight restriction 101", *tfr101, 20, "NM"),
        zone_feature("TFR-102", "Temporary flight restriction 102", *tfr102, 10, "NM"),
        zone_feature("TFR-103", "Temporary flight restriction 103", *tfr103, 10, "NM"),
        # Invalid: a negative radius (D7).
        zone_feature("ZN-CHANNEL", "Channel exercise area", 50.0, 0.0, -5, "NM"),
    ]

    envelope = {"source": "ADS-B aggregator export (synthetic)",
                "exported_at": "2024-05-02T00:00:00Z"}
    flights_doc = {**envelope, "flights": flights}
    zones_doc = {"type": "FeatureCollection", "name": "airspace_zones", "features": zones}

    # --- Redelivery (ingestion run 3): the 10 valid records as written, with one real change
    # (FLT-1002's callsign: an update) and one format-only change (FLT-1004's epoch seconds
    # as ISO-8601 Z strings of the same instants: unchanged once normalized).
    redelivery = copy.deepcopy(flights[:10])
    redelivery[1]["callsign"] = "PRAC902"
    for position in redelivery[3]["positions"]:
        position["ts"] = datetime.fromtimestamp(position["ts"], UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    redelivery_doc = {**envelope, "flights": redelivery}
    return flights_doc, zones_doc, redelivery_doc


def write_json(rel_path, obj):
    path = REPO / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


# ==========================================================================================
# Part 2: the answer key, computed from the files on disk (DESIGN.md section 7.7)
# ==========================================================================================

# ------------------------------------------------------------ normalization (section 6.d)


class Rejected(Exception):
    """A record the ingestion must reject, with its reason code."""

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


@dataclass(frozen=True)
class Point:
    t: float  # epoch seconds, UTC
    lat: float
    lon: float
    alt_m: float | None


@dataclass
class TrajectoryRecord:
    key: str
    callsign: str | None
    aircraft_type: str | None
    origin: str | None
    destination: str | None
    points: list
    content_hash: str


@dataclass
class ZoneRecord:
    key: str
    name: str | None
    lat: float
    lon: float
    radius_km: float
    content_hash: str


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def required(obj, name):
    value = obj.get(name)
    if value is None:
        raise Rejected("missing_field", f"{name} is missing or null")
    return value


def required_str(obj, name):
    value = required(obj, name)
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise Rejected("invalid_value", f"{name} must be a string of 1-64 characters")
    return value


def optional_str(obj, name):
    value = obj.get(name)
    if value is not None and not isinstance(value, str):
        raise Rejected("invalid_value", f"{name} must be a string")
    return value


def required_number(obj, name):
    value = required(obj, name)
    if not is_number(value):
        raise Rejected("invalid_value", f"{name} must be a number")
    return float(value)


def lon_lat_pair(obj, name):
    value = required(obj, name)
    if not isinstance(value, list) or len(value) != 2 or not all(map(is_number, value)):
        raise Rejected("invalid_value", f"{name} must be [lon, lat]")
    return float(value[0]), float(value[1])


def parse_ts(value):
    """ISO-8601 with Z or a +-HH:MM offset, or integer epoch seconds -> epoch seconds (UTC)."""
    if value is None:
        raise Rejected("missing_field", "ts is missing or null")
    if is_number(value):
        return float(value)
    if not isinstance(value, str):
        raise Rejected("invalid_timestamp", f"unsupported timestamp {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise Rejected("invalid_timestamp", f"unparseable timestamp {value!r}") from None
    if parsed.tzinfo is None:
        raise Rejected("invalid_timestamp", f"timestamp without UTC offset {value!r}")
    return parsed.timestamp()


def check_lat_lon(lat, lon):
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise Rejected("out_of_range", f"position ({lat}, {lon}) out of range")
    return lat, normalize_lon(lon)


def sha256_json(payload):
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_flight(raw):
    """Validate and normalize one flight record; raise Rejected with the first problem."""
    if not isinstance(raw, dict):
        raise Rejected("invalid_value", "record is not an object")
    # Field checks, in the order the record's fields are declared.
    key = required_str(raw, "flight_id")
    callsign = optional_str(raw, "callsign")
    aircraft = raw.get("aircraft")
    if aircraft is not None and not isinstance(aircraft, dict):
        raise Rejected("invalid_value", "aircraft must be an object")
    aircraft_type = optional_str(aircraft or {}, "icao_type")
    origin = optional_str(raw, "origin")
    destination = optional_str(raw, "destination")
    positions = required(raw, "positions")
    if not isinstance(positions, list):
        raise Rejected("invalid_value", "positions must be a list")
    parsed = []
    for position in positions:
        if not isinstance(position, dict):
            raise Rejected("invalid_value", "position must be an object")
        t = parse_ts(position.get("ts"))
        lon, lat = lon_lat_pair(position, "coord")  # GeoJSON order: [lon, lat]
        alt_ft = position.get("alt_ft")
        if alt_ft is not None and not is_number(alt_ft):
            raise Rejected("invalid_value", "alt_ft must be a number or null")
        parsed.append((t, lat, lon, alt_ft))
    # Ranges, longitude wrap and units; then order, exact duplicates, conflicts and count.
    points = []
    for t, lat, lon, alt_ft in parsed:
        lat, lon = check_lat_lon(lat, lon)
        points.append(Point(t, lat, lon, None if alt_ft is None else alt_ft * FT_TO_M))
    points.sort(key=lambda p: p.t)
    unique = []
    for p in points:
        if p not in unique:
            unique.append(p)
    if len({p.t for p in unique}) != len(unique):
        raise Rejected("conflicting_points", "two different positions share a timestamp")
    if len(unique) < 2:
        raise Rejected("too_few_points", "a track needs at least two distinct positions")
    payload = {
        "trajectory_id": key, "callsign": callsign, "aircraft_type": aircraft_type,
        "origin": origin, "destination": destination,
        "points": [[datetime.fromtimestamp(p.t, UTC).isoformat(), p.lat, p.lon, p.alt_m]
                   for p in unique],
    }
    return TrajectoryRecord(key, callsign, aircraft_type, origin, destination, unique,
                            sha256_json(payload))


def normalize_zone(raw):
    """Validate and normalize one zone feature; raise Rejected with the first problem."""
    if not isinstance(raw, dict):
        raise Rejected("invalid_value", "feature is not an object")
    key = required_str(raw, "id")
    geometry = required(raw, "geometry")
    if not isinstance(geometry, dict) or required(geometry, "type") != "Point":
        raise Rejected("invalid_value", "geometry must be a Point")
    lon, lat = lon_lat_pair(geometry, "coordinates")
    properties = required(raw, "properties")
    if not isinstance(properties, dict):
        raise Rejected("invalid_value", "properties must be an object")
    name = optional_str(properties, "name")
    radius = required_number(properties, "radius")
    unit = required(properties, "radius_unit")
    if not isinstance(unit, str):
        raise Rejected("invalid_value", "radius_unit must be a string")
    lat, lon = check_lat_lon(lat, lon)
    factor = {"nm": NM_TO_KM, "km": 1.0}.get(unit.lower())
    if factor is None:
        raise Rejected("invalid_value", f"unknown radius unit {unit!r}")
    radius_km = radius * factor
    if not 0.0 < radius_km < 10000.0:
        raise Rejected("out_of_range", f"radius {radius_km} km not in (0, 10000)")
    payload = {"zone_id": key, "name": name, "center_lat": lat, "center_lon": lon,
               "radius_km": radius_km}
    return ZoneRecord(key, name, lat, lon, radius_km, sha256_json(payload))


def read_records(path):
    """Detect a file by shape: ("trajectory", flights), ("zone", features) or ("file", None)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "file", None
    if isinstance(doc, dict) and isinstance(doc.get("flights"), list):
        return "trajectory", doc["flights"]
    if (isinstance(doc, dict) and doc.get("type") == "FeatureCollection"
            and isinstance(doc.get("features"), list)):
        return "zone", doc["features"]
    return "file", None


# --------------------------------------------------------------- ingestion replay (6.d)

COUNT_FIELDS = ("seen", "inserted", "updated", "unchanged", "duplicates", "rejected")


class Store:
    """What the service's tables hold: records by natural key, in insertion (pk) order."""

    def __init__(self):
        self.tables = {"trajectory": {}, "zone": {}}
        self.ingest_runs = 0
        self.rejection_rows = 0


def ingest(store, paths):
    """Replay one `gisdb ingest PATH ...` run.

    Returns (counts, rejections, duplicates, updated keys). A directory expands to its
    *.json files sorted by name; within a run the first valid copy of a key wins.
    """
    files = []
    for rel in paths:
        path = REPO / rel
        files.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    counts = dict.fromkeys(COUNT_FIELDS, 0)
    rejections, duplicates, updated_keys = [], [], []
    seen_in_run = {}
    for path in files:
        entity, records = read_records(path)
        if records is None:
            counts["seen"] += 1
            counts["rejected"] += 1
            rejections.append({"file": path.name, "record_index": None, "record_key": None,
                               "reason_code": "invalid_file"})
            continue
        table = store.tables[entity]
        for index, raw in enumerate(records):
            counts["seen"] += 1
            raw_key = raw.get("flight_id" if entity == "trajectory" else "id") \
                if isinstance(raw, dict) else None
            raw_key = raw_key if isinstance(raw_key, str) else None
            try:
                record = normalize_flight(raw) if entity == "trajectory" else normalize_zone(raw)
            except Rejected as exc:
                counts["rejected"] += 1
                rejections.append({"file": path.name, "record_index": index,
                                   "record_key": raw_key, "reason_code": exc.code})
                continue
            if (entity, record.key) in seen_in_run:
                if seen_in_run[(entity, record.key)] == record.content_hash:
                    counts["duplicates"] += 1
                    duplicates.append({"file": path.name, "record_index": index,
                                       "record_key": record.key})
                else:
                    counts["rejected"] += 1
                    rejections.append({"file": path.name, "record_index": index,
                                       "record_key": record.key,
                                       "reason_code": "duplicate_key_conflict"})
                continue
            seen_in_run[(entity, record.key)] = record.content_hash
            stored = table.get(record.key)
            if stored is None:
                counts["inserted"] += 1
            elif stored.content_hash != record.content_hash:
                counts["updated"] += 1
                updated_keys.append(record.key)
            else:
                counts["unchanged"] += 1
                continue
            table[record.key] = record
    store.ingest_runs += 1
    store.rejection_rows += len(rejections)
    return {"paths": list(paths), **counts}, rejections, duplicates, updated_keys


# --------------------------------------------------------------------- tracks and lengths


@dataclass(frozen=True)
class Sample:
    s: float  # along-track distance, km
    vec: tuple
    seg: int
    f: float  # fraction of segment seg


class Track:
    """A stored trajectory prepared for the scans: n-vectors, segment lengths, samples."""

    def __init__(self, record):
        self.tid = record.key
        self.times = [p.t for p in record.points]
        self.vecs = [to_nvec(p.lat, p.lon) for p in record.points]
        self.theta = [angle(a, b) for a, b in pairwise(self.vecs)]
        self.seg_km = [EARTH_RADIUS_KM * t for t in self.theta]
        self.cum_km = [0.0]  # along-track km at each vertex
        for length in self.seg_km:
            self.cum_km.append(self.cum_km[-1] + length)
        self.length_km = self.cum_km[-1]
        self.nseg = len(self.seg_km)
        self.samples = []  # every segment at n = max(2, ceil(len / 0.5 km) + 1) fractions
        for i in range(self.nseg):
            n = max(2, math.ceil(self.seg_km[i] / SAMPLE_KM) + 1)
            for k in range(0 if i == 0 else 1, n):  # a shared vertex is sampled once
                f = k / (n - 1)
                vec = slerp(self.vecs[i], self.vecs[i + 1], f)
                self.samples.append(Sample(self.cum_km[i] + f * self.seg_km[i], vec, i, f))

    def locate(self, s):
        """(segment, fraction) of the along-track distance s."""
        i = min(max(bisect_right(self.cum_km, s) - 1, 0), self.nseg - 1)
        length = self.seg_km[i]
        return i, (0.0 if length <= 0 else min(1.0, max(0.0, (s - self.cum_km[i]) / length)))

    def vec_at(self, s):
        i, f = self.locate(s)
        return slerp(self.vecs[i], self.vecs[i + 1], f)

    def time_at(self, s):
        """Time is linear in the arc-length fraction of the segment (constant speed)."""
        i, f = self.locate(s)
        return self.times[i] + f * (self.times[i + 1] - self.times[i])


def lengths(record):
    """(length_km, length_3d_km) from geographiclib, each checked against an n-vector sum."""
    pts = record.points
    length = length_3d = check = check_3d = 0.0
    for p, q in pairwise(pts):
        s12_km = SPHERE.Inverse(p.lat, p.lon, q.lat, q.lon)["s12"] / 1000.0
        theta = angle(to_nvec(p.lat, p.lon), to_nvec(q.lat, q.lon))
        length += s12_km
        check += EARTH_RADIUS_KM * theta
        if p.alt_m is not None and q.alt_m is not None:
            # Horizontal arc at the mean altitude, Pythagoras with the climb (not the chord).
            mean_km, climb_km = (p.alt_m + q.alt_m) / 2000.0, (q.alt_m - p.alt_m) / 1000.0
            radius = EARTH_RADIUS_KM + mean_km
            length_3d += math.hypot(s12_km / EARTH_RADIUS_KM * radius, climb_km)
            check_3d += math.hypot(theta * radius, climb_km)
    if abs(length - check) > 1e-6 or abs(length_3d - check_3d) > 1e-6:
        raise AssertionError(f"{record.key}: geographiclib and n-vector lengths disagree")
    has_null_alt = any(p.alt_m is None for p in pts)
    return length, (None if has_null_alt else length_3d)


# ------------------------------------------------------------------------- 1-D refinement


def bisect_change(is_inside, lo, hi, steps=60):
    """Bisect where is_inside changes between lo and hi (60 halvings); return the midpoint."""
    lo_side = is_inside(lo)
    for _ in range(steps):
        mid = (lo + hi) / 2
        if is_inside(mid) == lo_side:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


def golden_min(fn, lo, hi, steps=80):
    """Minimum of a unimodal fn on [lo, hi] by golden-section search; returns (x, fn(x))."""
    x1, x2 = hi - GOLDEN * (hi - lo), lo + GOLDEN * (hi - lo)
    f1, f2 = fn(x1), fn(x2)
    for _ in range(steps):
        if f1 <= f2:
            hi, x2, f2 = x2, x1, f1
            x1 = hi - GOLDEN * (hi - lo)
            f1 = fn(x1)
        else:
            lo, x1, f1 = x1, x2, f2
            x2 = lo + GOLDEN * (hi - lo)
            f2 = fn(x2)
    x = (lo + hi) / 2
    return x, fn(x)


# -------------------------------------------------------------------- zone passes (brute)


@dataclass
class ZoneScan:
    passes: list  # [(entry_s, exit_s, entry_kind, exit_kind)]
    min_g_km: float  # closest approach minus radius; negative means inside


def scan_zone(track, centre, radius_km):
    """All passes of a track through a closed disc, by dense sampling and 1-D refinement.

    g(s) = distance from the centre - radius (negative inside), sampled at <= 0.5 km.
      1. Every sign change between two samples is bisected: inside stretches run between
         roots (a track that starts or ends inside starts or ends a stretch).
      2. Every local minimum of the sampled g is refined by golden-section search.
      3. Touch rule, first: a stretch whose deepest point is within 1 m of the boundary is
         one touch at that point (entry = exit); its bracketed roots are discarded. A
         minimum within 1 m of the boundary with no stretch around it is a touch as well.
      4. A minimum more than 1 m inside with no inside sample around it (a dip narrower
         than the sampling step) gets its two roots bisected on either side of the minimum.
      5. Pieces that meet (gap <= 1 m, e.g. at a vertex) are merged, then labelled.
    """

    def g_seg(i, f):
        p = slerp(track.vecs[i], track.vecs[i + 1], f)
        return EARTH_RADIUS_KM * angle(p, centre) - radius_km

    def g_at(s):
        return g_seg(*track.locate(s))

    samples = track.samples
    g = [EARTH_RADIUS_KM * angle(smp.vec, centre) - radius_km for smp in samples]
    inside = [x <= 0.0 for x in g]

    stretches = []
    start = 0.0 if inside[0] else None
    for j in range(len(samples) - 1):
        if inside[j] == inside[j + 1]:
            continue
        seg = samples[j + 1].seg  # consecutive samples always share a segment
        f_lo = samples[j].f if samples[j].seg == seg else 0.0
        f = bisect_change(lambda x, seg=seg: g_seg(seg, x) <= 0.0, f_lo, samples[j + 1].f)
        s = track.cum_km[seg] + f * track.seg_km[seg]
        if inside[j]:
            stretches.append((start, s))
            start = None
        else:
            start = s
    if start is not None:
        stretches.append((start, track.length_km))

    minima = []  # (s, g, sample index) of every refined local minimum
    for j in range(1, len(samples) - 1):
        if g[j] <= g[j - 1] and g[j] <= g[j + 1]:
            s_min, g_min = golden_min(g_at, samples[j - 1].s, samples[j + 1].s)
            minima.append((s_min, g_min, j))

    pieces = []  # [entry_s, exit_s, is_touch]
    for s0, s1 in stretches:
        deepest = min([(gm, sm) for sm, gm, _ in minima if s0 <= sm <= s1]
                      + [(g[j], samples[j].s) for j in range(len(samples))
                         if inside[j] and s0 <= samples[j].s <= s1], default=None)
        if deepest is not None and deepest[0] >= -TOL_KM:
            pieces.append([deepest[1], deepest[1], True])  # the touch rule takes precedence
        else:
            pieces.append([s0, s1, False])
    for s_min, g_min, j in minima:
        if any(p[0] - TOL_KM <= s_min <= p[1] + TOL_KM for p in pieces):
            continue
        if abs(g_min) <= TOL_KM:
            pieces.append([s_min, s_min, True])
        elif g_min < -TOL_KM and not (inside[j - 1] or inside[j] or inside[j + 1]):
            entry = bisect_change(lambda s: g_at(s) <= 0.0, samples[j - 1].s, s_min)
            exit_ = bisect_change(lambda s: g_at(s) <= 0.0, s_min, samples[j + 1].s)
            pieces.append([entry, exit_, False])

    pieces.sort()
    merged = []
    for piece in pieces:
        if merged and piece[0] - merged[-1][1] <= TOL_KM:
            merged[-1][1] = max(merged[-1][1], piece[1])
            merged[-1][2] = merged[-1][2] and piece[2]
        else:
            merged.append(list(piece))

    passes = []
    for s0, s1, touch in merged:
        short = touch or s1 - s0 <= TOL_KM
        entry_kind = "track_start" if s0 <= TOL_KM else ("touch" if short else "crossing")
        exit_kind = ("track_end" if track.length_km - s1 <= TOL_KM
                     else ("touch" if short else "crossing"))
        passes.append((s0, s1, entry_kind, exit_kind))
    return ZoneScan(passes, min(g + [gm for _, gm, _ in minima]))


# ------------------------------------------------------------------ intersections (brute)


def arc_fraction(x, a, b, theta):
    """Fraction along arc a -> b of the foot of x, if x is on the arc within 1 m; else None.

    "On the arc within 1 m" = within 1 m of the arc's great circle, and between the arc's
    ends with 1 m to spare at either end.
    """
    if theta < 1e-12:
        return 0.0 if EARTH_RADIUS_KM * angle(a, x) <= TOL_KM else None
    n = unit(cross(a, b))
    if abs(EARTH_RADIUS_KM * math.asin(max(-1.0, min(1.0, dot(n, x))))) > TOL_KM:
        return None
    t = math.atan2(dot(x, cross(n, a)), dot(x, a))  # angle from a towards b
    if EARTH_RADIUS_KM * t < -TOL_KM or EARTH_RADIUS_KM * (t - theta) > TOL_KM:
        return None
    return min(1.0, max(0.0, t / theta))


def along_track(track, x):
    """Along-track km of the first point of the track within 1 m of x."""
    for j in range(track.nseg):
        f = arc_fraction(x, track.vecs[j], track.vecs[j + 1], track.theta[j])
        if f is not None:
            return track.cum_km[j] + f * track.seg_km[j]
    raise AssertionError(f"{track.tid}: point not on the track")


def scan_pair(a_track, b_track):
    """Every point where two paths meet, plus shared stretches, along A (the smaller id).

    1. Vertices first: every vertex of each track against every arc of the other.
    2. Each segment pair whose midpoints are within (len_a + len_b)/2 + 1 km: sample B
       every <= 0.5 km, take the signed distance to A's great circle, R*asin(n_A . p),
       and bisect sign changes (inclusive test; a sample within 1e-9 km is a root). A root
       counts if it lies on arc A within 1 m. If B stays within 1 m of A's great circle,
       the piece is co-linear: B's ends are projected onto arc A to give an overlap.
    3. Overlaps contiguous along A are merged; crossings inside them are dropped;
       crossings within 1 m on both tracks are one crossing.
    Returns rows (kind, s_a, s_b, point) sorted along A.
    """
    A, B = a_track, b_track
    hits = []  # (s_a, s_b, point)
    for k, q in enumerate(B.vecs):
        for i in range(A.nseg):
            f = arc_fraction(q, A.vecs[i], A.vecs[i + 1], A.theta[i])
            if f is not None:
                hits.append((A.cum_km[i] + f * A.seg_km[i], B.cum_km[k], q))
    for k, p in enumerate(A.vecs):
        for j in range(B.nseg):
            f = arc_fraction(p, B.vecs[j], B.vecs[j + 1], B.theta[j])
            if f is not None:
                hits.append((A.cum_km[k], B.cum_km[j] + f * B.seg_km[j], p))

    overlaps = []  # (s_a0, s_a1)
    for i in range(A.nseg):
        a0, a1, len_a = A.vecs[i], A.vecs[i + 1], A.seg_km[i]
        if A.theta[i] < 1e-12:
            continue
        n_a = unit(cross(a0, a1))
        u_a = cross(n_a, a0)
        mid_a = slerp(a0, a1, 0.5)
        for j in range(B.nseg):
            b0, b1, len_b = B.vecs[j], B.vecs[j + 1], B.seg_km[j]
            if B.theta[j] < 1e-12:
                continue
            if EARTH_RADIUS_KM * angle(mid_a, slerp(b0, b1, 0.5)) > (len_a + len_b) / 2 + 1.0:
                continue
            n = max(2, math.ceil(len_b / SAMPLE_KM) + 1)
            fs = [k / (n - 1) for k in range(n)]

            def signed_km(f, b0=b0, b1=b1, n_a=n_a):
                return EARTH_RADIUS_KM * math.asin(max(-1.0, min(1.0, dot(n_a, slerp(b0, b1, f)))))

            g = [signed_km(f) for f in fs]
            if all(abs(x) <= TOL_KM for x in g):  # co-linear piece
                lo, hi = sorted(math.atan2(dot(p, u_a), dot(p, a0)) for p in (b0, b1))
                t0, t1 = max(0.0, lo), min(A.theta[i], hi)
                if EARTH_RADIUS_KM * (t1 - t0) >= -TOL_KM:
                    overlaps.append((A.cum_km[i] + EARTH_RADIUS_KM * t0,
                                     A.cum_km[i] + EARTH_RADIUS_KM * max(t0, t1)))
                continue
            roots = [fs[k] for k in range(n) if abs(g[k]) <= 1e-9]
            for k in range(n - 1):
                if abs(g[k]) > 1e-9 and abs(g[k + 1]) > 1e-9 and g[k] * g[k + 1] <= 0.0:
                    roots.append(bisect_change(lambda f: signed_km(f) < 0.0, fs[k], fs[k + 1]))
            for f in roots:
                x = slerp(b0, b1, f)
                fa = arc_fraction(x, a0, a1, A.theta[i])
                if fa is not None:
                    hits.append((A.cum_km[i] + fa * len_a, B.cum_km[j] + f * len_b, x))

    merged = []
    for s0, s1 in sorted(overlaps):
        if merged and s0 <= merged[-1][1] + TOL_KM:
            merged[-1][1] = max(merged[-1][1], s1)
        else:
            merged.append([s0, s1])
    stretches = []
    for s0, s1 in merged:
        if s1 - s0 <= TOL_KM:  # a co-linear contact shorter than 1 m is a single crossing
            x = A.vec_at(s0)
            hits.append((s0, along_track(B, x), x))
        else:
            stretches.append((s0, s1))
    hits = [h for h in hits if not any(s0 - TOL_KM <= h[0] <= s1 + TOL_KM for s0, s1 in stretches)]
    unique = []
    for h in hits:
        if not any(abs(h[0] - u[0]) <= TOL_KM and abs(h[1] - u[1]) <= TOL_KM for u in unique):
            unique.append(h)

    rows = [("crossing", s_a, s_b, x) for s_a, s_b, x in unique]
    for s0, s1 in stretches:
        for kind, s in (("overlap_start", s0), ("overlap_end", s1)):
            x = A.vec_at(s)
            rows.append((kind, s, along_track(B, x), x))
    rows.sort(key=lambda r: (r[1], r[2]))
    return rows


def min_separation_km(a_track, b_track):
    """Closest approach of two paths: A sampled every <= 0.5 km against B's arcs."""

    def point_arc_km(x, a, b):
        n = unit(cross(a, b))
        t = math.atan2(dot(x, cross(n, a)), dot(x, a))
        if 0.0 <= t <= angle(a, b):
            return EARTH_RADIUS_KM * abs(math.asin(max(-1.0, min(1.0, dot(n, x)))))
        return EARTH_RADIUS_KM * min(angle(x, a), angle(x, b))

    return min(point_arc_km(smp.vec, b_track.vecs[j], b_track.vecs[j + 1])
               for smp in a_track.samples for j in range(b_track.nseg))


# ----------------------------------------------------------------------------- formatting


def r6(x):
    value = round(x, 6)
    return 0.0 if value == 0 else value  # never write -0.0


def r3(x):
    value = round(x, 3)
    return 0.0 if value == 0 else value


def iso_ms(t):
    """Epoch seconds -> ISO-8601 UTC with Z, rounded to the millisecond (".000" left out)."""
    ms = round(t * 1000)
    text = (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms)).isoformat()[:19]
    return text + ("Z" if ms % 1000 == 0 else f".{ms % 1000:03d}Z")


def clock(t):
    return iso_ms(t)[11:]


def latlon(vec):
    lat, lon = from_nvec(vec)
    return r6(lat), r6(lon)


def fmt_pos(lat, lon):
    return f"({lat:.6f},{lon:.6f})"


def epoch(text):
    return datetime.fromisoformat(text).timestamp()


def at_utc(hms):
    """'13:26:53.336' on 2024-05-01 -> epoch seconds."""
    return epoch(f"2024-05-01T{hms}+00:00")


# ==========================================================================================
# Expected values (DESIGN.md sections 7.3, 7.5 and 7.6), checked by the self-check
# ==========================================================================================

SCENARIO_TITLES = {
    "D1": "coordinates are [lon, lat]",
    "D2": "units: feet, nautical miles and kilometres",
    "D3": "timestamps with Z, +02:00, -08:00 and epoch seconds",
    "D4": "unordered positions, a repeated position and a repeated record",
    "D5": "unknown field is ignored",
    "D6": "null altitudes",
    "D7": "five invalid records",
    "S1": "start inside",
    "S2": "end inside and start inside",
    "S3": "great-circle bulge inside a reporting gap",
    "S4": "zone hit only by a straight lat/lon line",
    "S5": "polar zone",
    "S6": "zone on the antimeridian",
    "S7": "path touches the boundary at one point",
    "S8": "path passes 5 m outside",
    "S9": "path dips 5 m inside between two reports",
    "S10": "vertex on the boundary",
    "X1": "same route flown in opposite directions",
    "X2": "shared waypoint passed 30 s apart",
    "X3": "crossing near the pole",
    "X4": "crossing on the antimeridian",
    "X5": "ordinary crossings",
    "X6": "shared endpoint",
    "X7": "incidental crossing",
    "X8": "pair whose paths never meet",
}

# scenario, trajectory, zone, seq, entry kind, exit kind, distance_inside_km,
# entry (lat, lon, time), exit (lat, lon, time); None = not stated by the design.
EXPECTED_PASSES = [
    ("S1", "FLT-1001", "ZN-LHR", 1, "track_start", "crossing", 46.3,
     (51.47, -0.4543, "09:00:00"), (51.596552, -1.092003, "09:03:09.409")),
    ("S2", "FLT-1001", "ZN-JFK", 1, "crossing", "track_end", 55.56,
     (40.952204, -73.261404, "15:13:56.423"), (40.6413, -73.7781, "15:17:43")),
    ("S2", "FLT-1002", "ZN-JFK", 1, "track_start", "crossing", 55.56,
     (40.6413, -73.7781, "13:05:00"), (None, None, "13:08:42.240")),
    ("S2", "FLT-1002", "ZN-LHR", 1, "crossing", "track_end", 46.3,
     (None, None, "19:11:14.825"), (51.47, -0.4543, "19:14:20")),
    ("S3", "FLT-1003", "ZN-PITUFFIK", 1, "crossing", "crossing", 91.466229,
     (76.477753, -66.933657, "13:26:53.336"), (76.698331, -70.350698, "13:33:20.722")),
    ("S5", "FLT-1004", "ZN-POLE", 1, "crossing", "crossing", 166.384618,
     (88.750844, None, "07:29:12.180"), (88.750844, None, None)),
    ("S5", "FLT-1005", "ZN-POLE", 1, "crossing", "crossing", 150.965896,
     (88.750844, None, "06:24:45.375"), (88.750844, None, None)),
    ("S6", "FLT-1006", "ZN-DATELINE", 1, "crossing", "crossing", 102.798115,
     (61.736781, -178.898277, "03:48:26.257"), (61.319411, 179.371275, None)),
    ("S6", "FLT-1007", "ZN-DATELINE", 1, "crossing", "crossing", 111.118326,
     (None, None, "04:26:18.730"), None),
    ("S7", "FLT-1008", "TFR-101", 1, "touch", "touch", 0.0,
     (54.003101, -16.581974, "11:37:30.000"), (54.003101, -16.581974, "11:37:30.000")),
    ("S9", "FLT-1009", "TFR-103", 1, "crossing", "crossing", 0.863979,
     (None, None, "12:13:23.212"), (None, None, "12:13:26.787")),
    ("S10", "FLT-1010", "ZN-SURVEY", 1, "crossing", "crossing", 14.838807, None, None),
    ("S10", "FLT-1010", "ZN-SURVEY", 2, "crossing", "crossing", 18.519983,
     None, (51.0, -3.132329, "08:15:29.999")),
    ("S10", "FLT-1010", "ZN-SURVEY", 3, "crossing", "crossing", 14.781798, None, None),
]

# scenario, (A, B), kind, (lat, lon), time on A, time on B, time_gap_s
EXPECTED_INTERSECTIONS = [
    ("X1", ("FLT-1001", "FLT-1002"), "overlap_start", (51.47, -0.4543),
     "09:00:00", "19:14:20", 36860.0),
    ("X1", ("FLT-1001", "FLT-1002"), "overlap_end", (40.6413, -73.7781),
     "15:17:43", "13:05:00", 7963.0),
    ("X2", ("FLT-1008", "FLT-1009"), "crossing", (55.0, -45.0), "13:41:58", "13:42:28", 30.0),
    ("X3", ("FLT-1004", "FLT-1005"), "crossing", (88.712001, -108.768698), None, None, 4661.8),
    ("X4", ("FLT-1006", "FLT-1007"), "crossing", (61.822942, -178.523172), None, None, 2276.4),
    ("X5", ("FLT-1001", "FLT-1008"), "crossing", (53.132767, -11.781169), None, None, 4857.8),
    ("X5", ("FLT-1002", "FLT-1008"), "crossing", (53.132768, -11.781174), None, None, 25601.2),
    ("X6", ("FLT-1003", "FLT-1007"), "crossing", (61.1743, -149.9982), None, None, 52974.0),
    ("X7", ("FLT-1008", "FLT-1010"), "crossing", (50.950078, -3.147727), None, None, 9024.9),
]

ABSENT_ZONE_PAIRS = [("FLT-1003", "ZN-BAFFIN"), ("FLT-1009", "TFR-102"), ("FLT-1008", "ZN-SURVEY")]
ABSENT_TRAJECTORY_PAIRS = [("FLT-1001", "FLT-1009")]

# points, started_at, ended_at, length_km, length_3d_km, zone passes, intersections
EXPECTED_TRAJECTORIES = {
    "FLT-1001": (27, "09:00:00", "15:17:43", 5540.018970, 5549.507673, 2, 3),
    "FLT-1002": (26, "13:05:00", "19:14:20", 5540.018970, 5549.798348, 2, 3),
    "FLT-1003": (16, "11:00:00", "17:22:54", 5424.514271, None, 1, 1),
    "FLT-1004": (14, "06:00:00", "10:07:20", 3380.402955, 3385.890118, 1, 1),
    "FLT-1005": (12, "05:30:00", "08:58:57", 2855.715224, 2860.165542, 1, 1),
    "FLT-1006": (8, "02:00:00", "08:30:07", 5656.898645, 5666.476880, 1, 1),
    "FLT-1007": (9, "02:40:00", "09:45:29", 6098.681033, 6108.154507, 1, 2),
    "FLT-1008": (33, "10:00:00", "17:34:26", 6665.159302, 6676.324252, 1, 4),
    "FLT-1009": (32, "09:35:55", "16:53:23", 6343.241244, 6354.162627, 1, 1),
    "FLT-1010": (7, "08:00:00", "08:25:56", 95.092196, 95.099020, 3, 1),
}

# radius_km, pass_count, trajectory_count
EXPECTED_ZONES = {
    "ZN-LHR": (46.3, 2, 2), "ZN-JFK": (55.56, 2, 2), "ZN-PITUFFIK": (46.3, 1, 1),
    "ZN-BAFFIN": (111.12, 0, 0), "ZN-POLE": (138.9, 2, 2), "ZN-DATELINE": (55.56, 2, 2),
    "ZN-SURVEY": (9.26, 3, 1), "TFR-101": (37.04, 1, 1), "TFR-102": (18.52, 0, 0),
    "TFR-103": (18.52, 1, 1),
}

RUN_PATHS = [["data"], ["data"], [REDELIVERY_FILE]]
EXPECTED_RUNS = [  # seen, inserted, updated, unchanged, duplicates, rejected
    (26, 20, 0, 0, 1, 5),
    (26, 0, 0, 20, 1, 5),
    (10, 0, 1, 9, 0, 0),
]
EXPECTED_REJECTIONS = [
    ("flights.json", 10, "FLT-1011", "too_few_points"),
    ("flights.json", 11, "FLT-1012", "out_of_range"),
    ("flights.json", 12, "FLT-1013", "invalid_timestamp"),
    ("flights.json", 13, None, "missing_field"),
    ("zones.json", 10, "ZN-CHANNEL", "out_of_range"),
]
EXPECTED_DUPLICATES = [("flights.json", 14, "FLT-1004")]
EXPECTED_COUNTS_AFTER_RUN_2 = {"ingest_runs": 2, "ingest_rejections": 10, "trajectories": 10,
                               "trajectory_points": 184, "zones": 10}
EXPECTED_COUNTS_AFTER_ANALYSIS = {"analysis_runs": 1, "trajectory_metrics": 10,
                                  "zone_passes": 14, "trajectory_intersections": 9}

PASS_SCENARIO = {(t, z): sid for sid, t, z, *_ in EXPECTED_PASSES}
PAIR_SCENARIO = {pair: sid for sid, pair, *_ in EXPECTED_INTERSECTIONS}

# ==========================================================================================
# Analysis, key and self-check
# ==========================================================================================


def analyse():
    """Replay ingestion, scan all pairs and return everything the key and checks need."""
    store = Store()
    runs = [ingest(store, paths) for paths in RUN_PATHS[:2]]
    counts_after_run_2 = {
        "ingest_runs": store.ingest_runs,
        "ingest_rejections": store.rejection_rows,
        "trajectories": len(store.tables["trajectory"]),
        "trajectory_points": sum(len(r.points) for r in store.tables["trajectory"].values()),
        "zones": len(store.tables["zone"]),
    }
    trajectories = dict(store.tables["trajectory"])  # the analysed state: after runs 1-2
    zones = dict(store.tables["zone"])
    runs.append(ingest(store, RUN_PATHS[2]))  # the optional run 3: the redelivery

    tracks = {tid: Track(rec) for tid, rec in trajectories.items()}
    zone_scans, passes = {}, []
    for tid, track in tracks.items():
        for zid, zone in zones.items():
            scan = scan_zone(track, to_nvec(zone.lat, zone.lon), zone.radius_km)
            zone_scans[(tid, zid)] = scan
            for seq, (s0, s1, entry_kind, exit_kind) in enumerate(scan.passes, start=1):
                passes.append({"trajectory_id": tid, "zone_id": zid, "seq": seq,
                               "track": track, "entry_s": s0, "exit_s": s1,
                               "entry_kind": entry_kind, "exit_kind": exit_kind})
    passes.sort(key=lambda p: (p["trajectory_id"], p["zone_id"], p["seq"]))

    intersections = []
    ids = sorted(tracks)  # A = the lexicographically smaller id = the first ingested
    pairs_scanned = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pairs_scanned += 1
            for kind, s_a, s_b, x in scan_pair(tracks[a], tracks[b]):
                intersections.append({"pair": (a, b), "kind": kind, "point": x,
                                      "time_a": tracks[a].time_at(s_a),
                                      "time_b": tracks[b].time_at(s_b)})
    return {
        "runs": runs, "counts_after_run_2": counts_after_run_2,
        "trajectories": trajectories, "zones": zones, "tracks": tracks,
        "lengths": {tid: lengths(rec) for tid, rec in trajectories.items()},
        "zone_scans": zone_scans, "passes": passes, "intersections": intersections,
        "pairs_scanned": pairs_scanned,
    }


def pass_row(p):
    track = p["track"]

    def end(kind, s):
        lat, lon = latlon(track.vec_at(s))
        return {"kind": kind, "lat": lat, "lon": lon, "time": iso_ms(track.time_at(s))}

    return {
        "trajectory_id": p["trajectory_id"], "zone_id": p["zone_id"], "seq": p["seq"],
        "scenario": PASS_SCENARIO.get((p["trajectory_id"], p["zone_id"])),
        "entry": end(p["entry_kind"], p["entry_s"]),
        "exit": end(p["exit_kind"], p["exit_s"]),
        "distance_inside_km": r6(p["exit_s"] - p["entry_s"]),
        "duration_s": r3(track.time_at(p["exit_s"]) - track.time_at(p["entry_s"])),
    }


def intersection_row(x):
    a, b = x["pair"]
    lat, lon = latlon(x["point"])
    return {
        "trajectory_ids": [a, b], "kind": x["kind"], "scenario": PAIR_SCENARIO.get((a, b)),
        "lat": lat, "lon": lon,
        "times": {a: iso_ms(x["time_a"]), b: iso_ms(x["time_b"])},
        "time_gap_s": r3(abs(x["time_a"] - x["time_b"])),
    }


def build_key(res, scenario_results, all_passed):
    pass_rows = [pass_row(p) for p in res["passes"]]
    inter_rows = [intersection_row(x) for x in res["intersections"]]
    trajectories = {}
    for tid, rec in res["trajectories"].items():
        length_km, length_3d_km = res["lengths"][tid]
        trajectories[tid] = {
            "point_count": len(rec.points),
            "started_at": iso_ms(rec.points[0].t),
            "ended_at": iso_ms(rec.points[-1].t),
            "duration_s": r3(rec.points[-1].t - rec.points[0].t),
            "length_km": r6(length_km),
            "length_3d_km": None if length_3d_km is None else r6(length_3d_km),
            "zone_pass_count": sum(r["trajectory_id"] == tid for r in pass_rows),
            "intersection_count": sum(tid in r["trajectory_ids"] for r in inter_rows),
        }
    zones = {}
    for zid, zone in res["zones"].items():
        rows = [r for r in pass_rows if r["zone_id"] == zid]
        zones[zid] = {
            "center": {"lat": r6(zone.lat), "lon": r6(zone.lon)},
            "radius_km": r6(zone.radius_km),
            "pass_count": len(rows),
            "trajectory_count": len({r["trajectory_id"] for r in rows}),
        }
    _, rejections, duplicates, _ = res["runs"][0]  # runs 1 and 2 reject the same records
    return {
        "meta": {
            "generator": "practice/generate_sample_data.py",
            "seed": SEED,
            "earth_radius_km": EARTH_RADIUS_KM,
            "nm_to_km": NM_TO_KM,
            "ft_to_m": FT_TO_M,
            "tol_km": TOL_KM,
            "tolerances": {"position_m": 1.0, "time_s": 1.0, "distance_m": 1.0},
            "method": "slerp sampling 0.5 km + bisection/golden-section; "
                      "lengths via geographiclib Geodesic(6371008.8, 0)",
            "rules": {
                "touch_band_m": 1.0,
                "shared_endpoint_is_intersection": True,
                "overlap_direction": "overlap_start/overlap_end follow trajectory A: the first "
                                     "ingested (lower pk), which is also the lexicographically "
                                     "smaller trajectory_id; either direction is accepted",
            },
        },
        "ingestion": {
            "runs": [{"run": n, **counts} for n, (counts, *_) in enumerate(res["runs"], start=1)],
            "rejections": rejections,
            "duplicates": duplicates,
        },
        "table_counts": {
            "after_run_2": res["counts_after_run_2"],
            "after_analysis": {"analysis_runs": 1, "trajectory_metrics": len(trajectories),
                               "zone_passes": len(pass_rows),
                               "trajectory_intersections": len(inter_rows)},
        },
        "trajectories": trajectories,
        "zones": zones,
        "zone_passes": pass_rows,
        "intersections": inter_rows,
        "absent": {
            "zone_pairs": [list(p) for p in ABSENT_ZONE_PAIRS],
            "trajectory_pairs": [list(p) for p in ABSENT_TRAJECTORY_PAIRS],
            "statement": "every trajectory-zone pair and trajectory pair not listed in "
                         "zone_passes or intersections has no rows",
        },
        "scenarios": [{"id": sid, "title": SCENARIO_TITLES[sid], "result": "PASS" if ok else "FAIL"}
                      for sid, ok in scenario_results],
        "self_check": {"scenarios": len(scenario_results), "all_passed": all_passed},
    }


# ----------------------------------------------------------------------------- self-check


class Scenario:
    """The checks of one scenario: its failures and one line of evidence."""

    def __init__(self, sid):
        self.sid = sid
        self.failures = []
        self.evidence = ""

    def expect(self, ok, failure):
        if not ok:
            self.failures.append(failure)
        return ok

    @property
    def passed(self):
        return not self.failures

    def line(self):
        text = f"{self.sid} {'PASS' if self.passed else 'FAIL'} {self.evidence}".rstrip()
        return text if self.passed else text + " | " + "; ".join(self.failures)


class Facts:
    """What the checks look at: the raw flights file, the stored records and the key rows."""

    def __init__(self, res, raw_flights):
        self.res = res
        self.raw_flights = raw_flights
        self.raw = {}
        for record in raw_flights:
            self.raw.setdefault(record.get("flight_id"), record)  # the first copy of each id
        self.recs, self.zones = res["trajectories"], res["zones"]
        self.tracks, self.scans = res["tracks"], res["zone_scans"]
        self.passes = {(p["trajectory_id"], p["zone_id"], p["seq"]): pass_row(p)
                       for p in res["passes"]}
        self.inters = [intersection_row(x) for x in res["intersections"]]

    def rows(self, tid, zid):
        return [row for (t, z, _), row in sorted(self.passes.items()) if (t, z) == (tid, zid)]

    def row(self, tid, zid, seq=1):
        return self.passes[(tid, zid, seq)]  # a missing row raises KeyError: reported as FAIL

    def pair(self, a, b):
        return [r for r in self.inters if r["trajectory_ids"] == [a, b]]


def near_pos(lat, lon, exp_lat, exp_lon):
    if exp_lon is None:  # latitude only
        return abs(lat - exp_lat) * math.pi / 180 * EARTH_RADIUS_KM <= TOL_KM
    return gc_km((lat, lon), (exp_lat, exp_lon)) <= TOL_KM


def near_time(t, exp_hms):
    return abs(t - at_utc(exp_hms)) <= 1.0


def when(row, end):
    return clock(epoch(row[end]["time"]))


def where(row, end):
    return fmt_pos(row[end]["lat"], row[end]["lon"])


def kinds(row):
    return f"{row['entry']['kind']}->{row['exit']['kind']}"


def compare_expected_rows(sc, f):
    """Compare a scenario's rows with EXPECTED_PASSES / EXPECTED_INTERSECTIONS."""
    for _, tid, zid, seq, entry_kind, exit_kind, km, entry, exit_ in (
            e for e in EXPECTED_PASSES if e[0] == sc.sid):
        label = f"{tid} x {zid} #{seq}"
        row = f.passes.get((tid, zid, seq))
        if not sc.expect(row is not None, f"{label} missing"):
            continue
        sc.expect(kinds(row) == f"{entry_kind}->{exit_kind}",
                  f"{label} kinds {kinds(row)}, expected {entry_kind}->{exit_kind}")
        sc.expect(abs(row["distance_inside_km"] - km) <= TOL_KM,
                  f"{label} {row['distance_inside_km']} km, expected {km}")
        for end, want in (("entry", entry), ("exit", exit_)):
            if want is None:
                continue
            if want[0] is not None:
                sc.expect(near_pos(row[end]["lat"], row[end]["lon"], want[0], want[1]),
                          f"{label} {end} {where(row, end)}, expected ({want[0]}, {want[1]})")
            if want[2] is not None:
                sc.expect(near_time(epoch(row[end]["time"]), want[2]),
                          f"{label} {end} {row[end]['time']}, expected {want[2]}")
    for tid, zid in sorted({(t, z) for sid, t, z, *_ in EXPECTED_PASSES if sid == sc.sid}):
        want = sum(1 for e in EXPECTED_PASSES if e[1:3] == (tid, zid))
        got = len(f.rows(tid, zid))
        sc.expect(got == want, f"{tid} x {zid}: {got} passes, expected {want}")

    for _, (a, b), kind, pos, t_a, t_b, gap_s in (
            e for e in EXPECTED_INTERSECTIONS if e[0] == sc.sid):
        rows = [r for r in f.pair(a, b) if r["kind"] == kind]
        if not sc.expect(len(rows) == 1, f"{a} x {b}: {len(rows)} {kind} rows"):
            continue
        r = rows[0]
        sc.expect(near_pos(r["lat"], r["lon"], *pos),
                  f"{a} x {b} {kind} at {fmt_pos(r['lat'], r['lon'])}, expected {pos}")
        if t_a is not None:
            sc.expect(near_time(epoch(r["times"][a]), t_a) and near_time(epoch(r["times"][b]), t_b),
                      f"{a} x {b} {kind} times {r['times']}, expected {t_a}/{t_b}")
        sc.expect(abs(r["time_gap_s"] - gap_s) <= 1.0,
                  f"{a} x {b} {kind} gap {r['time_gap_s']} s, expected {gap_s}")
    for a, b in sorted({pair for sid, pair, *_ in EXPECTED_INTERSECTIONS if sid == sc.sid}):
        want = sum(1 for e in EXPECTED_INTERSECTIONS if e[1] == (a, b))
        got = len(f.pair(a, b))
        sc.expect(got == want, f"{a} x {b}: {got} rows, expected {want}")


# One function per scenario: its specific checks, then its evidence line. The rows listed in
# EXPECTED_PASSES and EXPECTED_INTERSECTIONS are compared before these run.


def check_d1(sc, f):
    coord = f.raw["FLT-1001"]["positions"][0]["coord"]
    first = f.recs["FLT-1001"].points[0]
    sc.expect(coord == [-0.4543, 51.47], f"FLT-1001 first coord {coord}")
    sc.expect(abs(first.lat - 51.47) < 1e-9 and abs(first.lon + 0.4543) < 1e-9,
              f"stored as ({first.lat}, {first.lon})")
    for tid, exp in EXPECTED_TRAJECTORIES.items():
        got = f.res["lengths"][tid][0]
        sc.expect(abs(got - exp[3]) <= TOL_KM, f"{tid} length_km {got:.6f}, expected {exp[3]}")
    sc.evidence = (f"FLT-1001 first coord {coord} stored as {fmt_pos(first.lat, first.lon)} "
                   f"(London); length_km of all 10 tracks as expected, FLT-1001 "
                   f"{f.res['lengths']['FLT-1001'][0]:.6f}")


def check_d2(sc, f):
    cruise_m = 37000 * FT_TO_M
    sc.expect(any(p.alt_m is not None and abs(p.alt_m - cruise_m) < 1e-9
                  for p in f.recs["FLT-1001"].points), f"no FLT-1001 point at {cruise_m} m")
    for zid, (radius_km, _, _) in EXPECTED_ZONES.items():
        got = f.zones[zid].radius_km
        sc.expect(abs(got - radius_km) < 1e-9, f"{zid} radius_km {got}, expected {radius_km}")
    pole_km = f.zones["ZN-POLE"].radius_km
    sc.expect(repr(pole_km) == "138.9", f"ZN-POLE radius_km renders as {pole_km!r}")
    for tid, exp in EXPECTED_TRAJECTORIES.items():
        got = f.res["lengths"][tid][1]
        if exp[4] is not None:
            sc.expect(got is not None and abs(got - exp[4]) <= TOL_KM,
                      f"{tid} length_3d_km {got}, expected {exp[4]}")
    sc.evidence = (f"37000 ft = {cruise_m:.1f} m; ZN-POLE 75 NM = {pole_km!r} km, "
                   f"ZN-SURVEY {f.zones['ZN-SURVEY'].radius_km!r} km; "
                   "9 length_3d_km values as expected")


def check_d3(sc, f):
    ts_1009 = f.raw["FLT-1009"]["positions"][0]["ts"]
    ts_1007 = f.raw["FLT-1007"]["positions"][0]["ts"]
    sc.expect(ts_1009 == "2024-05-01T11:35:55+02:00", f"FLT-1009 first ts {ts_1009}")
    sc.expect(ts_1007 == "2024-04-30T18:40:00-08:00", f"FLT-1007 first ts {ts_1007}")
    sc.expect(all(isinstance(p["ts"], int) for p in f.raw["FLT-1004"]["positions"]),
              "FLT-1004 ts are not epoch integers")
    for tid, exp in EXPECTED_TRAJECTORIES.items():
        pts = f.recs[tid].points
        sc.expect(near_time(pts[0].t, exp[1]) and near_time(pts[-1].t, exp[2]),
                  f"{tid} {iso_ms(pts[0].t)}-{iso_ms(pts[-1].t)}, expected {exp[1]}-{exp[2]}")
    run3, _, _, updated = f.res["runs"][2]
    got = tuple(run3[k] for k in COUNT_FIELDS)
    sc.expect(got == EXPECTED_RUNS[2], f"run 3 counts {got}, expected {EXPECTED_RUNS[2]}")
    sc.expect(updated == ["FLT-1002"], f"run 3 updated {updated}")
    sc.evidence = (f"FLT-1009 {ts_1009} -> {iso_ms(f.recs['FLT-1009'].points[0].t)}, "
                   f"FLT-1007 {ts_1007} -> {iso_ms(f.recs['FLT-1007'].points[0].t)}, "
                   f"FLT-1004 epoch seconds; run 3: updated {run3['updated']} (FLT-1002), "
                   f"unchanged {run3['unchanged']} (FLT-1004 too)")


def check_d4(sc, f):
    raw_1006 = [p["ts"] for p in f.raw["FLT-1006"]["positions"]]
    sc.expect(raw_1006 != sorted(raw_1006), "FLT-1006 positions are already in time order")
    sc.expect(iso_ms(f.recs["FLT-1006"].points[0].t) == "2024-05-01T02:00:00Z",
              "FLT-1006 first point is not 02:00:00Z")
    sc.expect(len(f.raw["FLT-1005"]["positions"]) == 13 and len(f.recs["FLT-1005"].points) == 12,
              "FLT-1005 is not 13 positions -> 12 points")
    sc.expect(f.raw_flights[14] == f.raw_flights[3], "record 14 is not an exact copy of record 3")
    for n in (1, 2):
        dups = [(d["file"], d["record_index"], d["record_key"]) for d in f.res["runs"][n - 1][2]]
        sc.expect(dups == EXPECTED_DUPLICATES, f"run {n} duplicates {dups}")
    n_positions = sum(len(r["positions"]) for r in f.raw_flights)
    n_points = f.res["counts_after_run_2"]["trajectory_points"]
    sc.expect(n_positions == 210, f"{n_positions} positions in flights.json, expected 210")
    sc.expect(n_points == 184, f"{n_points} points stored, expected 184")
    for tid, exp in EXPECTED_TRAJECTORIES.items():
        got = len(f.recs[tid].points)
        sc.expect(got == exp[0], f"{tid} {got} points, expected {exp[0]}")
    sc.evidence = ("FLT-1006 sorted (first 02:00:00Z), FLT-1005 13 -> 12 points, record 14 = "
                   f"FLT-1004 counted once as a duplicate; {n_positions} positions -> "
                   f"{n_points} points")


def check_d5(sc, f):
    sc.expect(f.raw["FLT-1008"].get("squawk") == "7000", "FLT-1008 has no squawk field")
    sc.expect("FLT-1008" in f.recs, "FLT-1008 is not stored")
    sc.evidence = 'FLT-1008 with "squawk": "7000" is stored'


def check_d6(sc, f):
    alts = [p["alt_ft"] for p in f.raw["FLT-1003"]["positions"]]
    sc.expect(alts[2] is None and alts[3] is None and alts.count(None) == 2,
              f"FLT-1003 alt_ft {alts[:5]}")
    sc.expect(f.res["lengths"]["FLT-1003"][1] is None, "FLT-1003 length_3d_km is not null")
    sc.evidence = "FLT-1003 positions 2 and 3 have alt_ft null: stored, length_3d_km null"


def check_d7(sc, f):
    for n in (1, 2):
        counts, rejections, _, _ = f.res["runs"][n - 1]
        got = [(r["file"], r["record_index"], r["record_key"], r["reason_code"])
               for r in rejections]
        sc.expect(got == EXPECTED_REJECTIONS, f"run {n} rejections {got}")
        got, want = tuple(counts[k] for k in COUNT_FIELDS), EXPECTED_RUNS[n - 1]
        sc.expect(got == want, f"run {n} counts {got}, expected {want}")
    sc.expect(f.res["counts_after_run_2"] == EXPECTED_COUNTS_AFTER_RUN_2,
              f"table counts {f.res['counts_after_run_2']}")
    run1, run2 = f.res["runs"][0][0], f.res["runs"][1][0]
    sc.evidence = ("rejected flights.json#10 FLT-1011 too_few_points, #11 FLT-1012 out_of_range, "
                   "#12 FLT-1013 invalid_timestamp, #13 (no id) missing_field, zones.json#10 "
                   f"ZN-CHANNEL out_of_range; run 1 seen {run1['seen']} = {run1['inserted']} "
                   f"inserted + {run1['duplicates']} duplicate + {run1['rejected']} rejected; "
                   f"run 2 unchanged {run2['unchanged']}")


def check_s1(sc, f):
    r = f.row("FLT-1001", "ZN-LHR")
    sc.evidence = (f"{kinds(r)} {r['distance_inside_km']:.6f} km, "
                   f"exit {where(r, 'exit')} {when(r, 'exit')}")


def check_s2(sc, f):
    r1, r2 = f.row("FLT-1001", "ZN-JFK"), f.row("FLT-1002", "ZN-JFK")
    r3 = f.row("FLT-1002", "ZN-LHR")
    sc.evidence = (f"FLT-1001 x ZN-JFK {kinds(r1)} {r1['distance_inside_km']:.6f} km "
                   f"entry {where(r1, 'entry')} {when(r1, 'entry')}; "
                   f"FLT-1002 x ZN-JFK {kinds(r2)} exit {when(r2, 'exit')}; "
                   f"FLT-1002 x ZN-LHR {kinds(r3)} entry {when(r3, 'entry')}")


def flt1003_gap(f):
    """FLT-1003's reporting gap (its longest segment in time): (index, start, end point)."""
    track = f.tracks["FLT-1003"]
    i = max(range(track.nseg), key=lambda k: track.times[k + 1] - track.times[k])
    return i, f.recs["FLT-1003"].points[i], f.recs["FLT-1003"].points[i + 1]


def straight_line_min_km(p, q, zone, steps=20000):
    """Closest approach to a zone centre of the straight lat/lon line p -> q (planar code)."""
    return min(gc_km((p.lat + (q.lat - p.lat) * k / steps, p.lon + (q.lon - p.lon) * k / steps),
                     (zone.lat, zone.lon))
               for k in range(steps + 1))


def check_s3(sc, f):
    i, ga, gb = flt1003_gap(f)
    track, pit = f.tracks["FLT-1003"], f.zones["ZN-PITUFFIK"]
    r = f.row("FLT-1003", "ZN-PITUFFIK")
    reports_inside = sum(gc_km((p.lat, p.lon), (pit.lat, pit.lon)) <= pit.radius_km
                         for p in f.recs["FLT-1003"].points)
    straight = straight_line_min_km(ga, gb, pit)
    sc.expect(gb.t - ga.t == 3 * 3600 and abs(track.seg_km[i] - 2550) < 1,
              f"gap segment {track.seg_km[i]:.1f} km")
    sc.expect(ga.t <= epoch(r["entry"]["time"]) and epoch(r["exit"]["time"]) <= gb.t,
              "the pass is not inside the gap")
    sc.expect(reports_inside == 0, f"{reports_inside} reports inside ZN-PITUFFIK")
    sc.expect(straight > pit.radius_km and abs(straight - 469.6) <= 0.1,
              f"straight line {straight:.3f} km from the centre")
    sc.evidence = (f"{kinds(r)} {r['distance_inside_km']:.6f} km, {when(r, 'entry')}-"
                   f"{when(r, 'exit')} inside the {iso_ms(ga.t)[11:16]}-{iso_ms(gb.t)[11:16]} gap "
                   f"({track.seg_km[i]:.1f} km), no report inside; straight lat/lon line "
                   f"{straight:.1f} km from the centre (miss)")


def check_s4(sc, f):
    i, ga, gb = flt1003_gap(f)
    track, baf = f.tracks["FLT-1003"], f.zones["ZN-BAFFIN"]
    c = to_nvec(baf.lat, baf.lon)
    lo, hi = track.cum_km[i], track.cum_km[i + 1]
    k = min(range(4001), key=lambda k: angle(track.vec_at(lo + (hi - lo) * k / 4000), c))
    _, arc_km = golden_min(lambda s: EARTH_RADIUS_KM * angle(track.vec_at(s), c),
                           lo + (hi - lo) * max(0, k - 1) / 4000,
                           lo + (hi - lo) * min(4000, k + 1) / 4000)
    straight = straight_line_min_km(ga, gb, baf)
    mean_km = gc_km(((ga.lat + gb.lat) / 2, (ga.lon + gb.lon) / 2), (baf.lat, baf.lon))
    sc.expect(not f.rows("FLT-1003", "ZN-BAFFIN"), "FLT-1003 x ZN-BAFFIN has a pass")
    sc.expect(abs(arc_km - 476.4) <= 0.1, f"great circle {arc_km:.3f} km from the centre")
    sc.expect(abs(straight - 0.11) <= 0.01 and abs(mean_km - 0.13) <= 0.01,
              f"straight line {straight:.3f} km, lat/lon average {mean_km:.3f} km from the centre")
    sc.evidence = (f"no pass: great circle {arc_km:.1f} km from the centre "
                   f"(r {baf.radius_km:.2f} km), straight lat/lon line {straight:.2f} km "
                   f"(lat/lon average of the gap ends {mean_km:.2f} km)")


def check_s5(sc, f):
    r4, r5 = f.row("FLT-1004", "ZN-POLE"), f.row("FLT-1005", "ZN-POLE")
    lats = "/".join(f"{r[end]['lat']:.6f}" for r in (r4, r5) for end in ("entry", "exit"))
    sc.evidence = (f"FLT-1004 {r4['distance_inside_km']:.6f} km entry {when(r4, 'entry')}; "
                   f"FLT-1005 {r5['distance_inside_km']:.6f} km entry {when(r5, 'entry')}; "
                   f"endpoints at lat {lats}")


def check_s6(sc, f):
    r6_, r7 = f.row("FLT-1006", "ZN-DATELINE"), f.row("FLT-1007", "ZN-DATELINE")
    sc.evidence = (f"FLT-1006 {r6_['distance_inside_km']:.6f} km entry {where(r6_, 'entry')} "
                   f"{when(r6_, 'entry')} exit {where(r6_, 'exit')}; "
                   f"FLT-1007 {r7['distance_inside_km']:.6f} km entry {when(r7, 'entry')}")


def check_s7(sc, f):
    scan, r = f.scans[("FLT-1008", "TFR-101")], f.row("FLT-1008", "TFR-101")
    sc.expect(abs(scan.min_g_km) <= TOL_KM,
              f"closest approach {scan.min_g_km * 1000:+.4f} m from the boundary")
    if kinds(r) == "touch->touch":
        sc.evidence = f"touch at {where(r, 'entry')} {when(r, 'entry')}"
    else:
        sc.evidence = f"{kinds(r)} {r['distance_inside_km']:.6f} km"


def check_s8(sc, f):
    scan, near = f.scans[("FLT-1009", "TFR-102")], f.scans[("FLT-1008", "ZN-SURVEY")]
    no_pass = sorted((s.min_g_km, k) for k, s in f.scans.items() if not s.passes)
    third = no_pass[2][0] if len(no_pass) > 2 else float("inf")
    sc.expect(not f.rows("FLT-1009", "TFR-102"), "FLT-1009 x TFR-102 has a pass")
    sc.expect(abs(scan.min_g_km * 1000 - 5.041) <= 0.01,
              f"closest approach {scan.min_g_km * 1000:+.4f} m")
    sc.expect(not f.rows("FLT-1008", "ZN-SURVEY") and abs(near.min_g_km - 0.236) <= 0.001,
              f"FLT-1008 x ZN-SURVEY closest approach {near.min_g_km:.4f} km")
    sc.expect([k for _, k in no_pass[:2]] == [("FLT-1009", "TFR-102"), ("FLT-1008", "ZN-SURVEY")]
              and third > 56.0, f"nearest pairs without a pass {no_pass[:3]}")
    sc.evidence = (f"no pass: closest approach {scan.min_g_km * 1000:+.3f} m outside; also no "
                   f"pass for FLT-1008 x ZN-SURVEY ({near.min_g_km:+.3f} km); every other pair "
                   f"without a pass is >= {third:.1f} km outside")


def check_s9(sc, f):
    scan, r = f.scans[("FLT-1009", "TFR-103")], f.row("FLT-1009", "TFR-103")
    tfr = f.zones["TFR-103"]
    reports_inside = sum(gc_km((p.lat, p.lon), (tfr.lat, tfr.lon)) <= tfr.radius_km
                         for p in f.recs["FLT-1009"].points)
    sc.expect(abs(scan.min_g_km * 1000 + 5.039) <= 0.01,
              f"deepest point {scan.min_g_km * 1000:+.4f} m")
    sc.expect(reports_inside == 0, f"{reports_inside} reports inside TFR-103")
    sc.evidence = (f"{kinds(r)} {r['distance_inside_km']:.6f} km {when(r, 'entry')}-"
                   f"{when(r, 'exit')}, {-scan.min_g_km * 1000:.3f} m deep, no report inside")


def check_s10(sc, f):
    rows, vertex = f.rows("FLT-1010", "ZN-SURVEY"), f.recs["FLT-1010"].points[3]
    sc.expect(abs(vertex.lon + 3.132329) < 1e-9, f"boundary vertex lon {vertex.lon}")
    sc.expect(abs(gc_km((vertex.lat, vertex.lon), (51.0, -3.0)) - 9.26) <= TOL_KM,
              "vertex 3 is not on the boundary")
    r = f.row("FLT-1010", "ZN-SURVEY", 2)
    distances = "/".join(f"{x['distance_inside_km']:.6f}" for x in rows)
    sc.evidence = (f"{len(rows)} passes {distances} km; pass 2 exits at {where(r, 'exit')} "
                   f"{when(r, 'exit')}, vertex 3 {fmt_pos(vertex.lat, vertex.lon)} "
                   f"{clock(vertex.t)}")


def crossing_text(f, a, b, with_times=False):
    r = f.pair(a, b)[0]
    times = f" {clock(epoch(r['times'][a]))}/{clock(epoch(r['times'][b]))}" if with_times else ""
    return f"{r['kind']} {fmt_pos(r['lat'], r['lon'])}{times} gap {r['time_gap_s']:.1f} s"


def check_x1(sc, f):
    rows = f.pair("FLT-1001", "FLT-1002")
    sc.evidence = "; ".join(f"{r['kind']} {fmt_pos(r['lat'], r['lon'])} "
                            f"{clock(epoch(r['times']['FLT-1001']))}/"
                            f"{clock(epoch(r['times']['FLT-1002']))}" for r in rows)
    sc.evidence += "; no crossings"


def check_x2(sc, f):
    sc.evidence = crossing_text(f, "FLT-1008", "FLT-1009", with_times=True)


def check_x5(sc, f):
    sc.evidence = (f"FLT-1001 x FLT-1008 {crossing_text(f, 'FLT-1001', 'FLT-1008')}; "
                   f"FLT-1002 x FLT-1008 {crossing_text(f, 'FLT-1002', 'FLT-1008')}")


def check_crossing(a, b):
    def check(sc, f):
        sc.evidence = crossing_text(f, a, b)

    return check


def check_x8(sc, f):
    sep = min_separation_km(f.tracks["FLT-1001"], f.tracks["FLT-1009"])
    pairs_with_rows = {tuple(r["trajectory_ids"]) for r in f.inters}
    others = f.res["pairs_scanned"] - len(pairs_with_rows) - 1
    sc.expect(not f.pair("FLT-1001", "FLT-1009"), "FLT-1001 x FLT-1009 has rows")
    sc.expect(abs(sep - 139.1) <= 0.1, f"closest approach {sep:.3f} km")
    sc.expect(others == 36, f"{others} other pairs without rows")
    sc.evidence = (f"no rows; the paths never come closer than {sep:.1f} km; the other "
                   f"{others} pairs without rows have none either")


SCENARIO_CHECKS = {
    "D1": check_d1, "D2": check_d2, "D3": check_d3, "D4": check_d4, "D5": check_d5,
    "D6": check_d6, "D7": check_d7,
    "S1": check_s1, "S2": check_s2, "S3": check_s3, "S4": check_s4, "S5": check_s5,
    "S6": check_s6, "S7": check_s7, "S8": check_s8, "S9": check_s9, "S10": check_s10,
    "X1": check_x1, "X2": check_x2, "X3": check_crossing("FLT-1004", "FLT-1005"),
    "X4": check_crossing("FLT-1006", "FLT-1007"), "X5": check_x5,
    "X6": check_crossing("FLT-1003", "FLT-1007"), "X7": check_crossing("FLT-1008", "FLT-1010"),
    "X8": check_x8,
}


def compare_sets(f):
    """The whole found result set against the expected one; returns (report line, ok)."""
    found_passes = sorted((p["trajectory_id"], p["zone_id"], p["seq"], p["entry_kind"],
                           p["exit_kind"]) for p in f.res["passes"])
    want_passes = sorted(e[1:6] for e in EXPECTED_PASSES)
    found_inter = sorted((*r["trajectory_ids"], r["kind"]) for r in f.inters)
    want_inter = sorted((*e[1], e[2]) for e in EXPECTED_INTERSECTIONS)
    failures = []
    for name, found, want in (("passes", found_passes, want_passes),
                              ("intersections", found_inter, want_inter)):
        if found != want:
            failures.append(f"{name}: missing {sorted(set(want) - set(found))}, "
                            f"unexpected {sorted(set(found) - set(want))}")
    for tid, exp in EXPECTED_TRAJECTORIES.items():
        got = (sum(p[0] == tid for p in found_passes), sum(tid in r[:2] for r in found_inter))
        if got != exp[5:7]:
            failures.append(f"{tid} passes/intersections {got}, expected {exp[5:7]}")
    for zid, (_, n_pass, n_traj) in EXPECTED_ZONES.items():
        got = (sum(p[1] == zid for p in found_passes),
               len({p[0] for p in found_passes if p[1] == zid}))
        if got != (n_pass, n_traj):
            failures.append(f"{zid} pass_count/trajectory_count {got}, expected {(n_pass, n_traj)}")
    after_analysis = {"analysis_runs": 1, "trajectory_metrics": len(f.recs),
                      "zone_passes": len(found_passes),
                      "trajectory_intersections": len(found_inter)}
    if after_analysis != EXPECTED_COUNTS_AFTER_ANALYSIS:
        failures.append(f"table counts after analysis {after_analysis}")
    summary = (f"{len(found_passes)} zone passes in {len({p[:2] for p in found_passes})} of "
               f"{len(f.scans)} trajectory-zone pairs; {len(found_inter)} intersection rows in "
               f"{len({r[:2] for r in found_inter})} of {f.res['pairs_scanned']} trajectory pairs")
    if failures:
        return f"FOUND SET != EXPECTED SET ({summary}) | " + "; ".join(failures), False
    return f"FOUND SET == EXPECTED SET ({summary})", True


def run_self_check(res, raw_flights):
    """Run every scenario check; return [(id, passed)], the report lines and the set check."""
    f = Facts(res, raw_flights)
    scenarios = []
    for sid, check in SCENARIO_CHECKS.items():
        sc = Scenario(sid)
        try:
            compare_expected_rows(sc, f)
            check(sc, f)
        except (KeyError, IndexError) as exc:  # a missing record or row fails the scenario
            sc.expect(False, f"missing {exc}")
        scenarios.append(sc)
    set_line, set_ok = compare_sets(f)
    return [(sc.sid, sc.passed) for sc in scenarios], [sc.line() for sc in scenarios], \
        set_line, set_ok


def main():
    flights_doc, zones_doc, redelivery_doc = build_data()
    write_json(FLIGHTS_FILE, flights_doc)
    write_json(ZONES_FILE, zones_doc)
    write_json(REDELIVERY_FILE, redelivery_doc)

    # Everything below works from the files as written.
    raw_flights = json.loads((REPO / FLIGHTS_FILE).read_text(encoding="utf-8"))["flights"]
    res = analyse()
    results, lines, set_line, set_ok = run_self_check(res, raw_flights)
    all_passed = set_ok and all(ok for _, ok in results)
    write_json(KEY_FILE, build_key(res, results, all_passed))

    for line in lines:
        print(line)
    print(set_line)
    if not all_passed:
        failed = sum(not ok for _, ok in results)
        print(f"SELF-CHECK FAILED ({failed} of {len(results)} scenarios failed"
              + ("" if set_ok else "; found set differs") + ")")
        return 1
    print(f"SELF-CHECK OK ({len(results)} scenarios)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
