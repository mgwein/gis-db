# Practice data specification

The contract for the practice data: what `practice/generate_sample_data.py` writes, why each record is there, and what a correct build must produce from it. Written 2026-10-08 (Step A) from the generated files whose sha256 values are in §2, and revised the same day after the Step A critiques: the generator's S4 self-check now refines its closest approach (0.10 km, §11.6), §5.1's D1 row is complete, and §12 is closed because DESIGN §7 now matches the key. The data files and the key did not change. If the files no longer match the §2 values, this document is out of date.

Practice material only: it is not part of the service, and Step B executors never see `practice/`.

**Authority.** `practice/answer_key.json` is authoritative. Every value below comes from the generated files or the key, never from the design's prototype. Where `practice/DESIGN.md` §7 differs, the key wins; §12 records the 2026-10-08 reconciliation, after which none differ.

| Reader | Start with |
|---|---|
| Candidate, after a practice run | §6 ingestion, §7 scenarios, §8 expected results; §5 explains what a wrong number usually means |
| Critics | §2, §5, §11, §12 |
| Author of `practice/check_answer_key.py` (Step C) | §6, §9, §10 |

**Conventions.**

- Positions in prose and tables are (lat, lon). `[lon, lat]` appears only where the JSON uses it.
- Times are UTC on 2024-05-01 unless a date is shown. They are written as the key writes them: `09:03:09.409`, with `.000` left out (`09:00:00`).
- Segment i joins points i and i+1 (0-based), as `segment_a` / `segment_b` do in DESIGN §6.c.
- `A × B` names a pair. For two trajectories, A is the lexicographically smaller `trajectory_id`, which in this data is also the first ingested (lower `pk`).

**Contents**

1. Files
2. Generation and determinism
3. JSON shapes
4. Records and how they were built
5. Planted gotchas, invalid and duplicate records
6. Ingestion accounting
7. Scenarios D1–D7, S1–S10, X1–X8
8. Expected analysis results
9. Answer key format
10. Tolerances and comparing a build with the key
11. Brute-force method and self-check report
12. Differences from the design record

## 1. Files

| File | Role | Top level | Records | Bytes |
|---|---|---|---|---|
| `data/flights.json` | Provided input: aircraft position reports | object `{source, exported_at, flights}` | 15 flights (10 valid, 1 exact duplicate, 4 invalid); 210 positions | 37 826 |
| `data/zones.json` | Provided input: circular airspace zones | GeoJSON `FeatureCollection` | 11 features (10 valid, 1 invalid) | 3 537 |
| `practice/redelivery/flights.json` | Input for the optional ingestion run 3; never in `data/` | same as `data/flights.json` | 10 flights, all valid; 185 positions | 33 045 |
| `practice/answer_key.json` | Expected results; candidate-only | object (§9) | 14 zone passes, 9 intersection rows, 25 scenarios | 20 092 |

There is no airports file: `origin` and `destination` are codes only.

## 2. Generation and determinism

Run from the repository root:

```bash
uv run --no-project --with geographiclib python practice/generate_sample_data.py
```

| Property | Value |
|---|---|
| Writes | Exactly the four files of §1, overwriting them. Paths come from the script's own location (`__file__`), so it never writes anywhere else |
| Stdout | The self-check report (§11.6). Last line `SELF-CHECK OK (25 scenarios)` and exit 0; any FAIL exits 1 |
| Run time | About 2 s |
| Dependencies | Python 3.11+ standard library (it uses `datetime.UTC`) plus geographiclib (2.1 here). geographiclib is used for two things: placing the TFR centres (`Direct`, `Inverse`) and the length oracle on `Geodesic(6371008.8, 0.0)`, an exact sphere |
| Independence | Never imports `gisdb`. Has no closed-form circle or arc intersection code (§11) |
| Randomness | `SEED = 20240501`, used only for `random.Random(SEED).shuffle` of FLT-1006's positions |
| Other inputs | None: no clock, environment or network input; the day is fixed at 2024-05-01 |

The output is byte-identical on every run. Repeated runs, `PYTHONHASHSEED` 1 and 12345, and Python 3.11.15 and 3.12.3 all give these hashes (rechecked 2026-10-08 after the generator revision, which changed only the self-check's S4 line):

| File | sha256 |
|---|---|
| `data/flights.json` | `3129fb565ab911a25bfbe573a3eb8918825544b3279ae39ec4e4d36171072afb` |
| `data/zones.json` | `973498c39b640e5909b2ea61a02abc9fa740ae3c4ebcff436458455d4cf9ac95` |
| `practice/redelivery/flights.json` | `b1ab794a33dd518667719d12e58d90dbadb0207a879888f6acdcecb5df12f0bb` |
| `practice/answer_key.json` | `0ceef55335ecf7c5a0202914390ca8ecc4d5a90d08a1c1aece8c732a04b67d55` |

## 3. JSON shapes

### 3.1 `data/flights.json`

Top level, keys in this order:

| Key | Type | Value |
|---|---|---|
| `source` | string | `"ADS-B aggregator export (synthetic)"` |
| `exported_at` | string | `"2024-05-02T00:00:00Z"` |
| `flights` | array | 15 flight records |

Flight record, keys in this order (`squawk` appears only on FLT-1008, after `destination`):

| Field | JSON type | Present in | Unit / format | Stored as (DESIGN §6.c) |
|---|---|---|---|---|
| `flight_id` | string | every record except index 13 | natural key, `FLT-1001` … `FLT-1013` | `trajectories.trajectory_id` |
| `callsign` | string | all | `PRAC` + 3 digits | `trajectories.callsign` |
| `aircraft` | object `{"icao_type": string}` | all | ICAO aircraft type, e.g. `"B77W"` | `trajectories.aircraft_type` (from `aircraft.icao_type`) |
| `origin`, `destination` | string | all | 4-letter ICAO airport code | `trajectories.origin`, `trajectories.destination` |
| `squawk` | string | FLT-1008 only, `"7000"` | unknown field | not stored |
| `positions` | array of objects | all | file order, not always time order | rows of `trajectory_points` |

Position, keys always `ts`, `coord`, `alt_ft` in this order:

| Field | JSON type | Unit / format | Stored as |
|---|---|---|---|
| `ts` | string or integer | ISO-8601 with `Z` or `±HH:MM`, whole seconds, no fraction; or integer Unix epoch seconds | `trajectory_points.ts` in UTC; the first and last give `trajectories.started_at` and `ended_at` |
| `coord` | array of 2 numbers | `[lon, lat]` in degrees (GeoJSON order), at most 6 decimals | `trajectory_points.lon`, `trajectory_points.lat` |
| `alt_ft` | integer or null | feet, a multiple of 100 | `trajectory_points.alt_m` = `alt_ft` × 0.3048; null stays null |

Time forms, counted over all 210 positions:

| Form | Real example | Used by | Positions |
|---|---|---|---|
| `Z` | `"2024-05-01T09:00:00Z"` | every record not listed below | 141 |
| `+02:00` | `"2024-05-01T11:35:55+02:00"` (FLT-1009's first, = 09:35:55Z) | FLT-1009 | 32 |
| `-08:00` | `"2024-04-30T18:40:00-08:00"` (FLT-1007's first, = 2024-05-01T02:40:00Z) | FLT-1007 | 9 |
| epoch integer | `1714543200` (FLT-1004's first, = 06:00:00Z) | FLT-1004 and its copy at index 14 | 28 |

The 141 `Z` strings include FLT-1013's invalid `"2024-05-01T25:61:00Z"`.

Real record (FLT-1010, complete; shown compactly, while the file is indented):

```json
{"flight_id": "FLT-1010", "callsign": "PRAC110", "aircraft": {"icao_type": "C208"},
 "origin": "EGFF", "destination": "EGFF",
 "positions": [
  {"ts": "2024-05-01T08:00:00Z", "coord": [-3.2, 50.95], "alt_ft": 1500},
  {"ts": "2024-05-01T08:07:38Z", "coord": [-2.8, 50.95], "alt_ft": 1500},
  {"ts": "2024-05-01T08:09:09Z", "coord": [-2.8, 51.0], "alt_ft": 1500},
  {"ts": "2024-05-01T08:15:30Z", "coord": [-3.132329, 51.0], "alt_ft": 1500},
  {"ts": "2024-05-01T08:16:47Z", "coord": [-3.2, 51.0], "alt_ft": 1500},
  {"ts": "2024-05-01T08:18:18Z", "coord": [-3.2, 51.05], "alt_ft": 1500},
  {"ts": "2024-05-01T08:25:56Z", "coord": [-2.8, 51.05], "alt_ft": 1500}]}
```

### 3.2 `data/zones.json`

Top level: `{"type": "FeatureCollection", "name": "airspace_zones", "features": [...]}`, with 11 features.

Feature, keys in this order:

| Field | JSON type | Values | Stored as (DESIGN §6.c) |
|---|---|---|---|
| `type` | string | always `"Feature"` | — |
| `id` | string | natural key, `ZN-…` or `TFR-…` | `zones.zone_id` |
| `geometry` | object | `{"type": "Point", "coordinates": [lon, lat]}`; always a Point | `zones.center_lon`, `zones.center_lat` |
| `properties.name` | string | e.g. `"London Heathrow control zone"` | `zones.name` |
| `properties.radius` | number | integers, except ZN-SURVEY `9.26`; ZN-CHANNEL is `-5` | `zones.radius_km` = radius × unit factor |
| `properties.radius_unit` | string | `"NM"` (10 features) or `"km"` (ZN-SURVEY only) | factor 1.852 or 1.0, matched case-insensitively (DESIGN §6.d) |

Real feature:

```json
{"type": "Feature", "id": "ZN-LHR",
 "geometry": {"type": "Point", "coordinates": [-0.4543, 51.47]},
 "properties": {"name": "London Heathrow control zone", "radius": 25, "radius_unit": "NM"}}
```

### 3.3 `practice/redelivery/flights.json`

The envelope (`source`, `exported_at`) and the record shape are the same as in `data/flights.json`. The file holds the 10 valid records (indices 0–9), in the same order and with the same values, except:

| Record | Change in the file | After normalization | Run 3 outcome |
|---|---|---|---|
| FLT-1002 | `callsign` `"PRAC102"` → `"PRAC902"` | different content hash | updated |
| FLT-1004 | every `ts` changes from an epoch integer to the ISO `Z` string of the same instant, e.g. `1714543200` → `"2024-05-01T06:00:00Z"` | same record, same hash | unchanged |

Everything else stays as in `data/`: FLT-1005's repeated position, FLT-1006's shuffled order, FLT-1008's `squawk`, FLT-1003's null altitudes, and the `+02:00` and `-08:00` offsets. The file has 185 positions.

### 3.4 Formatting and profile

- All four files are written with `json.dump(obj, f, indent=2)` plus a trailing newline: ASCII only, LF line endings, keys in the order shown above.
- Numbers are written the way Python writes floats: trailing zeros dropped (`51.47`, `-3.2`), and integral floats keep `.0` (`51.0`, `0.0`; ZN-POLE is `[0.0, 90.0]`). `alt_ft`, epoch times and most radii are integers.

A profiler run over the provided files (DESIGN §6.i, with its revised rules: likely keys by distinct ratio, `epoch s` / `epoch ms`) should report the following. Every value that §6.i lists matches.

| File | Path | Value |
|---|---|---|
| flights | records | `"flights"`, 15 items; other keys `exported_at`, `source` |
| flights | `flight_id` | 14 present, 13 distinct; `FLT-1004` appears twice |
| flights | `callsign` | 15 present, 14 distinct (93%, so the profiler treats it as a likely key); `PRAC104` appears twice, because index 14 is a full copy of FLT-1004. Repeated keys line: `flight_id FLT-1004 x2, callsign PRAC104 x2` |
| flights | `positions[].coord[0]` | min -166.203515, max 178.303493. Values beyond ±90 mean this is longitude |
| flights | `positions[].coord[1]` | min 35.5494, max 91.2 (91.2 is FLT-1012's invalid latitude) |
| flights | `positions[].alt_ft` | 2 nulls; min 0, max 39000 |
| flights | `positions[].ts` | `Z` 141, `±HH:MM` 41, `epoch s` 28 (all epoch values are below 2e10, so seconds) |
| zones | records | `"features"`, 11 items |
| zones | `geometry.coordinates[0]` | min -179.95, max 0.0 |
| zones | `geometry.coordinates[1]` | min 40.6413, max 90.0 |
| zones | `properties.radius` | min -5, max 75; `radius_unit` has 2 distinct values; repeated keys none |

## 4. Records and how they were built

### 4.1 Flight records

The outcome is that of ingestion run 1. Points are counted after normalization.

| Index | `flight_id` | Callsign | Type | Route | Time form | Positions | Run 1 | Points | Start–end (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | FLT-1001 | PRAC101 | B77W | EGLL→KJFK | `Z` | 27 | inserted | 27 | 09:00:00–15:17:43 |
| 1 | FLT-1002 | PRAC102 | B772 | KJFK→EGLL | `Z` | 26 | inserted | 26 | 13:05:00–19:14:20 |
| 2 | FLT-1003 | PRAC103 | B38M | BIKF→PANC | `Z` | 16 | inserted | 16 | 11:00:00–17:22:54 |
| 3 | FLT-1004 | PRAC104 | A332 | ENSB→PABR | epoch | 14 | inserted | 14 | 06:00:00–10:07:20 |
| 4 | FLT-1005 | PRAC105 | B763 | CYLT→UEST | `Z` | 13 | inserted | 12 | 05:30:00–08:58:57 |
| 5 | FLT-1006 | PRAC106 | B788 | PAFA→RJTT | `Z` | 8 | inserted | 8 | 02:00:00–08:30:07 |
| 6 | FLT-1007 | PRAC107 | B748 | PANC→RKSI | `-08:00` | 9 | inserted | 9 | 02:40:00–09:45:29 |
| 7 | FLT-1008 | PRAC108 | A359 | LFPG→(55.0, -45.0)→KORD | `Z` | 33 | inserted | 33 | 10:00:00–17:34:26 |
| 8 | FLT-1009 | PRAC109 | A346 | EDDF→(55.0, -45.0)→CYYZ | `+02:00` | 32 | inserted | 32 | 09:35:55–16:53:23 |
| 9 | FLT-1010 | PRAC110 | C208 | survey, EGFF→EGFF | `Z` | 7 | inserted | 7 | 08:00:00–08:25:56 |
| 10 | FLT-1011 | PRAC111 | GLF5 | KJFK→KJFK | `Z` | 1 | rejected `too_few_points` | — | — |
| 11 | FLT-1012 | PRAC112 | B738 | EGLL→LFPG | `Z` | 4 | rejected `out_of_range` | — | — |
| 12 | FLT-1013 | PRAC113 | B738 | LFPG→EGLL | `Z` | 3 | rejected `invalid_timestamp` | — | — |
| 13 | (none) | PRAC114 | A320 | EDDF→LFPG | `Z` | 3 | rejected `missing_field` | — | — |
| 14 | FLT-1004 | PRAC104 | A332 | ENSB→PABR | epoch | 14 | duplicate of index 3 | — | — |
| | | | | | **Total** | **210** | 10 inserted, 1 duplicate, 4 rejected | **184** | |

### 4.2 Zones

| Index | `id` | `name` | Centre (lat, lon) | Radius in file | `radius_km` | Run 1 |
|---|---|---|---|---|---|---|
| 0 | ZN-LHR | London Heathrow control zone | (51.47, -0.4543) | 25 NM | 46.3 | inserted |
| 1 | ZN-JFK | New York JFK terminal core | (40.6413, -73.7781) | 30 NM | 55.56 | inserted |
| 2 | ZN-PITUFFIK | Pituffik restricted area | (76.5312, -68.7032) | 25 NM | 46.3 | inserted |
| 3 | ZN-BAFFIN | Baffin Bay exercise area | (72.58, -75.12) | 60 NM | 111.12 | inserted |
| 4 | ZN-POLE | North Pole advisory area | (90.0, 0.0) | 75 NM | 138.9 | inserted |
| 5 | ZN-DATELINE | Dateline operations area | (61.7, -179.95) | 30 NM | 55.56 | inserted |
| 6 | ZN-SURVEY | Bristol Channel survey block | (51.0, -3.0) | 9.26 km | 9.26 | inserted |
| 7 | TFR-101 | Temporary flight restriction 101 | (54.324716, -16.43381) | 20 NM | 37.04 | inserted |
| 8 | TFR-102 | Temporary flight restriction 102 | (55.849211, -17.503759) | 10 NM | 18.52 | inserted |
| 9 | TFR-103 | Temporary flight restriction 103 | (56.261999, -24.473649) | 10 NM | 18.52 | inserted |
| 10 | ZN-CHANNEL | Channel exercise area | (50.0, 0.0) | -5 NM | (-9.26) | rejected `out_of_range` |

In Python floats, 25 × 1.852 is `46.300000000000004`, so a build stores that for ZN-LHR and ZN-PITUFFIK; the key rounds to `46.3`. The other products print exactly, and ZN-POLE's is `138.9`.

### 4.3 Construction

**Model.** A sphere with R = 6371.0088 km. Positions are n-vectors, and points along an arc come from slerp; raw lat/lon is never interpolated.

**`fly(route, dep, speed_kmh, step_min, cruise_ft)`** flies great-circle legs between route points at constant speed:

- A position is reported every `step_min` minutes from departure, plus one at each intermediate waypoint and one at the destination. Each report time is `dep + s / speed`, where s is the along-track distance.
- Altitude climbs linearly to cruise over the first 20 min and descends linearly over the last 25 min, rounded to the nearest 100 ft.
- `coord` is `[round(lon, 6), round(lat, 6)]`. Times are truncated to whole seconds, then written in the record's time form.

**Airports** (lat, lon):

- EGLL (51.4700, -0.4543), KJFK (40.6413, -73.7781), LFPG (49.0097, 2.5479), KORD (41.9742, -87.9073), EDDF (50.0379, 8.5622);
- CYYZ (43.6777, -79.6248), BIKF (63.9850, -22.6056), PANC (61.1743, -149.9982), PAFA (64.8151, -147.8564), RJTT (35.5494, 139.7798);
- RKSI (37.4602, 126.4407), ENSB (78.2461, 15.4656), PABR (71.2854, -156.7660), CYLT (82.5178, -62.2806), UEST (71.6977, 128.9030).

The waypoint WPT is (55.0, -45.0). EGFF (Cardiff) is only a code: FLT-1010's path is given by its vertices.

| Flight | Departure (UTC) | km/h | Step | Cruise (ft) | Injection |
|---|---|---|---|---|---|
| FLT-1001 | 09:00 | 880 | 15 min | 37000 | — |
| FLT-1002 | 13:05 | 900 | 15 min | 38000 | — |
| FLT-1003 | 11:00 | 850 | 15 min | 36000 | reports with 12:00 < t < 15:00 dropped; then `alt_ft` null at positions 2 and 3 |
| FLT-1004 | 06:00 | 820 | 20 min | 35000 | written as epoch integers; the whole record repeated as index 14 |
| FLT-1005 | 05:30 | 820 | 20 min | 34000 | an exact copy of position 3 inserted at index 4 (`06:30:00Z`) |
| FLT-1006 | 02:00 | 870 | 60 min | 39000 | positions shuffled; file order of the times: 06:00, 07:00, 03:00, 02:00, 08:30:07, 05:00, 04:00, 08:00 |
| FLT-1007 | 02:40 | 860 | 60 min | 37000 | written in `-08:00` |
| FLT-1008 | 10:00 | 880 | 15 min | 36000 | `"squawk": "7000"` |
| FLT-1009 | solved, first report 09:35:55 | 870 | 15 min | 37000 | written in `+02:00` |
| FLT-1010 | 08:00 | 220 | vertices only | 1500, flat | survey pattern (below) |
| FLT-1011 | — | — | — | — | one position (40.65, -73.79) at 16:00:00Z, alt 0 |
| FLT-1012 | — | — | — | — | FLT-1001's first 4 positions; position 2's latitude set to 91.2 |
| FLT-1013 | — | — | — | — | FLT-1008's first 3 positions; position 1's `ts` set to `"2024-05-01T25:61:00Z"` |
| index 13 | — | — | — | — | FLT-1009's first 3 positions, times written with `Z`; no `flight_id` key |

Each invalid record has exactly one problem.

**FLT-1009's departure** is solved so that it reaches WPT 30 s after FLT-1008: t_wp(FLT-1008) + 30 s − d(EDDF, WPT) / 870 km/h, where t_wp(FLT-1008) = 10:00 + d(LFPG, WPT) / 880 km/h. Its first report is `"2024-05-01T11:35:55+02:00"`.

**FLT-1003's reporting gap** runs from (70.204144, -34.143493) at 12:00:00 to (74.957916, -116.100537) at 15:00:00. That one segment is 2550.0 km long.

**ZN-BAFFIN** sits 0.13 km from the lat/lon average of the gap's two ends, so the straight lat/lon line between them passes 0.10 km (0.0997 km) from its centre. The great-circle segment passes 476.4 km from it.

**FLT-1010 survey** around ZN-SURVEY (centre (51.0, -3.0), r = 9.26 km):

- Vertices: (50.95, -3.2), (50.95, -2.8), (51.0, -2.8), (51.0, -3.132329), (51.0, -3.2), (51.05, -3.2), (51.05, -2.8).
- Each vertex time is the previous vertex time plus distance / 220 km/h. The times accumulate unrounded; the file truncates each one to whole seconds.
- Vertex 3 sits on latitude 51.0, west of the centre, at exactly 9.26 km from it (its longitude found by 200 bisection steps), then rounded to 6 decimals. After the rounding it lies 0.029 m outside the boundary, well inside the 1 m tolerance.

**TFR centres: `perp(track, i, d)`.**

1. Round segment i's endpoints to 6 decimals.
2. Take the slerp midpoint m.
3. Compute `azi = Geodesic(6371008.8, 0).Inverse(m, end)["azi1"]`.
4. The centre is `Direct(m, azi + 90°, d)`, rounded to 6 decimals.

| Zone | Beside | Offset d | Distance from the path to the boundary (+ = outside) |
|---|---|---|---|
| TFR-101 | FLT-1008 segment 6 (11:30:00–11:45:00, 220.0 km) | 20 NM | -0.001 m as planted; the brute force finds -0.0013 m |
| TFR-102 | FLT-1009 segment 8 (11:35:55–11:50:55, 217.5 km) | 10 NM + 5 m | +5.041 m |
| TFR-103 | FLT-1009 segment 10 (12:05:55–12:20:55, 217.5 km) | 10 NM − 5 m | -5.039 m |

## 5. Planted gotchas, invalid and duplicate records

### 5.1 Data gotchas

The "usual mistake" column describes what a wrong build shows. Its counts come from the key, or from running the generator's own code on the modified input.

| Id | Planted (exact) | Correct handling | Usual mistake and what it shows |
|---|---|---|---|
| D1 | Every `coord` and `geometry.coordinates` is `[lon, lat]`. Landmark: FLT-1001's first coord `[-0.4543, 51.47]` is London Heathrow | `lon, lat = coord`; FLT-1001 starts at (51.47, -0.4543) | Read as `[lat, lon]`: FLT-1003 to FLT-1007 (and the FLT-1004 copy at index 14) and ZN-DATELINE are rejected `out_of_range`, while FLT-1012 is accepted because its 91.2 now reads as a longitude. Run 1 shows inserted 15 (6 trajectories, 9 zones), duplicates 0, rejected 11; the stored flights and zones sit in the wrong places |
| D2 | `alt_ft` is in feet. Radii are in NM, except ZN-SURVEY (`9.26`, `"km"`) | m = ft × 0.3048; km = NM × 1.852 (ZN-POLE: 138.9 km) | NM read as km: ZN-POLE (then 75 km) has no passes, and the total drops from 14 passes to 10. Feet not converted: altitudes 3.28 times too large |
| D3 | Most times end in `Z`; FLT-1009 uses `+02:00`; FLT-1007 uses `-08:00`, so its first time is on 2024-04-30 local; FLT-1004 uses epoch integers | Convert to UTC: FLT-1009 starts 09:35:55Z, FLT-1007 2024-05-01T02:40:00Z, FLT-1004 06:00:00Z | Offset dropped (local wall time read as UTC): FLT-1009 starts 11:35:55Z, and X2's gap becomes 7230 s instead of 30 s. Epoch integers rejected: FLT-1004 and its copy are lost |
| D4 | FLT-1006's positions are shuffled. FLT-1005's position 4 repeats position 3 exactly. Flights index 14 repeats index 3 (FLT-1004) exactly | Sort by time; drop the exact duplicate point (13 positions → 12 points); count index 14 once in `duplicates` | FLT-1006 unsorted: its first point is 06:00:00Z instead of 02:00:00Z, and its path zigzags. FLT-1005's repeat kept: rejected as `conflicting_points`, or the run fails on `UNIQUE (trajectory_pk, ts)`. Index 14 counted as `unchanged` instead of `duplicates`, or inserted a second time (the run fails on `UNIQUE (trajectory_id)`) |
| D5 | FLT-1008 has `"squawk": "7000"` | Ignore unknown fields | Unknown fields forbidden: FLT-1008 is rejected, and its TFR-101 pass and 4 intersection rows disappear |
| D6 | FLT-1003's positions 2 and 3 have `"alt_ft": null` | Valid record; `alt_m` null; `length_3d_km` null | Record rejected (then S3 and X6 disappear), or null read as 0 ft |
| D7 | Five invalid records (§5.3) | Reject each whole record with its reason code | Repair instead (drop only the bad report): FLT-1012 survives with 3 points and FLT-1013 with 2. That gives 12 trajectories, 189 points, 1 extra pass (FLT-1012 × ZN-LHR) and 6 extra overlap rows (FLT-1012 with FLT-1001 and with FLT-1002, FLT-1013 with FLT-1008) |

### 5.2 Geometry traps

| Scenario | What is planted | What a wrong method does |
|---|---|---|
| S3 | A 2550.0 km reporting gap whose great-circle arc bulges north through ZN-PITUFFIK, with no position report inside the zone | A reports-only test misses the pass. So does linear lat/lon interpolation: the straight lat/lon line passes 469.6 km from the centre |
| S4 | ZN-BAFFIN lies 0.10 km from the straight lat/lon line between the same two reports, but 476.4 km from the great circle | Linear lat/lon interpolation invents a pass |
| S5, X3 | A zone centred on the North Pole; a crossing at latitude 88.7 | Longitude arithmetic and lat/lon bounding boxes break near the pole; the pole's longitude is arbitrary |
| S6, X4 | Hourly segments that span the antimeridian, through ZN-DATELINE and through each other | Naive longitude differences jump by 360°; lat/lon boxes miss the zone |
| S7 | The path touches TFR-101's boundary: its closest approach is about 1 mm inside | Without the 1 m touch band, the result is a crossing→crossing pass about 19 m long, or no pass |
| S8 | The path passes 5.041 m outside TFR-102 | A tolerance over 5 m invents a pass |
| S9 | The path dips 5.039 m inside TFR-103 for 0.864 km between two reports | A reports-only test misses it. A touch band over 5 m mislabels it as a touch |
| S10 | FLT-1010's vertex 3 lies on ZN-SURVEY's boundary (0.029 m outside), where pass 2 ends | Code that counts a vertex within 1 m of the boundary as inside can open a fourth, zero-length pass there; the key has exactly 3 |
| X1 | FLT-1001 and FLT-1002 fly the same great circle in opposite directions | Without a co-linear rule: spurious crossings or nothing, instead of one `overlap_start`/`overlap_end` pair |
| X2 | Both tracks have a vertex exactly at (55.0, -45.0) | Up to 4 segment pairs find the same point (duplicates without dedupe); strict interior tests find none |
| X6 | FLT-1003 ends where FLT-1007 starts (PANC) | Tests that exclude segment endpoints miss it |
| Absent list | FLT-1008 passes 0.236 km outside ZN-SURVEY. This one is incidental, not planted | Coarse approximations can invent a pass. The key lists the pair as absent |

### 5.3 Invalid and duplicate records

The step numbers refer to DESIGN §6.d's normalization order. Each invalid record has a single problem, so its code does not depend on the order of the checks. As the brief states, an invalid position report invalidates its whole record.

| File | Index | `record_key` | Problem (exact raw value) | Expected | Why that code |
|---|---|---|---|---|---|
| `flights.json` | 10 | FLT-1011 | one position: `{"ts": "2024-05-01T16:00:00Z", "coord": [-73.79, 40.65], "alt_ft": 0}` | rejected `too_few_points` | step 3: fewer than 2 distinct positions |
| `flights.json` | 11 | FLT-1012 | position 2 `"coord": [-6.649465, 91.2]`: latitude 91.2 | rejected `out_of_range` | step 2: latitude outside -90..90 |
| `flights.json` | 12 | FLT-1013 | position 1 `"ts": "2024-05-01T25:61:00Z"` | rejected `invalid_timestamp` | step 1: Pydantic `datetime_from_date_parsing` |
| `flights.json` | 13 | null | no `flight_id` key (callsign PRAC114) | rejected `missing_field`, with `record_key` null | step 1: Pydantic `missing` |
| `flights.json` | 14 | FLT-1004 | an exact copy of index 3 | `duplicates` += 1; no rejection row | same key and same content hash earlier in the same run |
| `zones.json` | 10 | ZN-CHANNEL | `"radius": -5, "radius_unit": "NM"` (-9.26 km) | rejected `out_of_range` | step 4: radius not in (0, 10000) km |

Four of the eight reason codes never occur in the practice data: `invalid_file`, `invalid_value`, `conflicting_points` and `duplicate_key_conflict`.

## 6. Ingestion accounting

Starting from a fresh schema:

| Run | Command | seen | inserted | updated | unchanged | duplicates | rejected | Why |
|---|---|---|---|---|---|---|---|---|
| 1 | `uv run gisdb ingest data` | 26 | 20 | 0 | 0 | 1 | 5 | 15 flights + 11 zones; 10 trajectories and 10 zones are new; index 14 is a duplicate; 4 flights and ZN-CHANNEL are rejected |
| 2 | the same again | 26 | 0 | 0 | 20 | 1 | 5 | Nothing changed. Duplicates are detected within a run, so index 14 counts again; the same 5 rejections are recorded again |
| 3 (optional, Step C) | `uv run gisdb ingest practice/redelivery/flights.json` | 10 | 0 | 1 | 9 | 0 | 0 | FLT-1002's callsign changed; FLT-1004's epoch → ISO change normalizes to the same record |

Every run satisfies seen = inserted + updated + unchanged + duplicates + rejected: 26 = 20 + 0 + 0 + 1 + 5, 26 = 0 + 0 + 20 + 1 + 5 and 10 = 0 + 1 + 9 + 0 + 0. The CHECK `ck_ingest_runs_accounting` enforces this on succeeded runs. Run 2 writes no trajectory, point or zone row.

Expected CLI output (DESIGN §7.6):

```text
{"ingest_run_id": 1, "status": "succeeded", "seen": 26, "inserted": 20, "updated": 0, "unchanged": 0, "duplicates": 1, "rejected": 5}
{"ingest_run_id": 2, "status": "succeeded", "seen": 26, "inserted": 0, "updated": 0, "unchanged": 20, "duplicates": 1, "rejected": 5}
```

**File order.** `data` expands to its `*.json` files sorted by name: `data/flights.json` (15 records), then `data/zones.json` (11). Rejection rows follow that order.

**`ingest_runs.files`** is derived from the files, not stored in the key. It is `{path, sha256 of the file's bytes, records}` per file:

- runs 1 and 2: `data/flights.json` (`3129fb56…`, 15), then `data/zones.json` (`973498c3…`, 11);
- run 3: `practice/redelivery/flights.json` (`b1ab794a…`, 10).

**Rejection rows.** Runs 1 and 2 each add these 5 rows; run 3 adds none:

| `source_file` (basename) | `record_index` | `record_key` | `reason_code` | `entity` |
|---|---|---|---|---|
| `flights.json` | 10 | FLT-1011 | `too_few_points` | trajectory |
| `flights.json` | 11 | FLT-1012 | `out_of_range` | trajectory |
| `flights.json` | 12 | FLT-1013 | `invalid_timestamp` | trajectory |
| `flights.json` | 13 | null | `missing_field` | trajectory |
| `zones.json` | 10 | ZN-CHANNEL | `out_of_range` | zone |

`ingest_rejections.source_file` stores the path as given (`data/flights.json`), so compare with `Path(source_file).name`. `payload` holds the raw record. The duplicate (index 14, FLT-1004) is counted only; it gets no row.

**Table counts:**

| Table | After run 2 (key) | After one `analyze` (key) | After the optional run 3 (derived, not in the key) |
|---|---|---|---|
| `ingest_runs` | 2 | 2 | 3 |
| `ingest_rejections` | 10 | 10 | 10 |
| `trajectories` | 10 | 10 | 10 |
| `trajectory_points` | 184 | 184 | 184 |
| `zones` | 10 | 10 | 10 |
| `analysis_runs` | — | 1 | unchanged |
| `trajectory_metrics` | — | 10 | unchanged |
| `zone_passes` | — | 14 | unchanged |
| `trajectory_intersections` | — | 9 | unchanged |

- `analyze` writes only the four analysis tables, and every further `analyze` adds one `analysis_runs` row while replacing the result rows with identical counts. `scripts/verify.sh` runs it twice.
- The key analyses the state after runs 1–2. Run 3 changes only a callsign, so re-analysing after it gives the same passes and intersections. Between run 3 and the next `analyze`, FLT-1002's metrics are stale (`input_hash` no longer equals `content_hash`).
- `uv run gisdb stats` after run 2 prints `{"ingest_rejections": 10, "ingest_runs": 2, "trajectories": 10, "trajectory_points": 184, "zones": 10}`.
- `uv run gisdb analyze` prints `{"analysis_run_id": 1, "status": "succeeded", "trajectories": 10, "zones": 10, "zone_passes": 14, "intersections": 9}`.

## 7. Scenarios D1–D7, S1–S10, X1–X8

### 7.1 Definitions behind the values

These are from DESIGN §6.g, matching the brief's text in DESIGN §8.3.

| Term | Definition |
|---|---|
| Earth | A sphere with R = 6371.0088 km. 1 NM = 1.852 km and 1 ft = 0.3048 m, both exact |
| Path | Between consecutive time-ordered reports, the shorter great-circle arc, flown at constant speed |
| Time and altitude inside a segment | Linear in the fraction of arc length |
| `length_km` | The sum of the segments' great-circle lengths |
| `length_3d_km` | The sum of hypot(θ·(R + mean altitude), altitude change); null if any altitude is null. A bonus value; not compared (§10) |
| Zone | A closed disc of great-circle radius `radius_km` |
| Pass | A maximal part of the path inside the disc. A vertex on the boundary never splits or duplicates a pass |
| Pass kinds | Entry: `track_start` (the track starts inside), `touch` or `crossing`. Exit: `track_end`, `touch` or `crossing`. `touch` means the path only reaches the boundary (within ±1 m) or the pass is at most 1 m long; entry and exit are then the same point (within 1 m) |
| Intersection | Every point where two paths meet is a `crossing`; shared vertices and endpoints count, each once. A stretch along the same great circle (within 1 m) is reported as an `overlap_start`/`overlap_end` pair in A's direction, with no crossings inside it |
| Tolerance | `TOL_KM = 0.001` (1 m) for every boundary, touch, same-point and merge decision |

### 7.2 Scenario table

The intent starts with the key's scenario title. All values are the key's.

| Id | Intent | Records | Expected outcome |
|---|---|---|---|
| D1 | coordinates are `[lon, lat]` (GeoJSON order) | every position and zone centre; landmark: FLT-1001 index 0 | FLT-1001's first point is stored as (51.47, -0.4543), London Heathrow. FLT-1001 `length_km` 5540.018970 |
| D2 | units: feet, nautical miles and kilometres | every `alt_ft`; every radius (ZN-SURVEY in km) | 37000 ft = 11277.6 m. `radius_km` ZN-POLE 138.9, ZN-SURVEY 9.26 (all ten in §8.2). 9 non-null `length_3d_km` values (§8.1) |
| D3 | timestamps with `Z`, `+02:00`, `-08:00` and epoch seconds | FLT-1009 (`+02:00`), FLT-1007 (`-08:00`), FLT-1004 (epoch); the rest `Z` | `started_at`: FLT-1009 2024-05-01T09:35:55Z, FLT-1007 2024-05-01T02:40:00Z, FLT-1004 2024-05-01T06:00:00Z. Run 3 leaves FLT-1004 unchanged |
| D4 | unordered positions, a repeated position and a repeated record | FLT-1006; FLT-1005; flights index 14 | FLT-1006's first point 02:00:00. FLT-1005: 13 positions → 12 points. `duplicates` 1 (index 14, FLT-1004) in runs 1 and 2. 210 positions → 184 points |
| D5 | unknown field is ignored | FLT-1008 (`"squawk": "7000"`) | FLT-1008 is stored like any other record |
| D6 | null altitudes | FLT-1003 positions 2 and 3 | Stored with `alt_m` null; FLT-1003's `length_3d_km` is null |
| D7 | five invalid records | flights indexes 10–13, zones index 10 | Rejected `too_few_points`, `out_of_range`, `invalid_timestamp`, `missing_field`, `out_of_range` (§5.3) |
| S1 | start inside: the track starts at the zone's centre | FLT-1001 × ZN-LHR | 1 pass `track_start`→`crossing`, 46.300000 km, exit (51.596552, -1.092003) at 09:03:09.409 |
| S2 | end inside and start inside | FLT-1001 × ZN-JFK; FLT-1002 × ZN-JFK and × ZN-LHR | FLT-1001 × ZN-JFK: `crossing`→`track_end`, 55.560000 km, entry (40.952204, -73.261404) at 15:13:56.423. FLT-1002 × ZN-JFK: `track_start`→`crossing`, 55.560000 km, exit 13:08:42.240. FLT-1002 × ZN-LHR: `crossing`→`track_end`, 46.300000 km, entry 19:11:14.825 |
| S3 | great-circle bulge inside a reporting gap: 3 h and 2550.0 km between reports, none inside the zone | FLT-1003 × ZN-PITUFFIK | 1 pass `crossing`→`crossing`, 91.466229 km: entry (76.477753, -66.933657) at 13:26:53.336, exit (76.698331, -70.350698) at 13:33:20.722, inside the 12:00–15:00 gap. The straight lat/lon line passes 469.6 km from the centre |
| S4 | zone hit only by a straight lat/lon line | FLT-1003 × ZN-BAFFIN | **No pass.** The great circle passes 476.4 km from the centre (r = 111.12 km); the straight lat/lon line passes 0.10 km from it |
| S5 | polar zone centred on (90, 0) | FLT-1004 and FLT-1005 × ZN-POLE | 1 pass each, `crossing`→`crossing`. FLT-1004: 166.384618 km, 07:29:12.181–07:41:22.650. FLT-1005: 150.965896 km, 06:24:45.375–06:35:48.152. All four endpoints at lat 88.750844 |
| S6 | zone on the antimeridian; hourly segments span ±180° | FLT-1006 and FLT-1007 × ZN-DATELINE | FLT-1006: 102.798115 km, entry (61.736781, -178.898277) at 03:48:26.257, exit (61.319411, 179.371275) at 03:55:31.629. FLT-1007: 111.118326 km, entry (61.790257, -178.911862) at 04:26:18.731, exit (61.596575, 179.020594) at 04:34:03.877 |
| S7 | path touches the boundary at one point (closest approach about 1 mm inside) | FLT-1008 × TFR-101 | 1 pass `touch`→`touch` at (54.003101, -16.581974), 11:37:30; 0.0 km, 0.0 s |
| S8 | path passes 5 m outside (+5.041 m) | FLT-1009 × TFR-102 | **No pass** |
| S9 | path dips 5 m inside between two reports (-5.039 m) | FLT-1009 × TFR-103 | 1 pass `crossing`→`crossing`, 0.863979 km, 12:13:23.212–12:13:26.787 (3.575 s), between the 12:05:55 and 12:20:55 reports |
| S10 | vertex on the boundary | FLT-1010 × ZN-SURVEY | 3 passes, each `crossing`→`crossing`: 14.838807, 18.519983 and 14.781798 km. Pass 2 exits at vertex 3 (51.0, -3.132329) at 08:15:30 |
| X1 | same route flown in opposite directions | FLT-1001 × FLT-1002 | Exactly 2 rows. `overlap_start` at (51.47, -0.4543): FLT-1001 09:00:00, FLT-1002 19:14:20, gap 36860.0 s. `overlap_end` at (40.6413, -73.7781): 15:17:43 and 13:05:00, gap 7963.0 s. No crossings |
| X2 | shared waypoint passed 30 s apart (vertex meets vertex) | FLT-1008 × FLT-1009 | Exactly 1 `crossing` at (55.0, -45.0): 13:41:58 and 13:42:28, gap 30.0 s |
| X3 | crossing near the pole | FLT-1004 × FLT-1005 | 1 `crossing` at (88.712001, -108.768698): 07:41:53.502 and 06:24:11.652, gap 4661.85 s |
| X4 | crossing on the antimeridian: both segments span ±180° | FLT-1006 × FLT-1007 | 1 `crossing` at (61.822942, -178.523172): 03:46:55.526 and 04:24:51.911, gap 2276.385 s |
| X5 | ordinary crossings | FLT-1001 × FLT-1008; FLT-1002 × FLT-1008 | (53.132767, -11.781169): 09:53:56.516 and 11:14:54.319, gap 4857.802 s. (53.132768, -11.781174): 18:21:35.481 and 11:14:54.320, gap 25601.161 s |
| X6 | shared endpoint (PANC) | FLT-1003 × FLT-1007 | 1 `crossing` at (61.1743, -149.9982): 17:22:54 and 02:40:00, gap 52974.0 s |
| X7 | incidental crossing | FLT-1008 × FLT-1010 | 1 `crossing` at (50.950078, -3.147727): 10:31:24.721 and 08:00:59.853, gap 9024.867 s |
| X8 | pair whose paths never meet (two westbound tracks) | FLT-1001 × FLT-1009 | **No rows**: the paths never come closer than 139.1 km. The other 36 pairs not named in X1–X7 have no rows either |

**Totals.** There are 14 zone passes in 12 of the 100 trajectory × zone pairs. There are 9 intersection rows (2 overlap, 7 crossing) in 8 of the 45 trajectory pairs.

**Other near approaches.** FLT-1008 passes 0.236 km outside ZN-SURVEY, so there is no pass. Apart from that pair and S8, every trajectory × zone pair without a pass stays at least 56.5 km outside its zone. The closest are FLT-1001 and FLT-1002 × TFR-101, at 56.56 km.

## 8. Expected analysis results

All values in this section come from `practice/answer_key.json`. Distances are shown to 6 decimals, whereas the key's JSON drops trailing zeros (`5540.01897`).

### 8.1 Trajectories

| Trajectory | `point_count` | `started_at` | `ended_at` | `duration_s` | `length_km` | `length_3d_km` | `zone_pass_count` | `intersection_count` |
|---|---|---|---|---|---|---|---|---|
| FLT-1001 | 27 | 09:00:00 | 15:17:43 | 22663.0 | 5540.018970 | 5549.507673 | 2 | 3 |
| FLT-1002 | 26 | 13:05:00 | 19:14:20 | 22160.0 | 5540.018970 | 5549.798348 | 2 | 3 |
| FLT-1003 | 16 | 11:00:00 | 17:22:54 | 22974.0 | 5424.514271 | null | 1 | 1 |
| FLT-1004 | 14 | 06:00:00 | 10:07:20 | 14840.0 | 3380.402955 | 3385.890118 | 1 | 1 |
| FLT-1005 | 12 | 05:30:00 | 08:58:57 | 12537.0 | 2855.715224 | 2860.165542 | 1 | 1 |
| FLT-1006 | 8 | 02:00:00 | 08:30:07 | 23407.0 | 5656.898645 | 5666.476880 | 1 | 1 |
| FLT-1007 | 9 | 02:40:00 | 09:45:29 | 25529.0 | 6098.681033 | 6108.154507 | 1 | 2 |
| FLT-1008 | 33 | 10:00:00 | 17:34:26 | 27266.0 | 6665.159302 | 6676.324252 | 1 | 4 |
| FLT-1009 | 32 | 09:35:55 | 16:53:23 | 26248.0 | 6343.241244 | 6354.162627 | 1 | 1 |
| FLT-1010 | 7 | 08:00:00 | 08:25:56 | 1556.0 | 95.092196 | 95.099020 | 3 | 1 |

`intersection_count` counts the rows in which the trajectory is A or B.

### 8.2 Zones

| Zone | `center` (lat, lon) | `radius_km` | `pass_count` | `trajectory_count` |
|---|---|---|---|---|
| ZN-LHR | (51.47, -0.4543) | 46.3 | 2 | 2 |
| ZN-JFK | (40.6413, -73.7781) | 55.56 | 2 | 2 |
| ZN-PITUFFIK | (76.5312, -68.7032) | 46.3 | 1 | 1 |
| ZN-BAFFIN | (72.58, -75.12) | 111.12 | 0 | 0 |
| ZN-POLE | (90.0, 0.0) | 138.9 | 2 | 2 |
| ZN-DATELINE | (61.7, -179.95) | 55.56 | 2 | 2 |
| ZN-SURVEY | (51.0, -3.0) | 9.26 | 3 | 1 |
| TFR-101 | (54.324716, -16.43381) | 37.04 | 1 | 1 |
| TFR-102 | (55.849211, -17.503759) | 18.52 | 0 | 0 |
| TFR-103 | (56.261999, -24.473649) | 18.52 | 1 | 1 |

### 8.3 Zone passes (14 rows, in key order)

| Trajectory × zone, seq | Kinds | Entry (lat, lon) and time | Exit (lat, lon) and time | `distance_inside_km` | `duration_s` | Scenario |
|---|---|---|---|---|---|---|
| FLT-1001 × ZN-JFK, 1 | `crossing`→`track_end` | (40.952204, -73.261404) 15:13:56.423 | (40.6413, -73.7781) 15:17:43 | 55.560000 | 226.577 | S2 |
| FLT-1001 × ZN-LHR, 1 | `track_start`→`crossing` | (51.47, -0.4543) 09:00:00 | (51.596552, -1.092003) 09:03:09.409 | 46.300000 | 189.409 | S1 |
| FLT-1002 × ZN-JFK, 1 | `track_start`→`crossing` | (40.6413, -73.7781) 13:05:00 | (40.952204, -73.261404) 13:08:42.240 | 55.560000 | 222.24 | S2 |
| FLT-1002 × ZN-LHR, 1 | `crossing`→`track_end` | (51.596552, -1.092003) 19:11:14.825 | (51.47, -0.4543) 19:14:20 | 46.300000 | 185.175 | S2 |
| FLT-1003 × ZN-PITUFFIK, 1 | `crossing`→`crossing` | (76.477753, -66.933657) 13:26:53.336 | (76.698331, -70.350698) 13:33:20.722 | 91.466229 | 387.386 | S3 |
| FLT-1004 × ZN-POLE, 1 | `crossing`→`crossing` | (88.750844, -32.924576) 07:29:12.181 | (88.750844, -106.516496) 07:41:22.650 | 166.384618 | 730.469 | S5 |
| FLT-1005 × ZN-POLE, 1 | `crossing`→`crossing` | (88.750844, -111.349546) 06:24:45.375 | (88.750844, -177.18908) 06:35:48.152 | 150.965896 | 662.777 | S5 |
| FLT-1006 × ZN-DATELINE, 1 | `crossing`→`crossing` | (61.736781, -178.898277) 03:48:26.257 | (61.319411, 179.371275) 03:55:31.629 | 102.798115 | 425.372 | S6 |
| FLT-1007 × ZN-DATELINE, 1 | `crossing`→`crossing` | (61.790257, -178.911862) 04:26:18.731 | (61.596575, 179.020594) 04:34:03.877 | 111.118326 | 465.146 | S6 |
| FLT-1008 × TFR-101, 1 | `touch`→`touch` | (54.003101, -16.581974) 11:37:30 | (54.003101, -16.581974) 11:37:30 | 0.000000 | 0.0 | S7 |
| FLT-1009 × TFR-103, 1 | `crossing`→`crossing` | (56.095529, -24.483159) 12:13:23.212 | (56.095956, -24.497067) 12:13:26.787 | 0.863979 | 3.575 | S9 |
| FLT-1010 × ZN-SURVEY, 1 | `crossing`→`crossing` | (50.950123, -3.105912) 08:01:47.731 | (50.950123, -2.894088) 08:05:50.269 | 14.838807 | 242.538 | S10 |
| FLT-1010 × ZN-SURVEY, 2 | `crossing`→`crossing` | (51.000076, -2.867671) 08:10:26.582 | (51.0, -3.132329) 08:15:30 | 18.519983 | 303.417 | S10 |
| FLT-1010 × ZN-SURVEY, 3 | `crossing`→`crossing` | (51.050123, -3.105733) 08:20:05.936 | (51.050123, -2.894267) 08:24:08.064 | 14.781798 | 242.128 | S10 |

### 8.4 Intersections (9 rows, in key order)

| A × B | `kind` | (lat, lon) | Time on A | Time on B | `time_gap_s` | Scenario |
|---|---|---|---|---|---|---|
| FLT-1001 × FLT-1002 | `overlap_start` | (51.47, -0.4543) | 09:00:00 | 19:14:20 | 36860.0 | X1 |
| FLT-1001 × FLT-1002 | `overlap_end` | (40.6413, -73.7781) | 15:17:43 | 13:05:00 | 7963.0 | X1 |
| FLT-1001 × FLT-1008 | `crossing` | (53.132767, -11.781169) | 09:53:56.516 | 11:14:54.319 | 4857.802 | X5 |
| FLT-1002 × FLT-1008 | `crossing` | (53.132768, -11.781174) | 18:21:35.481 | 11:14:54.320 | 25601.161 | X5 |
| FLT-1003 × FLT-1007 | `crossing` | (61.1743, -149.9982) | 17:22:54 | 02:40:00 | 52974.0 | X6 |
| FLT-1004 × FLT-1005 | `crossing` | (88.712001, -108.768698) | 07:41:53.502 | 06:24:11.652 | 4661.85 | X3 |
| FLT-1006 × FLT-1007 | `crossing` | (61.822942, -178.523172) | 03:46:55.526 | 04:24:51.911 | 2276.385 | X4 |
| FLT-1008 × FLT-1009 | `crossing` | (55.0, -45.0) | 13:41:58 | 13:42:28 | 30.0 | X2 |
| FLT-1008 × FLT-1010 | `crossing` | (50.950078, -3.147727) | 10:31:24.721 | 08:00:59.853 | 9024.867 | X7 |

### 8.5 Absent

These pairs must have no rows:

- Trajectory × zone pairs: FLT-1003 × ZN-BAFFIN (S4), FLT-1009 × TFR-102 (S8), and FLT-1008 × ZN-SURVEY (the incidental 0.236 km near approach).
- Trajectory pairs: FLT-1001 × FLT-1009 (X8).

The key's `statement` extends this to every pair not listed: "every trajectory-zone pair and trajectory pair not listed in zone_passes or intersections has no rows". That covers 88 of the 100 trajectory × zone pairs and 37 of the 45 trajectory pairs.

## 9. Answer key format

### 9.1 Structure

The top-level keys, in this order:

| Key | Type | Content |
|---|---|---|
| `meta` | object | `generator` `"practice/generate_sample_data.py"`; `seed` 20240501; `earth_radius_km` 6371.0088; `nm_to_km` 1.852; `ft_to_m` 0.3048; `tol_km` 0.001; `tolerances` `{"position_m": 1.0, "time_s": 1.0, "distance_m": 1.0}`; `method` (text); `rules` `{"touch_band_m": 1.0, "shared_endpoint_is_intersection": true, "overlap_direction": <text>}` |
| `ingestion.runs` | array of 3 | `{run, paths, seen, inserted, updated, unchanged, duplicates, rejected}`; `paths` is the CLI argument list (`["data"]`, or `["practice/redelivery/flights.json"]` for run 3) |
| `ingestion.rejections` | array of 5 | `{file, record_index, record_key, reason_code}`, the rejections of one run (identical in runs 1 and 2); `file` is a basename; `record_index` is 0-based within the file; `record_key` is null when the record has no key |
| `ingestion.duplicates` | array of 1 | `{file, record_index, record_key}`, the same in runs 1 and 2 |
| `table_counts` | object | `after_run_2` (the five core tables) and `after_analysis` (the four analysis tables, after one `analyze`) |
| `trajectories` | object keyed by `trajectory_id` (10) | `point_count`, `started_at`, `ended_at`, `duration_s`, `length_km`, `length_3d_km` (null when any altitude is null), `zone_pass_count`, `intersection_count` |
| `zones` | object keyed by `zone_id` (10) | `center {lat, lon}`, `radius_km`, `pass_count`, `trajectory_count` |
| `zone_passes` | array of 14 | `{trajectory_id, zone_id, seq, scenario, entry {kind, lat, lon, time}, exit {kind, lat, lon, time}, distance_inside_km, duration_s}` |
| `intersections` | array of 9 | `{trajectory_ids [A, B], kind, scenario, lat, lon, times {A: time, B: time}, time_gap_s}` |
| `absent` | object | `zone_pairs` (`[trajectory_id, zone_id]` lists), `trajectory_pairs` (`[A, B]` lists), `statement` |
| `scenarios` | array of 25 | `{id, title, result}`, where `result` is `"PASS"` or `"FAIL"` |
| `self_check` | object | `{"scenarios": 25, "all_passed": true}` |

Real rows, copied from the key:

```json
{"trajectory_id": "FLT-1001", "zone_id": "ZN-LHR", "seq": 1, "scenario": "S1",
 "entry": {"kind": "track_start", "lat": 51.47, "lon": -0.4543, "time": "2024-05-01T09:00:00Z"},
 "exit": {"kind": "crossing", "lat": 51.596552, "lon": -1.092003, "time": "2024-05-01T09:03:09.409Z"},
 "distance_inside_km": 46.3, "duration_s": 189.409}
```

```json
{"trajectory_ids": ["FLT-1008", "FLT-1009"], "kind": "crossing", "scenario": "X2",
 "lat": 55.0, "lon": -45.0,
 "times": {"FLT-1008": "2024-05-01T13:41:58Z", "FLT-1009": "2024-05-01T13:42:28Z"}, "time_gap_s": 30.0}
```

The other shapes, one real element each:

```text
meta.method                "slerp sampling 0.5 km + bisection/golden-section; lengths via geographiclib Geodesic(6371008.8, 0)"
meta.rules.overlap_direction  "overlap_start/overlap_end follow trajectory A: the first ingested (lower pk), which is also the lexicographically smaller trajectory_id; either direction is accepted"
ingestion.runs[0]          {"run": 1, "paths": ["data"], "seen": 26, "inserted": 20, "updated": 0, "unchanged": 0, "duplicates": 1, "rejected": 5}
ingestion.rejections[3]    {"file": "flights.json", "record_index": 13, "record_key": null, "reason_code": "missing_field"}
ingestion.duplicates[0]    {"file": "flights.json", "record_index": 14, "record_key": "FLT-1004"}
table_counts.after_run_2   {"ingest_runs": 2, "ingest_rejections": 10, "trajectories": 10, "trajectory_points": 184, "zones": 10}
trajectories["FLT-1003"]   {"point_count": 16, "started_at": "2024-05-01T11:00:00Z", "ended_at": "2024-05-01T17:22:54Z", "duration_s": 22974.0, "length_km": 5424.514271, "length_3d_km": null, "zone_pass_count": 1, "intersection_count": 1}
zones["ZN-POLE"]           {"center": {"lat": 90.0, "lon": 0.0}, "radius_km": 138.9, "pass_count": 2, "trajectory_count": 2}
absent.zone_pairs[0]       ["FLT-1003", "ZN-BAFFIN"]
scenarios[16]              {"id": "S10", "title": "vertex on the boundary", "result": "PASS"}
```

### 9.2 Values, order and meaning

| Item | Format and meaning |
|---|---|
| Times | ISO-8601 UTC ending in `Z`, rounded to the nearest millisecond. `.000` is left out on whole seconds: `"2024-05-01T09:00:00Z"`, `"2024-05-01T07:41:22.650Z"`. A parser must accept both forms |
| Positions | Degrees rounded to 6 decimals (about 0.11 m); never `-0.0` |
| Distances | km rounded to 6 decimals |
| `duration_s`, `time_gap_s` | Seconds rounded to 3 decimals |
| Numbers | Written as Python writes floats: `5540.01897` means 5540.018970, and integral values keep `.0` (`22663.0`). Counts and indexes are integers |
| `seq` (zone passes) | 1..n per (trajectory, zone), in track order, as in `zone_passes.seq` |
| `distance_inside_km` / `duration_s` | Along-track distance and time from entry to exit |
| Intersection rows | Have no `seq`; the rows of one pair are in order along A. `times` is keyed by `trajectory_id`; `time_gap_s` = abs(time on A − time on B) |
| `scenario` | A label for human readers; no build has this field |
| Row order | `zone_passes` by (`trajectory_id`, `zone_id`, `seq`). `intersections` by (A, B), then along A. `trajectories` and `zones` in file order |

**Not in the key** (skip these or derive them): altitudes at pass endpoints and intersections; `segment_a` and `segment_b`; the intersection `seq`; content hashes; run timestamps and `ingest_runs.files`; surrogate ids; `algorithm_version`.

### 9.3 Mapping to the build (DESIGN §6.c, §6.e)

| Key | Table and columns | API field |
|---|---|---|
| `trajectories.<id>`: `point_count`, `started_at`, `ended_at` | `trajectories` | `TrajectorySummary` |
| `trajectories.<id>`: `duration_s`, `length_km`, `length_3d_km`, `zone_pass_count`, `intersection_count` | `trajectory_metrics` | `TrajectorySummary.analysis` |
| `zones.<id>`: `center`, `radius_km` | `zones.center_lat`, `center_lon`, `radius_km` | `ZoneSummary.center`, `radius_km` |
| `zones.<id>`: `pass_count`, `trajectory_count` | count of the zone's `zone_passes` rows; count of their distinct `trajectory_pk` | `ZoneSummary.analysis` |
| `zone_passes[]` | `zone_passes`: `seq`, `entry_kind`, `entry_lat`, `entry_lon`, `entry_time`, the matching `exit_*` columns, `distance_inside_km`, `duration_s` | `ZonePassOut` in `TrajectoryDetail.zone_passes` and `ZoneDetail.passes` |
| `intersections[]` | `trajectory_intersections`: `trajectory_a_pk` is A; `kind`, `lat`, `lon`, `time_a` = `times[A]`, `time_b` = `times[B]`, `time_gap_s` | `IntersectionOut`; seen from B, `time_self` is B's time and `kind` is unchanged |
| `ingestion.runs[]` | `ingest_runs` counters | the `gisdb ingest` output line |
| `ingestion.rejections[]` | `ingest_rejections` (compare `source_file` by basename) | — |
| `table_counts` | row counts | `gisdb stats` |

## 10. Tolerances and comparing a build with the key

`meta.tolerances` applies as follows:

| Item | Rule |
|---|---|
| Positions (pass endpoints, intersection points, zone centres) | Great-circle distance at most 1 m (`position_m`). Never compare raw longitude: at ±180 and at the pole it is ambiguous (S5, S6, X3, X4, ZN-POLE's centre) |
| Times (`started_at`, `ended_at`, entry and exit times, `times`) | At most 1 s apart (`time_s`). The key is rounded to the millisecond; a build stores microseconds |
| `duration_s`, `time_gap_s` | At most 1 s apart (they are time differences) |
| `length_km`, `distance_inside_km`, `radius_km` | At most 1 m (0.001 km) apart (`distance_m`). For example, a build's 46.300000000000004 matches 46.3 |
| `length_3d_km` | Not compared: the brief defines it only as a bonus, with no formula or null rule. The key carries it for reference |
| Kinds, `seq`, counts, reason codes, record indexes, keys | Exact |
| Overlap direction | Either direction is accepted. A build whose A is FLT-1002 reports `overlap_start` at (40.6413, -73.7781) and `overlap_end` at (51.47, -0.4543) |
| File names | Compare by basename |
| Absent pairs | No rows at all for the pairs in `absent`, and no rows beyond those the key lists |

**Comparing a build** (DESIGN §7.7; Step C writes `practice/check_answer_key.py`):

1. Start from a fresh schema, run `gisdb ingest data` twice, then `gisdb analyze` once.
2. Compare the CLI lines, `gisdb stats` and the rejection rows with `ingestion` and `table_counts`.
3. Compare the API or database rows with `trajectories`, `zones`, `zone_passes` and `intersections`, and check `absent`.
4. Optionally run 3. Expect seen 10, inserted 0, updated 1, unchanged 9, duplicates 0, rejected 0; FLT-1002's callsign `PRAC902`; and FLT-1002's analysis marked stale until the next `analyze`.

Before trusting the key, check that `self_check.all_passed` is true and every `scenarios[].result` is `"PASS"`. The generator writes the key even when its self-check fails.

## 11. Brute-force method and self-check report

The key comes from sampling and 1-D refinement, never from the closed-form formulas of DESIGN §6.g. It therefore checks a build's geometry rather than repeating it.

### 11.1 Normalization and ingestion replay

- The generator has its own normalization code (no Pydantic). It follows DESIGN §6.d:
  - field checks;
  - `[lon, lat]` order;
  - conversion to UTC;
  - range checks and longitude wrap;
  - ft → m and NM/km → km;
  - sorting by time and dropping exact duplicate points;
  - the conflict check and the 2-point minimum;
  - a SHA-256 content hash of the normalized record.
- On every planted record it gives the same reason codes as the §6.d Pydantic mapping.
- Runs 1–3 are replayed with within-run duplicate detection, where the first copy wins. The analysis uses the state after runs 1–2.

### 11.2 Lengths

- `length_km` is the sum of `Geodesic(6371008.8, 0.0).Inverse(...)["s12"] / 1000` over consecutive points. It is asserted to equal the n-vector sum R·angle within 1e-6 km.
- `length_3d_km` is the sum of hypot(s12 / R · (R + mean altitude), altitude change), checked the same way. It is null when any altitude is null.

### 11.3 Zone passes

This is `scan_zone`, run on every one of the 100 trajectory × zone pairs, with no prefilter.

1. Each segment is sampled by slerp at n = max(2, ceil(len / 0.5 km) + 1) evenly spaced arc-length fractions. A shared vertex is sampled once. At each sample, g = R·angle(p, centre) − r, which is negative inside.
2. Every inside/outside change between two samples is bisected (60 halvings). The inside stretches run between these roots; a track that starts or ends inside opens or closes a stretch.
3. Every local minimum of the sampled g is refined by golden-section search (80 steps).
4. **The touch rule comes first.** If a stretch's deepest point is within 1 m of the boundary, the stretch becomes one touch at that point (entry = exit), and its bracketed roots are discarded. A refined minimum within 1 m of the boundary outside any stretch is also a touch.
   - S7 relies on this rule. Its sampled minimum is -0.0013 m, and 0.5 km sampling brackets two sign changes about 19 m apart, which would otherwise make a crossing pass.
5. A minimum deeper than 1 m with no inside sample around it (a dip narrower than the sampling step) gets its two roots bisected on either side. This is a safety net and fires nowhere in this data: every non-touch pass contains at least 2 inside samples, S9 included.
6. Pieces that meet within 1 m, such as at a vertex, are merged.
7. Each pass is labelled:
   - `track_start` if it starts within 1 m of the track's start, and `track_end` likewise at the end;
   - otherwise `touch` if it is a touch or at most 1 m long;
   - otherwise `crossing`.
8. Positions come from slerp at the along-track distance, and times from linear interpolation in the segment's fraction.

### 11.4 Intersections

This is `scan_pair`, run on every one of the 45 trajectory pairs, with A the smaller id.

1. **Vertices first.** Every vertex of each track is tested against every arc of the other. A vertex within 1 m of an arc's great circle, and between its ends with 1 m to spare, is a crossing. This finds shared vertices and endpoints (X2, X6) whatever their floating-point signs.
2. **Segment pairs.** Only pairs whose midpoints lie within (len_a + len_b) / 2 + 1 km are scanned. B is sampled every 0.5 km or less, and the signed distance of each sample to A's great circle is computed as R·asin(n_A · p).
   - If every sample is within 1 m, the piece is co-linear: B's ends are projected onto arc A, giving an overlap interval.
   - Otherwise, a sample within 1e-9 km is a root, and sign changes are bisected (60 steps) with the inclusive test g[k]·g[k+1] ≤ 0. A root counts if it lies on arc A within 1 m. On its own, a strict test (< 0) would find X6 with FLT-1003 as A but not with FLT-1007 as A; the vertex step finds it either way.
3. Overlap intervals that are contiguous along A (gap of 1 m or less) are merged; an overlap 1 m long or shorter becomes a single crossing.
4. Crossings inside a merged overlap (±1 m) are dropped. Crossings within 1 m of each other on both tracks are counted once.
5. Rows are sorted along A. Times come from the linear fraction on each track, and `time_gap_s` = abs(time on A − time on B).

### 11.5 Cross-check

Step A also checked the key against an implementation of DESIGN §6.g items 1–9, written from the spec text alone, plus Pydantic-based normalization. Every item agreed: ingestion, the 10 trajectories, the 10 zones, the 14 passes, the 9 intersections and both absent lists.

Before the key's rounding, the two methods differ by at most:

- 0.11 mm at pass endpoints;
- 0.006 mm in distance inside;
- under 0.0001 mm at crossing and overlap points.

### 11.6 Self-check report

The generator's stdout, verbatim:

```text
D1 PASS FLT-1001 first coord [-0.4543, 51.47] stored as (51.470000,-0.454300) (London); length_km of all 10 tracks as expected, FLT-1001 5540.018970
D2 PASS 37000 ft = 11277.6 m; ZN-POLE 75 NM = 138.9 km, ZN-SURVEY 9.26 km; 9 length_3d_km values as expected
D3 PASS FLT-1009 2024-05-01T11:35:55+02:00 -> 2024-05-01T09:35:55Z, FLT-1007 2024-04-30T18:40:00-08:00 -> 2024-05-01T02:40:00Z, FLT-1004 epoch seconds; run 3: updated 1 (FLT-1002), unchanged 9 (FLT-1004 too)
D4 PASS FLT-1006 sorted (first 02:00:00Z), FLT-1005 13 -> 12 points, record 14 = FLT-1004 counted once as a duplicate; 210 positions -> 184 points
D5 PASS FLT-1008 with "squawk": "7000" is stored
D6 PASS FLT-1003 positions 2 and 3 have alt_ft null: stored, length_3d_km null
D7 PASS rejected flights.json#10 FLT-1011 too_few_points, #11 FLT-1012 out_of_range, #12 FLT-1013 invalid_timestamp, #13 (no id) missing_field, zones.json#10 ZN-CHANNEL out_of_range; run 1 seen 26 = 20 inserted + 1 duplicate + 5 rejected; run 2 unchanged 20
S1 PASS track_start->crossing 46.300000 km, exit (51.596552,-1.092003) 09:03:09.409Z
S2 PASS FLT-1001 x ZN-JFK crossing->track_end 55.560000 km entry (40.952204,-73.261404) 15:13:56.423Z; FLT-1002 x ZN-JFK track_start->crossing exit 13:08:42.240Z; FLT-1002 x ZN-LHR crossing->track_end entry 19:11:14.825Z
S3 PASS crossing->crossing 91.466229 km, 13:26:53.336Z-13:33:20.722Z inside the 12:00-15:00 gap (2550.0 km), no report inside; straight lat/lon line 469.6 km from the centre (miss)
S4 PASS no pass: great circle 476.4 km from the centre (r 111.12 km), straight lat/lon line 0.10 km (lat/lon average of the gap ends 0.13 km)
S5 PASS FLT-1004 166.384618 km entry 07:29:12.181Z; FLT-1005 150.965896 km entry 06:24:45.375Z; endpoints at lat 88.750844/88.750844/88.750844/88.750844
S6 PASS FLT-1006 102.798115 km entry (61.736781,-178.898277) 03:48:26.257Z exit (61.319411,179.371275); FLT-1007 111.118326 km entry 04:26:18.731Z
S7 PASS touch at (54.003101,-16.581974) 11:37:30Z
S8 PASS no pass: closest approach +5.041 m outside; also no pass for FLT-1008 x ZN-SURVEY (+0.236 km); every other pair without a pass is >= 56.6 km outside
S9 PASS crossing->crossing 0.863979 km 12:13:23.212Z-12:13:26.787Z, 5.039 m deep, no report inside
S10 PASS 3 passes 14.838807/18.519983/14.781798 km; pass 2 exits at (51.000000,-3.132329) 08:15:30Z, vertex 3 (51.000000,-3.132329) 08:15:30Z
X1 PASS overlap_start (51.470000,-0.454300) 09:00:00Z/19:14:20Z; overlap_end (40.641300,-73.778100) 15:17:43Z/13:05:00Z; no crossings
X2 PASS crossing (55.000000,-45.000000) 13:41:58Z/13:42:28Z gap 30.0 s
X3 PASS crossing (88.712001,-108.768698) gap 4661.9 s
X4 PASS crossing (61.822942,-178.523172) gap 2276.4 s
X5 PASS FLT-1001 x FLT-1008 crossing (53.132767,-11.781169) gap 4857.8 s; FLT-1002 x FLT-1008 crossing (53.132768,-11.781174) gap 25601.2 s
X6 PASS crossing (61.174300,-149.998200) gap 52974.0 s
X7 PASS crossing (50.950078,-3.147727) gap 9024.9 s
X8 PASS no rows; the paths never come closer than 139.1 km; the other 36 pairs without rows have none either
FOUND SET == EXPECTED SET (14 zone passes in 12 of 100 trajectory-zone pairs; 9 intersection rows in 8 of 45 trajectory pairs)
SELF-CHECK OK (25 scenarios)
```

**Format.**

- Lines 1–25 read `<id> PASS <evidence>`. A failing scenario reads `<id> FAIL <evidence> | <failure>; <failure>`, and a missing row or record is reported as a FAIL, not a traceback.
- Line 26 compares the whole found set with the expected one; on a mismatch it reads `FOUND SET != EXPECTED SET (...) | <what is missing or unexpected>`.
- The last line is `SELF-CHECK OK (25 scenarios)` with exit 0, or `SELF-CHECK FAILED (<k> of 25 scenarios failed[; found set differs])` with exit 1.
- The evidence prints times and gaps rounded for display: `4661.9 s` is the key's 4661.85 s.

**What the checks assert.** Every scenario first compares its rows with the design's §7.5 values, held in the generator as `EXPECTED_PASSES` and `EXPECTED_INTERSECTIONS`. The comparison is the §10 rule set:

- kinds and row counts per pair exact;
- positions within 1 m (latitude only where the design gives only a latitude, as for S5's endpoints);
- times within 1 s;
- `distance_inside_km` within 1 m;
- gaps within 1 s.

Then come the scenario's own checks:

| Scenario | Its own checks |
|---|---|
| D1 | FLT-1001's raw first `coord` is `[-0.4543, 51.47]` and is stored as (51.47, -0.4543); every `length_km` is within 1 m of the design |
| D2 | FLT-1001 has a point at 11277.6 m; all 10 `radius_km` values match, and ZN-POLE's renders as `138.9`; every non-null `length_3d_km` is within 1 m |
| D3 | The first raw `ts` of FLT-1009 and FLT-1007 are as planted; FLT-1004's are all integers; every start and end is within 1 s; run 3 counts are (10, 0, 1, 9, 0, 0), with FLT-1002 the only update |
| D4 | FLT-1006's raw order is unsorted and its first point is 02:00:00Z; FLT-1005 goes 13 → 12; record 14 equals record 3; the duplicates of runs 1 and 2 are exactly index 14; 210 positions, 184 points and every point count |
| D5–D6 | `squawk` is present and FLT-1008 is stored; exactly FLT-1003's positions 2 and 3 are null and its `length_3d_km` is null |
| D7 | The rejections and counts of runs 1 and 2, and the table counts after run 2 |
| S3 | The gap is 3 h and 2550 km (±1 km); the pass lies inside the gap; no report is inside; the straight line passes outside, at 469.6 ± 0.1 km |
| S4 | No pass; the great circle is at 476.4 ± 0.1 km, the straight line at 0.10 ± 0.01 km (the best of 20,000 samples, refined by golden-section search between its neighbours), the lat/lon average at 0.13 ± 0.01 km |
| S7 | The closest approach is within 1 m of the boundary |
| S8 | No pass; the closest approach is +5.041 ± 0.01 m; FLT-1008 × ZN-SURVEY has no pass, at 0.236 ± 0.001 km; these two are the nearest pairs without a pass, and the next is more than 56 km out |
| S9 | The deepest point is -5.039 ± 0.01 m, and no FLT-1009 report is inside |
| S10 | Vertex 3's longitude is -3.132329, and it lies within 1 m of the 9.26 km boundary |
| X8 | No rows; the closest approach is 139.1 ± 0.1 km; exactly 36 other pairs have no rows |
| FOUND SET | The full set of (trajectory, zone, seq, entry kind, exit kind) and of (A, B, kind) equals the expected set; per-trajectory pass and intersection counts, per-zone pass and trajectory counts, and the after-analysis table counts all match |

## 12. Differences from the design record

None remain. DESIGN §7 was reconciled with the key on 2026-10-08; should the two ever disagree again, the answer key is right.

What the reconciliation changed in DESIGN, for traceability:

| Item | DESIGN before | Now (key and generator) |
|---|---|---|
| S5: FLT-1004 × ZN-POLE entry time (§7.5) | 07:29:12.180 | 07:29:12.181 (unrounded 07:29:12.180955) |
| S6: FLT-1007 × ZN-DATELINE entry time (§7.5) | 04:26:18.730 | 04:26:18.731 (unrounded 04:26:18.730888) |
| S10: FLT-1010 × ZN-SURVEY pass 2 exit time (§7.5) | 08:15:29.999 | 08:15:30 (unrounded 08:15:29.999524; the exit lies 2.9 cm before vertex 3, whose time is 08:15:30) |
| S3 and S9 wording (§7.5); the narrow-dip rule (§7.7) | "no sample inside"; the rule "catches S9" | "no position report inside": S3's pass holds more than 180 samples and S9's two, 3.351 m inside, so ordinary sign changes bracket both; the narrow-dip rule is a safety net that fires nowhere in this data (§11.3) |
| S4: the straight lat/lon line's closest approach to ZN-BAFFIN (§7.4, §7.5) | 0.11 km | 0.10 km (0.0997 km). 0.11 was the best of 20,000 samples; the generator now refines it (§11.6) |
| Gaps of X1's `overlap_end`, X3, X4, X5 and X7 (§7.5) | not stated, or to 0.1 s | the key's values: 7963.0, 4661.85, 2276.385, 4857.802 and 25601.161, 9024.867 s |
| Time format of the key (§7.7) | "millisecond precision" | rounded to the millisecond, `.000` left out on whole seconds (§9.2) |
| Self-check FOUND SET line (§7.7) | passes and intersections only | also the per-trajectory, per-zone and after-analysis counts |

The generator's `EXPECTED_PASSES` carries the three corrected times. It compares within 1 s, so its output and the four files did not change.
