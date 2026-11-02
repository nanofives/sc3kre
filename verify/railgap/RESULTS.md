# railgap RESULTS (2026-11-02): a rail station one cell off the track carries no trips. PASS

Pre-registration: `PRE.md` (2e9b0c2). Probe: `re/tools/netmod/rail_probe.py`. Raw JSON: `dev/railgap/inst/` (not kept).

## Setup as run (deviations from PRE)

- PRE's site (194..195, 62..63) and the next one found were **river water**: flags 0, no occupant, flat, so the site
  search took them as free land. `place_direct` refused every key there (rail station, subway station, coal plant).
  The search was re-run with `tiler.City.is_water` and with tree occupants (major 5) counted as clearable.
- Site used: station footprint **(180..181, 127..128)**, Berlin, ground height 32 everywhere. Track along z=125
  ((180,125) curve, (181,125) straight). Gap cell **(181,126)**. Roads at x=182 and z=129 touch the station.
  An existing station sits at (183..184, 126..127), touching the same track and road.
- Gap closed with `nb_drive.py build 2 181,126 181,126` (one rail cell, piece 18000). `nb_drive.py remove` reported
  success on that cell twice but left the piece in place (rail removal through manager vt+0xb4 does not work).
  Reopened instead with the game's bulldozer (`roadover_drive.py tool bulldoze`, posted move, the highlight checked
  in a grab, then a posted click). Transit flags grid `+0x5c` checked after every change.
- Window lengths: G1 3 x 20 s, T 3 x 20 s + 6 x 30 s, G2 6 x 30 s.

## Result (counts for the new station's node rect only)

| arm | sim days | entered from road / lot | entered from rail | steps out to rail | steps out failed | arrived trips through it |
|---|---|---|---|---|---|---|
| G1 gap | 176 | 2 | 0 | **0** | 4 | **0** |
| T touching (6 x 30 s) | 578 | 34 | 164 | **31** | 346 | **19** |
| G2 gap | 624 | 12 | 0 | **0** | 24 | **0** |

The short T run (3 x 20 s) gave 60 rail-to-station steps, 1 station-to-rail step and 0 arrivals.

Predictions 1, 2 and 3 hold. Prediction 4 holds too: in both gap arms trips still entered the station from the road or
a lot, and every step out of it failed.

## Also measured (all runs pooled: 190,939 arrived trips, Berlin, no bus stops in the city)

| step | count |
|---|---|
| road > rail station / lot > rail station | 3,518 / 2,424 |
| rail station > rail / > nothing | 5,033 / 43,223 |
| rail > rail station | 25,599 |
| road > subway station / lot > subway station | 5,601 / 4,450 |
| subway station > subway / > nothing | 10,095 / 2,387 |
| subway > subway station | 36,276 |
| rail-subway station (0x30) > rail / > subway | 3,991 / 4,482 |
| **any station > road** | **0** |

Stations are a one-way door: road or lot onto the track. No station step ever led back to a road. The trip ends on
the track itself, on a cell the arrival test `FUN_10008a94` accepts. Arrived paths holding a node type: rail 5,524,
rail station 5,715, subway 8,430, subway station 8,474, rail-subway 1,900.

Station cells carry the network bit of their mode: rail station 0x14 (0x10 | rail 4), subway station 0x18
(0x10 | subway 8), rail-subway 0x3c / 0x1c.
