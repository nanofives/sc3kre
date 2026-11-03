# stationwarn RESULTS (2026-11-03): poorly connected stations are flagged in the city, in "?" and on Cuadros. PASS

Owner: "add an indicator when a station of any kind can't receive passengers because it's poorly connected".
Rule and RVAs: `re/analysis/STATION_RULE.md`. Code: `re/harness/src/sc3resize_stationwarn.c` (block STATIONWARN in
sc3resize). Off switch `SC3RESIZE_STATIONWARN=0` (checked: log says off, no scan, no marker). `_MARK=0` no marker,
`_BLINK=0` steady marker, `_LOG=1` one line per flagged station per scan.

## What the player sees

| where | what | picture |
|---|---|---|
| city view | the station and the ground under it blink red (the game's own cell highlighter, the red the tools use for "refused"), about 0.7 s on / 0.7 s off | `owner_shots/1_*`, `4_*`, `7_*` |
| "?" dialog | one red row per reason: "Sin pasajeros: no toca la via / no toca el metro / no toca via ni metro / via sin otra estacion / metro sin otra estacion / sin calle ni edificios / sin calle al lado (bus)". A connected station gets "Conexion: correcta" | `2_*`, `3_*`, `5_*`, `6_*` |
| Cuadros, Transporte tab | "Estaciones sin conexion: N de M" in red, or "Estaciones: M, todas conectadas" | `8_*` |

The check is static (the router's rule read from the map), rescanned every 3 s, about 0 ms on a 256 map. No measured
trip count is used for the flags. The marker cannot use the game's flashing outage icon: that display is power-only
(SIMSPR `0x1003db3d`, one image set), so it would read as "no power".

## Placement cases (Berlin, dev tree, posted input and game calls only)

| case | built | flagged | "?" row | stock "Pasajeros por dia" |
|---|---|---|---|---|
| train station one cell off the track (180,127) | place_direct 0xED | no toca la via | yes | 0 |
| same, gap closed with one rail cell (181,126) | nb_drive build 2 | not flagged | Conexion: correcta | 17 after about 11 game months |
| train station on a 2-cell rail stub, no road (25,78) | 0xED + rail 27..28,78 | via sin otra estacion + sin calle ni edificios | 2 rows | 0 |
| subway station, no tunnel, road beside it (25,81) | 0xE9 | no toca el metro | yes | 0 |
| bus stop in the prison yard (30,80) / (31,80) | 0x1F96 | sin calle al lado | not opened | 0 |
| bus stop beside a road (177,131) | 0x1F96 | not flagged | not opened | not read |
| rail-subway | not placeable with place_direct (it is a network piece) | covered by the census below | | |

## Census: 7 shipped cities, every station (each loaded, unpaused, about 75 s)

Usage value = the station cell's density from the transit layer getter `vt+0x60(x, z, &b, 0x10)` (the stock per-cell
rows read it, SimTransit `0x1000b472`), diagnostic only.

| city | stations | flagged | flagged with usage 0 | not flagged with usage > 0 |
|---|---|---|---|---|
| Berlin | 86 | 2 (subway, no road, no lot reach) | 2 | 77 of 84 |
| London | 284 | 3 | 2 | 250 of 281 |
| Seoul | 75 | 1 (rail-subway off the track) | 1 | 74 of 74 |
| Sacramento | 123 | 3 (rail, no road, no lot reach) | 1 | 101 of 120 |
| Madrid | 63 | 0 | | 63 of 63 |
| Moscow | 161 | 3 | 3 | 156 of 158 |
| Frankfurt | 88 | 0 | | 87 of 88 |
| total | 880 | 12 | 9 | 808 of 868 |

The 3 flagged stations with usage above 0:

- Sacramento rail stations (149,4) usage 1 and (228,11) usage 19: Sacramento has bus stops, and a station hands
  arriving trips to a neighbouring bus stop (`0x10007fe9`). Fixed after the census: a neighbouring bus stop now counts
  as a way out (`sin calle ni edificios` no longer fires there). Not re-measured in Sacramento.
- London rail-subway (78,192), "metro sin otra estacion", usage 32: trips walk in from the road and arrive at the
  station itself (its footprint is in a destination grid, first-arrival walk), so nothing rides the line. The flag is
  right about the line, the usage comes from those walk-in arrivals.

Stations not flagged with usage 0 (60 of 868) are the other direction: the rule says a trip can pass, but none did in
the window. Not chased further. Possible causes the static check does not see: the trip budget (1,024 cost units),
buildings without transit modes (+0xc..+0xe), or a destination too far for the first-arrival walk.

## Not covered

- Rail-subway placed by hand; ferries (not trip nodes, nothing to flag); seaports and airports (not trip nodes).
- Trips from class-3 buildings (no destination grid) walking in from the Default distance are not counted as access.
- A 1024 map (the scan grids hold up to 1024 x 1024; timing not measured there).
- English install text (translations fr/de/it/nl/sv are machine-made, `re/harness/lang/*.txt`).
