# PRE-REGISTRATION — two-scroll origin-independence test at 512 (committed before the run)

Owner: `bigcities`. Committed BEFORE the lease. Follow-up to the single-tile run (`RESULTS.md`), which
gave `tx=b+267, ty=-a+244` at ONE camera origin (-396,672) and left ONE open question: **are the
offsets (CX,CY)=(267,244) origin-independent** (`CX+CY=N-1` hints yes) or scroll-dependent?

## Desk finding that reframes "placement reliability" (recorded 2026-08-28, no lease)
Re-projecting every prior drag point through the CORRECTED transform: **most "failures" were OFF-MAP
targets, not unreliable placement.** The default camera views the **top-right corner** — screen centre
(400,300) → tile **(510,1)** — so the on-map-with-margin region is a tiny band (screen `x∈[150,600]
y∈[100,200]` → tiles `x∈[429,491] y∈[13,76]`); everything below/right projects off the 512 map. Run-1
Com `(250,400)→(516,-43)` and run-2 Ind `(400,400)→(535,-24)` were OFF-MAP. The only genuine on-map
miss was run-2 Res (473,13) via a DEGENERATE drag. **So the reliability fix is: (1) AIM with pick.py so
targets are on-map; (2) use small REAL-EXTENT drags (degenerate ones are flaky); (3) SETTLE after
`fire:` before dragging.** No harness build needed.

## Question
Place a rect at the default origin O1 and another after a camera scroll to origin O2; if pick.py with
the SAME (CX,CY) predicts BOTH, the offsets are origin-independent and the projection is ANCHORED (aim
at any scroll after one `### CAM-CHAIN:` read).

## Fixture / oracle / config
- `N512_city.sc3` (all-zero) → working copy `verify/citysize_pick_test/N512_twoscroll.sc3`.
- Oracle: `city_write.City.zone_histogram()` + per-value bbox.
- Restore SHIPPED SIMSPR; `patch_citysize --n 512` + `patch_dirtbuf --n 512` (`--check` green); bare
  `-GamePath` auto-load; `SC3_SESSION=bigcities`; `-AtSec` ≤ 800. `### CAM-CHAIN:` presence is the
  instrument gate (the origin-read fix; absent ⇒ VOID stale dll).

## Sequence (frozen before firing)
```
0xE2FA5BC2@20;fire:0x10003101@60;wait:1500;cam;drag:200,130,480,175;key:0x25,600;key:0x25,600;key:0x25,600;key:0x25,600;key:0x25,600;key:0x25,600;key:0x25,600;key:0x25,600;cam;fire:0x10003201;wait:1500;drag:300,150,520,190;fire:0x10009002;wait:6000
```
- tip / load-gate (`fire:0x10003101` = Res-Low, already the round-1 tool) / **settle 1.5 s** /
  `cam` #1 → **O1** (`### CAM-CHAIN[0] origin`) / **round 1**: Res real-extent drag `(200,130)→(480,175)`
  → value **1** / **scroll**: 8× `key:0x25` (VK_LEFT taps, ~32 px each) / `cam` #2 → **O2** / `fire`
  Com-Low (0x10003201) / settle 1.5 s / **round 2**: Com real-extent drag `(300,150)→(520,190)` →
  value **5** / Save / finish. (19 steps < GZMAXSEQ 32.)
- Round-1 endpoints project on-map at O1: `(200,130)→(443,18)`, `(480,175)→(489,42)`. Round-2 reuses a
  fixed central rect (on-map at O1: `(460,26),(498,43)`); after a modest scroll it stays near the
  on-map band (CAM-CHAIN gives the true O2 either way).

## Prediction procedure (AFTER the run, from committed inputs)
Read **O1** and **O2** from the two `### CAM-CHAIN[..] origin(+0x54/58)=` lines (the dims==N cellmap).
```
py -3.12 re/tools/pick.py --origin=<O1x>,<O1y> --n 512 --to-tile 200,130   # round-1 corners
py -3.12 re/tools/pick.py --origin=<O1x>,<O1y> --n 512 --to-tile 480,175
py -3.12 re/tools/pick.py --origin=<O2x>,<O2y> --n 512 --to-tile 300,150   # round-2 corners
py -3.12 re/tools/pick.py --origin=<O2x>,<O2y> --n 512 --to-tile 520,190
```
Predicted value-1 bbox = rect between the round-1 corner tiles (O1); value-5 = round-2 corners (O2).

## Pre-registered outcomes (decided before firing)
| # | observation | verdict |
|---|---|---|
| PASS | value-1 bbox == pick.py(O1) AND value-5 bbox == pick.py(O2), with **O2 ≠ O1** | **⭐ (CX,CY) ORIGIN-INDEPENDENT → projection ANCHORED at 512/rot0.** Aim any tile at any scroll after one CAM-CHAIN read. pick.py usable for development service authoring. |
| FAIL-O2 | value-1 matches (O1) but value-5 ≠ pick.py(O2) | **(CX,CY) are origin-DEPENDENT.** Report O1, O2, actual value-5 bbox; back-solve the O2 offsets → derive (CX,CY) as f(origin). Definitive new data, not a rescue. |
| FAIL-scroll | O2 == O1 (CAM-CHAIN origins identical) | `key:` did not scroll; round 2 is a 2nd sample at O1 (tests reliability, not origin-independence). Re-fixture the scroll (direction/among/zoom). |
| FAIL-round1 | value-1 ≠ pick.py(O1) | Regression at the validated origin — investigate (should not happen). |
| FAIL-noregister | a value absent | If its target was on-map (pick.py at that origin) → genuine placement miss (real-extent + settle should prevent). If off-map at O2 → expected; the on-map round still tests. |
| VOID | crash / `### CAM-CHAIN` absent / `cam` REFUSE | Instrument; report, do not interpret. |

Record in `RESULTS.md` (full numbers): both `### CAM-CHAIN` blocks (O1, O2), the four pick.py
predictions, value-1 and value-5 bboxes, histogram.

## Cleanup contract (every path incl. abort)
1. `patch_citysize --restore` + `patch_dirtbuf --restore` (`--check`).
2. Re-stage owner's build per BOARD standing rule (FOUR-recipe SIMSPR `f5b9f1d9`, TWO-recipe
   GZGraphicD) — read the exact gated command from BOARD.md; verify with `--read`.
3. Release lease `-DirtyOk`. Never commit `N512_twoscroll.sc3`.
