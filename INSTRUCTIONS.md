# Airspace Track Analysis Service: Python coding exercise (3 hours)

## Context

Our airspace-awareness team is building a web map that shows where aircraft have flown, which airspace zones they passed through and where their tracks crossed. The map needs a backend service that stores aircraft tracks and airspace zones, runs a geospatial analysis over them, and serves the data and the results, read-only, to the web client. Build that service in Python, from scratch.

## Provided data

Two sample files are provided in `data/`.

`data/flights.json` holds aircraft position reports, grouped by flight. It is a JSON object with export metadata (`source`, `exported_at`) and a `flights` array with one record per flight:

| Field | Meaning |
|---|---|
| `flight_id` | identifier of the flight; required |
| `callsign` | the flight's callsign; may be absent |
| `aircraft.icao_type` | aircraft type (ICAO type designator) |
| `origin`, `destination` | departure and arrival airports (4-letter ICAO codes) |
| `positions[]` | the flight's position reports |
| `positions[].ts` | time of the report: ISO-8601 with a UTC offset, or Unix epoch seconds |
| `positions[].coord` | a position following GeoJSON conventions |
| `positions[].alt_ft` | altitude in feet, may be null |

`data/zones.json` holds circular airspace zones as a GeoJSON `FeatureCollection`, one feature per zone:

| Field | Meaning |
|---|---|
| `id` | identifier of the zone |
| `geometry` | a GeoJSON `Point`: the centre of the zone |
| `properties.name` | name of the zone |
| `properties.radius` | radius of the zone, in `properties.radius_unit` |
| `properties.radius_unit` | NM or km |

Both files may contain fields not listed here; ignore them.

**Data quality.** The files may contain invalid records, exact duplicates of records and of position reports, and unordered positions. A track needs at least two position reports. A record with any invalid field or position report is invalid as a whole: skip the entire record; do not repair it or drop individual reports. Keep one copy of exact duplicates, and report what you skipped and why.

## Requirements

1. Design a database schema for this data and create it with migrations.
2. Build an ingestion process that loads the provided files into the database; it does not have to go through the API. It must be repeatable: re-running it on the same input must not duplicate or change data, and every run should be auditable.
3. Expose read-only REST endpoints for the web client: list and detail endpoints for flights and for zones, and one for a flight's positions, with pagination and proper error responses.
4. Add structured logging in which all log lines of one API request can be correlated.
5. Compute the analysis defined below, store the results in the database, and include them in the API's data models.
6. Write automated tests.
7. Write a README that covers how to run the service, the assumptions you made, and how you used AI.

## Analysis definitions

- Treat the Earth as a sphere with radius R = 6371.0088 km. Unit conversions are exact: 1 NM = 1.852 km, 1 ft = 0.3048 m.
- Between two consecutive position reports of a flight (ordered by time), the aircraft flies along the shorter great-circle arc between them at constant speed. A flight's path is the sequence of these arcs.
- Flight length: the sum of the great-circle distances between consecutive positions, in km. (Bonus: a length that also accounts for altitude changes.)
- A zone is the set of points within its radius of its centre, measured as great-circle distance, boundary included.
- Zone entries and exits: for every flight and every zone, report each pass of the flight's path through the zone with its entry point and exit point (latitude, longitude) and the time the flight is at each point. If a flight starts inside a zone, that pass's entry is the flight's first position; if it ends inside, the exit is its last position. If the path only touches the boundary (it comes within 1 m of the boundary but never more than 1 m inside), report it as one pass whose entry and exit are the same point, marked as a touch.
- Track crossings: for every pair of flights, report each point where their paths intersect, with the time each flight is at that point. A position shared by both paths (for example a common waypoint, start or end) counts as an intersection. If two paths run along the same great circle for a stretch, report where the shared stretch starts and ends instead of individual crossing points.
- Times at points between two reports follow from constant speed: proportional to the distance travelled along the arc. Points less than 1 m apart are the same point.

## Environment and stack

We use FastAPI, SQLAlchemy with Alembic, PostgreSQL, and uv for dependencies and running. Similar modern alternatives (ORM, migrations, dependency management) are acceptable.

A PostgreSQL 16 server should be available at localhost:5432 (user `gis`, password `gis`, databases `gis` and `gis_test`); if it is not, use another SQL database through the same ORM and migrations and say so.

## AI assistance

Two built-in assistants are available in the editor, a smaller and a larger model, with a limited token budget. You may use them, and only them. How you use them is part of the evaluation.

## Deliverables

- Code, migrations, tests and the README, committed to this repository.
- The commands to set up, ingest, analyze, serve and test.
- A short note on how you used AI.

## Evaluation

We will look at the correctness of the analysis; data modelling (keys, constraints); ingestion robustness and repeatability; API design; observability; tests; code clarity; judgement in using AI; and the trade-offs you explain.

## Time

3 hours. Prioritize a working end-to-end slice over completeness; note what you would do next. Where this brief leaves a choice open, make a reasonable one and record it in your README.
