# PRE-REGISTRATION — single-tile projection anchoring at 512 (committed before the run)

Owner: `bigcities`. Committed BEFORE the lease (BOARD tamper-evidence rule). Follow-up to the FAIL-
projection run (`PRE.md` / `RESULTS.md`), which showed the transform mechanism is right but `cam`
reported an origin the pick did not use, and one ambiguous rectangle could not resolve it.

⚠️ **CONTINGENT ON A HARNESS CHANGE.** This run requires the `### CAM-CHAIN:` diagnostic (deterministic
`*(*(classA+0xb8)+0x158)` origin read + enumeration of ALL class-A→iso→cellmap candidates). That change
is blocked on the shared harness build lock (held by `resize` at commit time) and must be BUILT and its
presence confirmed in the running dll before this fires. The `### CAM-CHAIN:` line is the instrument
gate: absent ⇒ VOID (stale dll), do not interpret.

## Question
Two, answered in one lease:
1. Which of the live cellmaps is the one the drag/pick actually uses (resolve the two-full-view-cellmap
   puzzle), by reading EVERY class-A→iso→cellmap candidate origin and seeing which predicts the tiles.
2. Does `pick.py`, fed the PICK's own origin, predict placed tiles exactly at N=512, rot=0 — anchoring
   the projection with NO corner/axis ambiguity.

## Why single-tile, three points
A drag paints a tile-space rectangle, forcing a guess about which bbox corner maps to which endpoint
and about (a,b)-vs-(b,a) axis order — the ambiguity that muddied the first run. **Three DEGENERATE
drags (`drag:x,y,x,y`) place three SINGLE tiles** at three NON-COLLINEAR screen points, each with a
distinct zone value (Res=1, Com=5, Ind=9). Three non-collinear (screen→tile) samples fully determine
the 2D affine, so even a total FAIL yields clean data for a fresh solve. No corner/axis guessing.

## Fixture / oracle / config (as the prior run)
- `N512_city.sc3` (all-zero) → working copy `verify/citysize_pick_test/N512_single.sc3` (pristine kept).
- Oracle: `city_write.City.zone_histogram()` + per-value tile LIST (each value expected ≈ 1 tile).
- Restore SHIPPED SIMSPR; `patch_citysize --n 512` + `patch_dirtbuf --n 512` (`--check` green);
  bare `-GamePath` auto-load; `SC3_SESSION=bigcities` so `capture.ps1` reuses my lease; `-AtSec` ≤ 800.

## Sequence (frozen before firing)
```
0xE2FA5BC2@20;fire:0x10003101@60;cam;drag:300,200,300,200;fire:0x10003201;drag:500,200,500,200;fire:0x10003301;drag:400,400,400,400;cam;fire:0x10009002;wait:6000
```
- dismiss tip / load-gate on Res fire@60 / `cam` #1 (emits `### CAM-CHAIN:` — all candidate origins) /
  Res single tile @(300,200) / Com tool / Com single tile @(500,200) / Ind tool / Ind single tile
  @(400,400) / `cam` #2 (confirm no drift) / Save (in-place, no confirm on bare-path load) / finish.
- Points are non-collinear (triangle), central, within 800x600 (holds if client is 1024x768 too),
  clear of the left palette (x>96) and top menu / status bar. All open ground (all-zero map).

## Prediction procedure (AFTER the run, from committed inputs)
For EACH candidate origin `(ox,oy)` logged by `### CAM-CHAIN[k]` (with its zoom, and the dims flag):
```
py -3.12 re/tools/pick.py --origin=<ox>,<oy> --zoom <z> --to-tile 300,200
py -3.12 re/tools/pick.py --origin=<ox>,<oy> --zoom <z> --to-tile 500,200
py -3.12 re/tools/pick.py --origin=<ox>,<oy> --zoom <z> --to-tile 400,400
```
The candidate whose three predictions equal the three placed tiles (value 1 @P1, 5 @P2, 9 @P3) is the
pick's cellmap.

## Pre-registered outcomes (decided before firing)
| # | observation | verdict |
|---|---|---|
| PASS | exactly one candidate origin's pick.py predictions match all three placed tiles, and it is the `dims==N` candidate | **Projection ANCHORED at 512/rot0; the pick's cellmap = `iso+0x158` of the `dims==N` class-A, identified deterministically.** pick.py usable for development aiming; the deterministic chain is the read to use henceforth. |
| PASS-degenerate | the `dims==N` candidate matches all three AND another candidate also matches (same origin) | Anchored; the extra match is harmless (identical origin). |
| FAIL-nomatch | NO candidate origin predicts all three | Mechanism/axis model still wrong. Report the three (screen→tile) samples + every candidate origin/zoom/dims; three non-collinear points fully determine the affine, so this is definitive new data for a fresh derivation — NOT a rescue. |
| FAIL-multitile | a placement flipped >1 tile | Take the connected cluster's anchor if unambiguous; else re-fixture with `at:` and note. |
| FAIL-noregister | a value absent from the raster | that tool/point did not apply (chrome/off-open); the remaining points still test — partial. |
| VOID-instrument | `### CAM-CHAIN:` absent (stale dll) OR `cam` REFUSE OR 0 candidates listed | Instrument failure; report, rebuild/refire. Do NOT interpret the raster. |
| VOID | crash / no save / save did not write back | Report; re-fixture. |

Record in `RESULTS.md` (full numbers — the `.sc3` is not retained): both `### CAM:` + all
`### CAM-CHAIN:` lines verbatim, the three placed tiles per value, every candidate's pick.py
predictions, and which candidate (if any) matched.

## Cleanup contract (every path incl. abort)
1. `patch_citysize --restore` + `patch_dirtbuf --restore` (`--check` green).
2. Re-stage the owner's live build per BOARD standing rule (FOUR-recipe SIMSPR `f5b9f1d9`, TWO-recipe
   GZGraphicD) — read the exact gated command from BOARD.md; verify with its `--read` checks.
3. Release the lease `-DirtyOk`.
4. Never commit `N512_single.sc3` (game-derived).
