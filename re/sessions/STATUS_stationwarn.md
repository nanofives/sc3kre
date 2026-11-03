# STATUS stationwarn (round 2026-11-03 owner feedback) - DONE, ready to merge

## goal
Owner: "add an indicator when a station of any kind can't receive passengers because it's poorly connected".

## verdict + deciding RVA
Rule read from SimTransit (C2), the touch part also measured by railgap: 4 station type ids tagged in FUN_10005983
(0x2fb2 bus stop, 0x2fc6 rail, 0x3048 subway, 0x3049 rail-subway). Ring scan 0x10007a63 (footprint grown by 1, no
corners). IN from a road cell or a lot reach grid (+0x84/88/8c, FUN_1000559e); OUT only to own track (0x10007f87) or a
neighbouring bus stop (0x10007fe9); track nodes arrive only on map edge 0x1000/0x2000 (FUN_10008a94) or in another
station with lots in reach. Ports, airports, ferries: not trip nodes. Power and funding: not read by the router.
Full note: re/analysis/STATION_RULE.md.

## built
Block STATIONWARN (`SC3RESIZE_STATIONWARN=0` off, `_MARK=0`, `_BLINK=0`, `_LOG=1`): static scan every 3 s, red
blinking marker on the game's cell highlighter (city view +0xc0), red "?" rows per reason (through QROWS), Cuadros
Transporte line "Estaciones sin conexion: N de M". Strings in all 7 tables (sc3lang check clean).

## proven game-side vs static only
- In game (Berlin): off-track train station flagged, then not flagged once one rail cell closed the gap (stock
  "Pasajeros por dia" 0 -> 17); dead-end stub station, subway without tunnel, bus stops without road flagged; bus
  stop beside a road not flagged. Marker blink, dialog rows and Cuadros line seen in frame dumps.
- Census over 880 stations in 7 shipped cities: 12 flagged, 9 with station usage 0, the other 3 explained (2 fixed by
  the bus-stop exit, 1 walk-in arrivals). verify/stationwarn/RESULTS.md.
- Static only: rail-subway placed by hand, 1024 maps, trips from class-3 buildings (Default walk distance).

## blocked on
nothing

## files owned (worktree dev\stationwarn\wt)
- re/harness/src/sc3resize_stationwarn.c (NEW, ignored by .gitignore /re/*: needs `git add -f`)
- re/harness/src/sc3resize.c (include before vdbars, sw_tick in the heartbeat after rz_poll, sw_install)
- re/harness/src/sc3resize_vdbars.c (Cuadros line in vb_transport)
- re/harness/src/sc3resize_restore.c (sw_qrows call in rs_qrows before the grow)
- re/harness/lang/{es,en,fr,de,it,nl,sv}.txt (12 stationwarn.* keys)
- re/analysis/STATION_RULE.md (new)
- MAIN: verify/stationwarn/RESULTS.md, verify/stationwarn/owner_shots/ (9 PNG), re/sessions/STATUS_stationwarn.md

## game-harness need
dev\stationwarn tree only. No game of mine is running.

## asks of other sessions
placehints4 has the same touch rule in sc3resize_placehints.c (ph_station_links); kept separate on purpose, both agree.
