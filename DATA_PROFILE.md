## data/flights.json
- top level: object; records: "flights" (list, 15 items); other keys: source, exported_at

| path | types | n | nulls | min | max | distinct | example |
|------|-------|---|-------|-----|-----|----------|---------|
| aircraft.icao_type | str | 15 | 0 |  |  | 13 | B77W |
| callsign | str | 15 | 0 |  |  | 14 | PRAC101 |
| destination | str | 15 | 0 |  |  | 11 | KJFK |
| flight_id | str | 14 | 0 |  |  | 13 | FLT-1001 |
| origin | str | 15 | 0 |  |  | 10 | EGLL |
| positions[].alt_ft | int | 210 | 2 | 0 | 39000 |  | 0 |
| positions[].coord[0] | float | 210 | 0 | -166.203515 | 178.303493 |  | -0.4543 |
| positions[].coord[1] | float | 210 | 0 | 35.5494 | 91.2 |  | 51.47 |
| positions[].ts | int, str | 210 | 0 | 1714543200 | 1714558040 | 136 | 2024-05-01T09:00:00Z |
| squawk | str | 1 | 0 |  |  | 1 | 7000 |
- repeated keys: flight_id FLT-1004 x2 callsign PRAC104 x2
- timestamp forms: positions[].ts: Z 141 epoch s 28 ±HH:MM 41

## data/zones.json
- top level: object; records: "features" (list, 11 items); other keys: type, name

| path | types | n | nulls | min | max | distinct | example |
|------|-------|---|-------|-----|-----|----------|---------|
| geometry.coordinates[0] | float | 11 | 0 | -179.95 | 0.0 |  | -0.4543 |
| geometry.coordinates[1] | float | 11 | 0 | 40.6413 | 90.0 |  | 51.47 |
| geometry.type | str | 11 | 0 |  |  | 1 | Point |
| id | str | 11 | 0 |  |  | 11 | ZN-LHR |
| properties.name | str | 11 | 0 |  |  | 11 | London Heathrow control zone |
| properties.radius | float, int | 11 | 0 | -5 | 75 |  | 25 |
| properties.radius_unit | str | 11 | 0 |  |  | 2 | NM |
| type | str | 11 | 0 |  |  | 1 | Feature |
- repeated keys: none

