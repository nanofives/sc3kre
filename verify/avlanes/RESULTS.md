# avlanes M1: failed trips with one-way avenue halves in routing only (2026-10-19)

Plan: `verify/avlanes/PLAN.md` section 7. Build: main 19b5fe8, own test tree `Simcity_stock_avlanes` (hard-linked
stock install, no other package), instance `re\harness\inst_avlanes` (sc3netmod from 19b5fe8, sc3resize). City: two
fresh copies of shipped Seoul (2,722 avenue cells). Both games `SC3NETMOD_LANEDENSITY=all` (every piece's turn matrix
honoured by the router). Probe `re/tools/netmod/hwtraffic_probe.py` (game month counters +0xb0 / +0xb4 / +0xb8), 9 sim
months at speed 4 per game, month 1 (partial, after load) dropped. Data `data/m1_A.json`, `m1_B.json`,
`m1_*_lanedensity.txt`.

| arm | what differs |
|---|---|
| A | stock 11204 matrix (two-way, `0x01040104`) |
| B | test package `m1_oneway_11204` (one `connects` entry: low x+ => x-, high x- => x+, = `0x00040100`), right-hand traffic: state 1 -> -z, 3 -> +z, 2 -> +x, 0 -> -x. Live check: four 11204 cells, states 0..3, exemplar m140 = 0x00040100 |

The test package is local only (under `verify/avlanes/`, not in `examples/`) and was uninstalled after the run: it would
make every avenue one-way, which the plan rules out for shipping.

## Result (8 full sim months per arm)

| | A (two-way halves) | B (one-way halves) |
|---|---|---|
| trips routed per month | 3,188..3,767 (mean 3,575) | 3,273..3,721 (mean 3,575) |
| failed trips per month | 62..87 (mean 72.0) | 57..77 (mean 69.9) |
| failed ratio per month | 1.74..2.36% (mean 2.01%) | 1.59..2.14% (mean 1.95%) |
| LANEDENSITY wrong-way fails (whole game) | 6,924 | 86,400 |
| refused-transition closes | 8,340 | 93,510 |
| trip list full (per-trip list of 32 refused transitions overflowed) | 0 | 26,224 |
| arrivals refused | 36 | 30 |

Failed trips did not rise: B's monthly range lies inside A's. The router did meet the one-way rule: 12.5x the wrong-way
fails and 11x the refused transitions, so trips that tried to go the wrong way down a half were turned back and found
another way. The per-trip refused list overflowed 26,224 times in B (0 in A). When it is full, LANEDENSITY leaves the
refused cell marked visited instead of remembering the transition (LANE_DENSITY.md 3), so those trips explore less.
That did not show as more failures here. Its cost in time was not measured.

## Read

One-way halves are workable for routing before any median opening exists, in this city. The reason is in the stock
pieces: at a stock road crossing the two halves are two 43 crossroads joined by the road, so a trip can already turn
from one half into the other there, and an avenue end (the 11203 pair) is already a U-turn. Both arms honour those
stock matrices (LANEDENSITY=all), so B measured the direction rule alone.

Caveats:
- One city, one game per arm, 8 months.
- LANEDENSITY=all honours every stock piece in both arms. A shipped build would honour only the avenue variants
  (default mode), so the other stock pieces would route as today.
- The time cost was not measured. B ran more router work per trip (refused closes, list overflows). Measure
  ms/trip with `ld_alt.py`-style paired runs when avcore exists.
- The per-trip list (LD_TRIPMAX 32) overflowed 26,224 times: avcore should try a larger list and read "trip list full"
  again (whether that changes failures is not known).
- No lanes or art changed: cars still drive the stock two-way lanes in this test.
