# railgap: does a rail station one cell away from the track carry trips? (pre-registered 2026-11-02)

Question (owner, 2026-11-02): "putting train stations one tile away from the railroad, will they work?"

Code read (`re/analysis/HIGHWAY_TRIPS.md` 1.2, `LANE_DENSITY.md`): select_next `FUN_1000755e` ring-scans the node rect
grown by one, corners excluded. A station only reaches a rail cell that shares an edge with it.

## Setup

- Tree `dev/railgap/tree`, mods on except sc3perf (moved to `inst/off`, so routing stays on the sim thread).
  City: copy of shipped Berlin (`railgap_berlin.sc3`), never saved. Speed 4.
- Site: the only free 2x2 found one cell off a straight run of track with a road on another side.
  Station footprint (194..195, 62..63). Gap column x=196 (z 62, 63), empty. Track at (197,62), (197,63). Road along z=64.
- Station: RailStation `0x207edc0e,0x57e,0xed` placed with `place_direct.py` (game's own PlaceBuilding).
- Arms on the same station, changing only the one cell between it and the track:
  - **G (gap)**: station as placed, (196,63) empty.
  - **T (touching)**: one rail cell laid at (196,63) with `nb_drive.py build 2` (joins the track at (197,63)).
  - Order G, T, G (the spur bulldozed with `nb_drive.py remove 196,63`). 3 windows of 20 s per arm.
- Probe: `re/tools/netmod/rail_probe.py run` (Frida, read-only). Per station rect it counts select_next steps out of
  the station node (`sta_out`, `>4` rail / `>x` no step) and arrived trips whose path holds that station.

## Predictions (from the code read)

1. G: steps out of the new station's node never give a rail node (`>4` = 0). Arrived trips through it = 0.
2. T: `>4` steps out of the station > 0 and arrived trips through it > 0.
3. Back to G: as in 1.
4. Trips still enter the station in G (from road / lot), then fail to step on (`>x`). Reported, not a pass criterion.

Pass = 1, 2 and 3 hold. If the station gets no entries at all in any arm, the test is INCONCLUSIVE, not a pass.
