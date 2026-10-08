# PLAN
## 1. Conventions
- Tokens written <NAME=value> in a prompt mean: use value. If PLAN.md §3 "Placeholder values" gives NAME a different value, use PLAN's value and say so in your reply.
- Stack: Python 3.12, code stays 3.11-compatible (no `type X = ...`, no `class C[T]`); uv only (`uv add`, `uv run`; never pip, never requirements.txt); FastAPI + uvicorn; SQLAlchemy 2.x typed ORM; Alembic; psycopg 3; Pydantic v2 + pydantic-settings; structlog; pytest + fastapi.testclient; ruff.
- Layout: package gisdb in src/gisdb/ (config, db, models, logging_config, records, ingest, geodesy, analysis, cli, api/{app,deps,schemas,routes}); migrations/; tests/; scripts/. Import as gisdb.<module>. No extra layers (no repositories, services packages, DI frameworks).
- SQLAlchemy: class Base(DeclarativeBase) in models.py with the naming convention; Mapped[...], mapped_column(), relationship(), select(), session.scalars()/.execute()/.get(). NEVER declarative_base(), Column() in models, session.query(), engine.execute().
- Sync only: create_engine, sessionmaker, Session; endpoints are plain def. NEVER AsyncSession, create_async_engine, asyncpg, aiosqlite, async def endpoints.
- Database URL only from settings (GISDB_DATABASE_URL). Postgres URLs are postgresql+psycopg://. NEVER postgresql:// or psycopg2.
- Keys: id = internal integer PK, never in the API; <x>_id = natural string key used in URLs and JSON (exception: ingest_run_id and analysis_run_id in CLI output and logs are the runs' integer id); <x>_pk = integer FK to <x>s.id. Units in names: _km, _m, _s. Times are timezone-aware UTC.
- Types: UTCDateTime and JSONType from gisdb.models; server_default=text("CURRENT_TIMESTAMP"), NEVER func.now(); String(n) + named CheckConstraint instead of Enum; no ARRAY, no Geography.
- Coordinates: in code a position is (lat, lon) in degrees; the source's coordinate layout (PLAN §3, COORD_ORDER) is unpacked only at the JSON boundary in records.py.
- Pydantic v2: model_config = ConfigDict(...), field_validator, model_validator, model_validate, model_dump. NEVER class Config, orm_mode, @validator, @root_validator, parse_obj, .dict(). Settings: from pydantic_settings import BaseSettings, SettingsConfigDict.
- FastAPI: Annotated parameters (Annotated[Session, Depends(get_session)], Annotated[int, Query(ge=1, le=500)] = 50); GET routes only; NEVER @app.on_event.
- Logging: log = structlog.get_logger(__name__); log.info("area.object.verb", key=value) with names from PLAN §7; logs go to stderr; NEVER print() in src/ (a CLI writes its one JSON result line with sys.stdout.write); never log whole payloads or coordinate arrays.
- Errors: catch specific exceptions (e.g. sqlalchemy.exc.SQLAlchemyError, json.JSONDecodeError); `except Exception` only to log.exception(...) or to re-raise; inside except, raise NewError(...) from exc.
- Geo: a sphere with the radius in PLAN §8 (EARTH_RADIUS_KM); all geodesy in src/gisdb/geodesy.py with math only; NEVER interpolate, average or subtract raw lat/lon.
- Migrations: the human runs autogenerate and reviews. NEVER create or edit files in migrations/versions/.
- Tests: NEVER weaken, skip or delete a test or an expected value to make it pass; if a test looks wrong, stop and say why.
- Scope: change only the files the prompt names; add dependencies only when the prompt names them; never run git; never leave a server running; after 3 failed attempts at the same command, stop and report.
- Lint: once pyproject.toml exists, run uv run ruff format and uv run ruff check --fix on the .py files you changed before replying, and fix what remains by hand (lines of at most 100 characters; split a long string in src/ into implicitly concatenated pieces).
- Replies: changed files (one line each) plus the last 15 lines of any command you ran; never paste whole files back.
## 2. Brief
- R1 "Design a database schema for this data and create it with migrations."
- R2 "Build an ingestion process that loads the provided files into the database; it does not have to go through the API. It must be repeatable: re-running it on the same input must not duplicate or change data, and every run should be auditable."
- R3 "Expose read-only REST endpoints for the web client: list and detail endpoints for flights and for zones, and one for a flight's positions, with pagination and proper error responses."
- R4 "Add structured logging in which all log lines of one API request can be correlated."
- R5 "Compute the analysis defined below, store the results in the database, and include them in the API's data models."
- R6 "Write automated tests."
- R7 "Write a README that covers how to run the service, the assumptions you made, and how you used AI."
- R8 (analysis, verbatim) "Treat the Earth as a sphere with radius R = 6371.0088 km. Unit conversions are exact: 1 NM = 1.852 km, 1 ft = 0.3048 m."
- R9 (analysis, verbatim) "Between two consecutive position reports of a flight (ordered by time), the aircraft flies along the shorter great-circle arc between them at constant speed. A flight's path is the sequence of these arcs."
- R10 (analysis, verbatim) "Flight length: the sum of the great-circle distances between consecutive positions, in km. (Bonus: a length that also accounts for altitude changes.)"
- R11 (analysis, verbatim) "A zone is the set of points within its radius of its centre, measured as great-circle distance, boundary included."
- R12 (analysis, verbatim) "Zone entries and exits: for every flight and every zone, report each pass of the flight's path through the zone with its entry point and exit point (latitude, longitude) and the time the flight is at each point. If a flight starts inside a zone, that pass's entry is the flight's first position; if it ends inside, the exit is its last position. If the path only touches the boundary (it comes within 1 m of the boundary but never more than 1 m inside), report it as one pass whose entry and exit are the same point, marked as a touch."
- R13 (analysis, verbatim) "Track crossings: for every pair of flights, report each point where their paths intersect, with the time each flight is at that point. A position shared by both paths (for example a common waypoint, start or end) counts as an intersection. If two paths run along the same great circle for a stretch, report where the shared stretch starts and ends instead of individual crossing points."
- R14 (analysis, verbatim) "Times at points between two reports follow from constant speed: proportional to the distance travelled along the arc. Points less than 1 m apart are the same point."
- R15 (data quality) "The files may contain invalid records, exact duplicates of records and of position reports, and unordered positions. A track needs at least two position reports. A record with any invalid field or position report is invalid as a whole: skip the entire record; do not repair it or drop individual reports. Keep one copy of exact duplicates, and report what you skipped and why."
- R16 (stack) "We use FastAPI, SQLAlchemy with Alembic, PostgreSQL, and uv for dependencies and running. Similar modern alternatives (ORM, migrations, dependency management) are acceptable. A PostgreSQL 16 server should be available at localhost:5432 (user `gis`, password `gis`, databases `gis` and `gis_test`); if it is not, use another SQL database through the same ORM and migrations and say so."
- R17 (AI) "Two built-in assistants are available in the editor, a smaller and a larger model, with a limited token budget. You may use them, and only them. How you use them is part of the evaluation."
- R18 (deliverables) "Code, migrations, tests and the README, committed to this repository. The commands to set up, ingest, analyze, serve and test. A short note on how you used AI."
- R19 (evaluation, time) "We will look at the correctness of the analysis; data modelling (keys, constraints); ingestion robustness and repeatability; API design; observability; tests; code clarity; judgement in using AI; and the trade-offs you explain. 3 hours. Prioritize a working end-to-end slice over completeness; note what you would do next. Where this brief leaves a choice open, make a reasonable one and record it in your README."
## 3. Data mapping
### Names and files
| brief term -> generic name | file | record list | natural key (JSON type) |
|---|---|---|---|
| flight -> trajectories (key trajectory_id); positions[] -> trajectory_points | data/flights.json | `flights` (15 records) | `flight_id`, JSON string (14 present, 13 distinct: FLT-1004 twice; one record has none) |
| zone -> zones (key zone_id) | data/zones.json | `features` (11 records) | `id`, JSON string (11 distinct) |
### Fields
| source field | column | type | unit / conversion |
|---|---|---|---|
| flights[].flight_id | trajectories.trajectory_id | String(64) NOT NULL UNIQUE | none |
| flights[].callsign, aircraft.icao_type, origin, destination | trajectories.callsign, aircraft_type, origin, destination | String(32), String(8), String(4), String(4); all NULL | none; may be absent |
| positions[].ts | trajectory_points.ts | UTCDateTime NOT NULL | to UTC (see timestamps) |
| positions[].coord[0] | trajectory_points.lon | Float NOT NULL | degrees, [-180, 180] |
| positions[].coord[1] | trajectory_points.lat | Float NOT NULL | degrees, [-90, 90] |
| positions[].alt_ft | trajectory_points.alt_m | Float NULL | feet to metres, x 0.3048 (exact); null stays NULL (2 of 210) |
| features[].id | zones.zone_id | String(64) NOT NULL UNIQUE | none |
| properties.name | zones.name | String(128) NULL | none |
| geometry.coordinates[0], [1] | zones.center_lon, center_lat | Float NOT NULL | degrees; geometry.type must be "Point" |
| properties.radius with properties.radius_unit | zones.radius_km | Float NOT NULL | NM x 1.852, km x 1; must land in (0, 10000) km (profile min is -5) |
| other keys (squawk, source, exported_at, type, name, ...) | none | none | ignored; never hashed |
### Coordinates and timestamps
- Layout [lon, lat] (GeoJSON), unpacked only in records.py. Zones: coordinates[0] spans -179.95..0.0, which goes beyond ±90, so it is the longitude; coordinates[1] spans 40.6413..90.0 (latitude; 90.0 is a pole and -179.95 lies next to the antimeridian). Flights: both indices exceed ±90 at an extreme (coord[0] -166.203515..178.303493, coord[1] max 91.2), so the landmark decides.
- Landmark: London Heathrow (EGLL, zone ZN-LHR) appears as index 0 = -0.4543, index 1 = 51.47 and sits at 51.47 N, 0.4543 W; swapped it would be 0.45 S, 51.47 E (open Indian Ocean). So index 0 = lon, index 1 = lat, and 91.2 is an invalid latitude (out_of_range). Zones' index-1 minimum 40.6413 is KJFK's latitude.
- Timestamps (210 position reports): `Z` 141, `±HH:MM` 41, epoch seconds as JSON number 28, naive 0; the profile's ts min/max is 1714543200..1714558040 (2024-05-01T06:00:00Z..10:07:20Z). Naive times do NOT count as UTC: rejected as invalid_timestamp (the brief promises an offset or epoch).
### Validation -> reason codes
- One code per rejected record; first failing check wins: key, other record fields, positions in file order (ts, coord, alt_ft), then the record-level checks; detail names the field path.
- invalid_file: path missing or unreadable, not UTF-8 JSON, top level not an object, record list (`flights`/`features`) absent or not a list (file-level row, record_index NULL).
- missing_field: absent or null flight_id, positions, ts, coord (flights); id, geometry, geometry.coordinates, properties, properties.radius, properties.radius_unit (zones).
- invalid_value: record not an object, or wrong JSON type/format (bool, NaN, Infinity are never numbers): ids not a str of 1-64 chars; callsign str 1-32; icao_type ^[A-Z0-9]{2,4}$; origin/destination ^[A-Z]{4}$; name str 1-128; positions not a list; coord not exactly 2 numbers; alt_ft not a number or null; geometry.type not "Point"; radius_unit not "NM" or "km" (case-sensitive).
- out_of_range: lat outside [-90, 90]; lon outside [-180, 180]; alt_ft outside [-2000, 100000]; radius_km not in (0, 10000) after conversion.
- invalid_timestamp: ts not an ISO-8601 string with Z or ±HH:MM, not a number, naive, or an instant outside 1970-01-01..2099-12-31 UTC.
- Record-level: fewer than 2 distinct position reports after exact-duplicate removal (also an empty list) -> too_few_points; same instant with different lat/lon/alt -> conflicting_points; same natural key as an earlier accepted record of the run with different content -> duplicate_key_conflict.
### Placeholder values
| NAME | value |
|---|---|
| DATA_DIR | data |
| DB_URL | postgresql+psycopg://gis:gis@localhost:5432/gis |
| TEST_DB_URL | postgresql+psycopg://gis:gis@localhost:5432/gis_test |
| TRAJECTORY_SOURCE | file data/flights.json; record list `flights`; natural key `flight_id` (JSON string) |
| POINT_SOURCE | list `positions[]` of each flight; fields `ts`, `coord` ([lon, lat]), `alt_ft` |
| POINT_ATTRS | none (ts, coord and alt_ft feed only ts, lon, lat, alt_m) |
| ZONE_SOURCE | file data/zones.json; record list `features`; natural key `id` (JSON string) |
| TRAJECTORY_ATTRS | callsign → callsign String(32); aircraft.icao_type → aircraft_type String(8); origin → origin String(4); destination → destination String(4); all NULL allowed |
| ZONE_ATTRS | properties.name → name String(128); NULL allowed |
| COORD_ORDER | [lon, lat] |
| TIME_FORMATS | ISO-8601 string with `Z` (141) or `±HH:MM` (41) offset; Unix epoch seconds as JSON number (28); no naive form accepted |
| ALT_UNIT | positions[].alt_ft, feet (alt_m = alt_ft x 0.3048) |
| RADIUS_UNITS | radius field `properties.radius`; unit field `properties.radius_unit` with `NM` (x 1.852 km) or `km` (x 1) |
| EARTH_RADIUS_KM | 6371.0088 |
| TOL_KM | 0.001 |
| SAMPLE_TRJ | FLT-1003 |
## 4. Schema
- Names: tables trajectories, trajectory_points, zones (§3) plus the run and result tables below; natural keys trajectory_id, zone_id String(64) UNIQUE; integer id PK on every table except trajectory_points; FKs named <x>_pk (ingest_run_pk, trajectory_pk, zone_pk, analysis_run_pk, a_pk, b_pk). Every table has created_at UTCDateTime NOT NULL server_default CURRENT_TIMESTAMP; trajectories and zones also updated_at. Named constraints from the naming convention; CHECKs named ck_<table>_<rule>.
- 0001 core (message "core schema"; the human runs alembic revision --autogenerate and reviews):
  - ingest_runs: status String(16) CHECK in (running, succeeded, failed); started_at, finished_at (NULL until finished); files JSON [{path, sha256, records}]; seen, inserted, updated, unchanged, duplicates, rejected Integer NOT NULL default 0 CHECK >= 0; error Text NULL; CHECK status <> 'succeeded' OR seen = inserted + updated + unchanged + duplicates + rejected.
  - ingest_rejections: ingest_run_pk FK ON DELETE CASCADE, indexed; file String(512); record_index Integer NULL; record_key String(64) NULL; reason_code String(32) CHECK in the 8 codes of §3; detail Text; payload JSON NULL (the raw record).
  - trajectories: trajectory_id, callsign, aircraft_type, origin, destination (§3); started_at, ended_at UTCDateTime NOT NULL with CHECK ended_at > started_at; point_count Integer CHECK >= 2; content_hash String(64) NOT NULL; index on started_at.
  - trajectory_points: PK (trajectory_pk FK ON DELETE CASCADE, seq Integer CHECK >= 0, 0-based in ts order); ts, lat, lon, alt_m (§3) with range CHECKs on lat and lon; UNIQUE (trajectory_pk, ts).
  - zones: zone_id, name (§3); center_lat, center_lon Float NOT NULL with range CHECKs; radius_km Float NOT NULL CHECK > 0 AND < 10000; content_hash String(64) NOT NULL.
- 0002 analysis (message "analysis schema"); each analysis run replaces all result rows:
  - analysis_runs: status (as ingest_runs); started_at, finished_at; algorithm_version String(16) = "1"; earth_radius_km, tol_km Float; trajectories, zones, zone_passes, intersections Integer counts; error Text NULL.
  - trajectory_metrics: trajectory_pk FK UNIQUE (CASCADE), analysis_run_pk FK; length_km, length_3d_km, duration_s Float CHECK >= 0; zone_pass_count, intersection_count Integer CHECK >= 0; input_hash String(64) = trajectories.content_hash when analysed (audit only).
  - zone_passes: analysis_run_pk, trajectory_pk, zone_pk FKs (CASCADE, trajectory_pk and zone_pk indexed); entry_kind CHECK in (crossing, track_start, touch); exit_kind CHECK in (crossing, track_end, touch); entry_lat, entry_lon, entry_time, entry_alt_m and exit_lat, exit_lon, exit_time, exit_alt_m (alt NULL allowed); distance_inside_km, duration_s Float CHECK >= 0; CHECK (entry_kind = 'touch') = (exit_kind = 'touch').
  - trajectory_intersections: analysis_run_pk; a_pk, b_pk FKs to trajectories.id (CASCADE, indexed) with CHECK a_pk < b_pk; kind CHECK in (crossing, overlap_start, overlap_end); lat, lon Float; time_a, time_b UTCDateTime; time_gap_s Float CHECK >= 0.
## 5. Ingestion
- Command: `gisdb ingest [PATH ...]` (default data). A PATH is a file or a directory (non-recursive, *.json by name); a record list `flights` makes trajectories, `features` makes zones. One ingest_runs row per call; the one JSON result line is {ingest_run_id, status, seen, inserted, updated, unchanged, duplicates, rejected}.
- Per record (file order, record_index 0-based): validate (§3 codes) -> normalize -> sha256 -> upsert. Normalize: ts to UTC; (lat, lon) degrees; alt_m = alt_ft x 0.3048; radius_km; positions sorted by ts, exact duplicates (same instant, lat, lon, alt) collapsed to one, seq 0..n-1; started_at, ended_at, point_count derived. content_hash = sha256 hex of canonical JSON (sorted keys, no spaces, ts as ISO-8601 UTC, floats by repr) of the normalized record, ignored source keys excluded.
- Upsert by natural key: absent -> insert (inserted); present with equal content_hash -> unchanged, no write; present with a different hash -> update the row and replace its points (updated). A rejected record never touches an existing row. Re-running the same input gives inserted 0, updated 0 and only a new ingest_runs (+ ingest_rejections) row.
- Duplicates: same key and same hash as an earlier accepted record of this run -> duplicates + 1, event ingest.record.duplicate, skipped. Same key, different hash -> the later record is rejected duplicate_key_conflict (first wins).
- Counters: seen counts every record visited plus one per invalid file (which also counts as rejected); when succeeded, seen = inserted + updated + unchanged + duplicates + rejected.
- Transactions: the run row is committed first (running); loading all files and writing rejections is one transaction; then counters, finished_at and status succeeded are set. Bad files or records never fail the run (exit 0). On SQLAlchemyError or any unexpected error: roll back the load, mark the run failed with the error text, log ingest.run.failed, exit 1; bad usage exits 2.
## 6. API
- GET only, no prefix, JSON (other methods 405). Every response, errors included, carries X-Request-ID. Pagination: limit (int 1-500, default 50) and offset (int >= 0, default 0); envelope {items, total, limit, offset}, total = rows matching the filters.
- GET /health -> 200 {"status": "ok"} after SELECT 1; DB failure -> 503 {"status": "unavailable"} + health.check.failed.
- GET /trajectories: limit, offset, started_after, started_before (ISO-8601 with offset, naive -> 422; inclusive bounds on started_at); order started_at, trajectory_id. GET /trajectories/{trajectory_id} -> detail. GET /trajectories/{trajectory_id}/points: limit (default 500, max 500), offset; items {seq, ts, lat, lon, alt_m} in seq order.
- GET /zones: limit, offset; order zone_id. GET /zones/{zone_id} -> detail.
- TrajectoryOut (list item): trajectory_id, callsign, aircraft_type, origin, destination, started_at, ended_at, point_count, length_km, length_3d_km, duration_s, zone_pass_count, intersection_count (the last five null until analyzed). TrajectoryDetail = TrajectoryOut + zone_passes[] + intersections[] (null until analyzed). ZoneOut: zone_id, name, center_lat, center_lon, radius_km, pass_count (null until analyzed). ZoneDetail = ZoneOut + passes[] (null until analyzed).
- zone_passes[] item: zone_id, entry {kind, lat, lon, time, alt_m}, exit {kind, lat, lon, time, alt_m}, distance_inside_km, duration_s, ordered by entry time; passes[] item: the same with trajectory_id instead of zone_id. intersections[] item, seen from the requested trajectory: other_trajectory_id, kind, lat, lon, time, other_time, time_gap_s; ordered by time, other_trajectory_id, kind.
- Errors: 404 {"detail": "trajectory '<id>' not found"} or "zone '<id>' not found" (also for /points); 422 FastAPI's default {"detail": [...]} for bad parameters; 500 {"detail": "Internal server error"} (logged as http.unhandled_error).
- Times are ISO-8601 UTC with Z; numbers are served as stored (no rounding); id and *_pk never appear.
## 7. Logging
| event | level | fields |
|---|---|---|
| app.startup | info | version, db_dialect |
| http.request | info | request_id, method, path, status_code, duration_ms |
| http.unhandled_error | error | exception |
| health.check.failed | warning | error |
| ingest.run.started | info | ingest_run_id, paths |
| ingest.file.read | info | ingest_run_id, file, sha256, records |
| ingest.record.rejected | warning | ingest_run_id, file, record_index, record_key, reason_code |
| ingest.record.duplicate | info | ingest_run_id, file, record_index, record_key |
| ingest.run.finished | info | ingest_run_id, status, seen, inserted, updated, unchanged, duplicates, rejected, duration_ms |
| ingest.run.failed | error | ingest_run_id, error |
| analysis.run.started | info | analysis_run_id, trajectories, zones, algorithm_version |
| analysis.run.finished | info | analysis_run_id, status, trajectories, zone_passes, intersections, duration_ms |
| analysis.run.failed | error | analysis_run_id, error |
- Setup: structlog JSON lines on stderr (keys timestamp ISO-8601 UTC, level, event, logger, plus the fields above); level from GISDB_LOG_LEVEL (default INFO); configure once at startup (app.startup comes from the FastAPI lifespan) and at CLI start; stdout carries only the CLI's one JSON result line; never log payloads or coordinate arrays; record_key is null when the record has none.
- Correlation: the request-id middleware takes an incoming X-Request-ID matching ^[A-Za-z0-9._-]{1,64}$, else uuid4().hex; binds request_id, method and path with structlog.contextvars before the handler runs, logs http.request once per request (4xx, 5xx and /health too), clears the context afterwards and echoes the header. So http.unhandled_error and every line logged while a request is handled share its request_id. A CLI run binds its integer ingest_run_id or analysis_run_id the same way.
## 8. Analysis
- Model: sphere with R = EARTH_RADIUS_KM = 6371.0088 km (§3); a position is a unit n-vector from (lat, lon); distance = R x atan2(|a x b|, a . b); geodesy.py is math only and handles poles and the antimeridian. Full recompute in one transaction: the analysis_runs row is committed first (running), then all result rows are deleted and re-inserted and the run is marked succeeded; an error rolls back (old results stay) and marks it failed. TOL_KM = 0.001.
- Definitions (brief wording, generic names):
  - Path: between two consecutive trajectory_points (ordered by ts) the trajectory flies along the shorter great-circle arc at constant speed; its path is the sequence of these arcs.
  - length_km = sum of the great-circle distances between consecutive points. length_3d_km (bonus) = sum over segments of sqrt(d^2 + (delta_alt_m / 1000)^2), delta_alt = 0 when an end altitude is NULL. duration_s = ended_at - started_at.
  - Zone = the points within radius_km of (center_lat, center_lon), measured as great-circle distance, boundary included (a first or last point within TOL_KM of the boundary counts as inside).
  - Zone pass = one row per pass of a trajectory's path through a zone, with entry and exit point (lat, lon) and the time at each. Starts inside: entry = its first point (kind track_start); ends inside: exit = its last point (track_end); other ends are boundary crossings (crossing). Touch: the path comes within TOL_KM of the boundary but is never more than TOL_KM inside (depth = radius_km - nearest distance to the centre; -TOL_KM <= depth <= TOL_KM): one pass, entry = exit = the closest point, both kinds touch, distance_inside_km 0, duration_s 0. Depth below -TOL_KM is no pass.
  - Intersections = for every pair of trajectories (a_pk < b_pk), each point where their paths intersect, with the time each is at that point (kind crossing). A point shared by both paths (common waypoint, start or end) counts. Two arcs on the same great circle (all four endpoints within TOL_KM of the other arc's great circle) give the shared stretch as one overlap_start and one overlap_end row; a stretch shorter than TOL_KM is one crossing.
  - Times between two reports follow constant speed: t = t_i + (arc distance from point i / segment length) x (t_i+1 - t_i); entry/exit alt_m is interpolated the same way (NULL if an end is NULL). Points less than TOL_KM apart are the same point: one row, earliest time.
- TOL_KM arithmetic: the finest coordinates have N = 6 decimals (e.g. -166.203515; shorter ones such as 51.47 are exact as given) -> 10^-6 degrees x 111.2 km/degree = 0.0001112 km (0.11 m); TOL_KM = max(0.001 km, 0.0001112 km) = 0.001 km, the brief's 1 m. One value serves "same point", the touch band and the overlap test.
### Where results are stored and served
| result | stored (0002) | served (API) |
|---|---|---|
| length_km, length_3d_km, duration_s | trajectory_metrics, same names | TrajectoryOut, same names; null without a metrics row |
| zone_pass_count, intersection_count | trajectory_metrics (rows counted in zone_passes and trajectory_intersections) | TrajectoryOut, same names; ZoneOut.pass_count = zone_passes rows of the zone, null until a run succeeded |
| zone passes | zone_passes | TrajectoryDetail.zone_passes[], ZoneDetail.passes[] |
| intersections | trajectory_intersections | TrajectoryDetail.intersections[] (both members of a pair see the row) |
- Test edges from the profile: antimeridian arc (lon 178.303493 toward -179.x), zone at lat 90.0, zone centre lon -179.95, exact-boundary and 1 m touch, start inside, zero-length segment, shared waypoint.
## 9. Commands
- migrate: uv run alembic upgrade head
- ingest: uv run gisdb ingest [PATH ...] (default data; one JSON result line, §5)
- analyze: uv run gisdb analyze (one JSON line {analysis_run_id, status, trajectories, zones, zone_passes, intersections})
- stats: uv run gisdb stats (one JSON line: row count per table, last ingest and analysis run, rejected_by_code of the last ingest run)
- serve: uv run gisdb serve [--host 127.0.0.1] [--port 8000]
- test: uv run pytest -q
- verify: bash scripts/verify.sh [DATA_DIR] (last line VERIFY OK)
- Dev database URL (default of GISDB_DATABASE_URL): postgresql+psycopg://gis:gis@localhost:5432/gis
- Test database URL: postgresql+psycopg://gis:gis@localhost:5432/gis_test (database name contains "test"; tests abort otherwise, run alembic upgrade head on it once per session and truncate tables between tests)
## 10. Decisions and open questions
- A1. Generic names everywhere (trajectory = flight, URLs /trajectories); the README maps the brief's terms. Reason: one vocabulary in code, tables and API; the brief fixes no URLs.
- A2. Naive timestamps are invalid, never assumed UTC (0 in the sample). Reason: the brief promises an offset or epoch, and a guess could shift a track by hours.
- A3. Required: flight_id, positions (each with ts and coord); zone id, geometry, radius, radius_unit. Optional but validated when present: callsign, icao_type, origin, destination, name. Reason: the brief names only flight_id as required and callsign as optional.
- A4. Same key twice in a run: same content = duplicate; different content keeps the first and rejects the later (duplicate_key_conflict). Reason: deterministic, no merge guessing; FLT-1004 is the sample case.
- A5. A rejected record never changes or deletes an existing row. Reason: a bad re-export must not damage good data.
- A6. Exact duplicate position reports collapse to one (not counted separately: the run reports skipped records, i.e. duplicates and rejections with reason codes; counting collapsed reports is a next step); the same instant with different data rejects the whole record (conflicting_points). Reason: the brief allows dropping exact duplicates only.
- A7. Strict bounds: alt_ft [-2000, 100000], radius_km (0, 10000), instants 1970..2099, case-sensitive units, ICAO formats. Reason: catches sign, unit and millisecond-epoch errors; loosen in one place if the data disagrees.
- A8. A NULL altitude stays NULL: 3D length counts that segment's altitude change as 0 and entry/exit alt_m is NULL. Reason: never invent data.
- A9. Results are a snapshot of the last successful analyze; ingest does not clear them, so run analyze after ingest (verify.sh does); fields stay null until then. Reason: simplest consistent rule for 3 hours; staleness handling is the first next step.
- A10. /points defaults to limit 500, other lists to 50. Reason: a map draws a whole path in one call.
- A11. Stationary reports (equal positions at different times) are kept; a point's time is the earliest report there. Reason: keeps the data as given and the time rule deterministic.
- A12. Last resorts, each costing a §2 requirement (taken only at its tripwire; NOTES "Known limitations" names it): cut 7 (R12 touch, R13 overlap) and cut 9 (R15 report what was skipped and why); never skip P4.2 at tripwire 87 (R3 zone endpoints). Cut 6 is not one: R10's 3-D length is a bonus. Reason: they drop stated requirements.
- A13. The other cuts give 21 min (1: 2, 2: 2, 3: 1, 4: 4, 5: 6, 6: 1, 8: 3, 10: 2), 15 of them after minute 105 (cuts 1, 3, 4, 5, 10). Reason: the time budget, recounted without the last resorts.
- Q1. FLT-1004 appears twice (callsign PRAC104 twice): if the copies differ, keep the first (assumed), reject both, or take the last?
- Q2. Should a timestamp without an offset be rejected (assumed) or read as UTC?
- Q3. May the API use the generic names (/trajectories, assumed) or should the web client see /flights?
- Q4. Is length_3d_km = sum of sqrt(d^2 + delta_alt^2) per segment acceptable, or should arcs follow radius R + altitude?
- Q5. Should analysis run automatically after each ingest (assumed: on demand with gisdb analyze)?
## 11. Status
- [x] Phase 0: Orient and plan
- [ ] Phase 1: Project setup
- [ ] Phase 2: Database models and migrations
- [ ] Phase 3: JSON ingestion
- [ ] Phase 4: Read-only API
- [ ] Phase 5: Structured logging
- [ ] Phase 6: Geospatial analysis
- [ ] Phase 7: Tests and verification
