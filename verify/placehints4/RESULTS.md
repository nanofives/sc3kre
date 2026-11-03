# placehints4 RESULTS (2026-11-03)

Build: `dev\placehints4\inst\sc3resize.dll` (main b200b92 + this stream). Berlin, 800x600 windowed,
`SC3RESIZE_PLACEHINTS_LOG=1`, posted input only (hover moves, `WM_KEYDOWN` / `WM_KEYUP` VK_SHIFT to the game window,
frame dumps). Pictures: `verify\placehints4\owner_shots\`. Detail and RVAs: `re/analysis/PLACEHINTS.md` E.

## 1. Plop halo only while Shift is held

Owner: "without shift it should hide the area affecting a ploppable building".

| case | result | picture |
|---|---|---|
| Big Park hover, no Shift | stock footprint only (light blue), plain `$1,045`, no halo | `A1_park_no_shift.png` |
| posted Shift down, mouse not moved | green halo on ground and buildings plus the text. Log `halo drawn (Shift down)` | `A2_park_shift_down.png` |
| posted Shift up, mouse not moved | halo and text gone, view as A1. Log `halo cleared (Shift up)` | `A3_park_shift_up.png` |
| Shift held, mouse moved to another spot (over buildings) | halo follows, footprint stock red (refused) | `A4_park_moved_shift_held.png` |

How: the halo is marked only while Shift is down, and a Shift edge re-runs the building tool's own preview (SIMGEOM
`0x10021764` path, tool vt+0x54). The stock fill under it (SIMSPR `0x1004af93`) clears and re-pushes the grid. The
footprint highlight stays stock. `SC3RESIZE_PLACEHINTS_SHIFT=force` keeps the halo always on, `=never` never.

Decision on the airport / seaport red no-transport cells: kept always on. They mark where the zone being dragged
cannot grow, the same role as the stock red refusal, not an area the building affects. Not changed.

## 2. Public transport in the Shift view (orchestrator: go with (a) plus the in-box split)

While a bus stop, train station, subway station or rail-to-subway station is being placed:
- **Shift:** the cells whose lots would walk to it (the residential reach from the live SimTransit byte, corners cut,
  as the trip start scan SimTransit `0x1000755e` does) in the tool's light blue, **green** where trips from that cell
  already use bus, rail or subway (TRIPCELLS), and the label: walk reach R / C / I, trips starting in the area and how
  many by transit, and how many cells it connects through.
- **Always:** footprint **red** when nothing it needs touches it (no rail for a train station, no tunnel for a subway
  station, no road for a bus stop). Same role as the airport red cells and the stock refusal. That rule is
  `ph_station_links`, shared with stationwarn.

| case | result | picture |
|---|---|---|
| train station touching a rail line (laid in the test game), no Shift | stock footprint, plain `$265`. Log `links 2` | `B1_train_touching_no_shift.png` |
| same, Shift | blue area, label `Estacion de tren: a pie R 5 C 4 I 6 celdas \| 61 viajes desde la carga salen de aqui, 0 en transporte (verde) \| conecta por 2 celdas` | `B2_train_touching_shift.png` |
| one cell off the track, no Shift | footprint red. Log `links 0` | `B3_train_gap_red_no_shift.png` |
| in the city, off any track, Shift | red footprint, blue area with green cells (30 with transit trips), `463 viajes ... 40 en transporte (verde) \| no toca la via: 0 viajes (rojo)` | `B4_train_in_city_shift.png` |
| bus stop beside a road, Shift | blue area, `269 viajes ... conecta por 2 celdas` (its red cell is the stock refusal over a building) | `C1_busstop_shift.png` |

Station types (measured from the plop tool log): bus stop 12210, train station 12230, subway station 12360, rail to
subway 12361. Off switch `SC3RESIZE_PLACEHINTS_STATION=0`. New strings: 13 keys `placehints.st_*` / `placehints.station`,
es/en extracted, fr/de/it/nl/sv machine translations merged, `sc3lang.py check` clean (291 keys in every table).

Two things the owner should know:
- **Trip numbers say "since the city loaded" until the Graficas page has been opened once.** TRIPCELLS closes its
  months from GRAPHNEW's budget hook, and that hook does nothing before the page is first opened. After that the label
  gives trips a month. This is TRIPCELLS / GRAPHNEW behaviour, not changed here.
- Walk reach in Berlin reads 5 / 4 / 6 (R / C / I), one more than STTraffic.INI. The label shows the live values.

## Not covered / needs owner check

- The physical Shift key (posted key messages only, which is what the block reads).
- `_SHIFT=force|never`, the full mod set together (only sc3resize rebuilt, all mods were loaded from this inst).
- Airport drag not re-shot (that code path did not change).
- Subway and rail-to-subway stations: type ids measured, not shot. Subway placement in the underground view not looked at.
- `SC3RESIZE_PLACEHINTS_STATION=0` built, not launched.
