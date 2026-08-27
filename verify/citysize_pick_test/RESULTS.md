# RESULTS — screen→world projection validation at 512

Pre-registration: `PRE.md` (committed `77b5960` before the run). Fired 2026-08-27, one lease.
Shot: `.happy-share/cmsysyj1a0rivn51c47lbyf3l/picktest_012120.png` (800x600). No crash.
`### GZSEQ: COMPLETE (9 steps) at t+15781 ms`. Probe `sc3probe.dll` sha `B0F5124A…` (284160 B —
a sibling had rebuilt after my release; my `CAM>` arm is present, confirmed by the log line below).

## VERDICT: FAIL-projection (pre-registered), and it is STRUCTURED + diagnostic.
`pick.py` does NOT predict the landed tile. The diamond COEFFICIENTS are correct; the AXIS ASSIGNMENT
and an ORIGIN/CENTERING OFFSET are wrong. Root cause is in the rot-remap / worldpx→tile wrapper
(`FUN_1000a5c6` / `FUN_1000a48a`), not the diamond core (`FUN_1000a33a`).

## Camera state (both `cam` reads identical — camera did not drift between the two drags)
```
### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EC660D0  rectA=-396,672,404,1272 span=800x600  zoom=0 tilepx=8   <== USED
### CAM: zoom=0 rot=0 tilepx=8 (8<<zoom=8)  presentGate(+0x7c)=0  flag(+0x32c)=0
### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed
### CAM: MAP 512x512 tiles  (world extent ~130816x130816 px)
```
So origin (left,top) = (-396, 672), zoom=0, rot=0, N=512. Client is 800x600 (not 1024x768; irrelevant
— the pick uses the live origin + actual coords, and all drag points are within 800x600).

⭐ **The new `0x10016eba` map-dims wiring WORKS.** Log: `CAM> armed occupant-bridge capture on
SIMSPR!0x10016EBA …` then `### CAM: MAP 512x512`. First time `cam` reports map dims instead of
"UNAVAILABLE". That deliverable is banked independent of the projection verdict.

## Drags
| drag | tool | screen | raster result |
|---|---|---|---|
| A (Res-Low) | fire 0x10003101 | `280,180 -> 360,240` | **value 1: 108 tiles, bbox x[465..490] y[11..16]** |
| B (Com-Low) | fire 0x10003201 | `520,360 -> 600,420` | **value 5: ABSENT (placed nothing)** |

Baseline working copy verified all-zero before the run (`{0: 262144}`). Post-run histogram
`{0: 262036, 1: 108}`. Drag B placing nothing repeats item-1's second-drag null; pre-registered as
partial (hit-chrome / off-open-ground), not investigated this lease.

## Prediction vs actual (drag A)
`pick.py --cam=-396,672,0,0 --n 512 --to-tile <endpoint>` (NB `--cam=` form; leading `-` needs `=`):
| screen endpoint | pick.py PREDICTS | game ACTUAL (bbox corner) |
|---|---|---|
| 280,180 | tile (228,198) | (465,11) |
| 360,240 | tile (233,223) | (490,16) |

Predicted bbox x[228..233] y[198..223] (6 wide × 26 tall). Actual x[465..490] y[11..16] (26 wide ×
6 tall). **Transposed and offset.**

## Diagnosis — the true transform, solved from both endpoints
Both endpoints fit exactly:
```
game tx = sx/8 + sy/4 + 385.5          game ty = -sx/8 + sy/4 + 1.5
```
Against `pick.py`'s continuous form at this camera:
```
my u = -sx/8 + sy/4 + 218.5            my v = sx/8 + sy/4 + 118.5      (rot0 outputs (u,v))
```
Therefore, exactly: **`game_tx = my_v + 267`** and **`game_ty = my_u − 217`**.
- The **±1/8 and 1/4 coefficients are CORRECT** — the diamond core `FUN_1000a33a` and the tile
  sizes (tileW=8, tileH=4 at zoom 0) are right; scale and shape are validated.
- The game **swaps the two branches** (its tx tracks my v, its ty tracks my u) and adds **constant
  offsets +267 / −217**. So `pick.py`'s `rot0 = identity (u,v)` is wrong at runtime; the real map maps
  raw (u,v) to (something·v + off, something·u + off).
- In world-pixel terms (wpx=sx−396, wpy=sy+672): `tx = wpx/8 + wpy/4 + 267`,
  `ty = −wpx/8 + wpy/4 − 216`.

## Why this lease cannot fully fix it
The two endpoints come from ONE small drag and are **near-collinear**, so the full 2D affine (in
particular the two offsets, which may themselves contain left/top/N) is **underdetermined** — the
same weakness that limited item 1. The offsets 267 / −217 are near but not equal to N/2 (256), so a
clean "±N/2 half-extent recenter" is suggested but NOT proven from this data.

## Next (desk RE, no lease)
Re-read the FULL chain **`FUN_1000a48a` (worldpx→tile wrapper) and `FUN_1000a5c6` (rot remap)**, not
just the diamond core — the swap and the +267/−216 offset live there. The prior sweep transcribed
`FUN_1000a33a` correctly (coefficients confirmed in-game) but reported `rot0 = identity`, which the
runtime refutes: there is a base transpose + map-relative offset even at rot=0. Get the offset in
terms of `left/top/tileW/tileH/N`, correct `pick.py`, re-run `--selftest`, then a 2nd validation lease
with **two NON-collinear drags at two different camera positions** to pin it beyond doubt.

## Instrument notes
- `pick.py --cam` rejects a leading-`-` value (`--cam -396,…` → argparse error). Use `--cam=-396,…`.
  Cosmetic; fix alongside the formula correction.
- `cam` read was clean: 1/1 candidate (no ambiguity), stable across both reads, FOLLOW disarmed.

## Reconciliation (desk RE 2026-08-27, no lease) — CORRECTED formula, pick.py fixed
Re-read `FUN_1000a48a`, `FUN_1000a5c6`, `FUN_1000b70e`/`FUN_1000b867`, `FUN_100090ef` and the iOS
twin, reconciled against the two measured points:
- **`rot=0` IS identity** in `FUN_1000a5c6` `[CONFIRMED @ 0x1000a5c6:9-14]`; the prior rot table was
  right (`rot1:(b,W-1-a) rot2:(W-1-a,H-1-b) rot3:(H-1-b,a)`, W=`+0x14`, H=`+0x18`).
- **The `+267/-217` is NOT in the SIMSPR pick chain.** `FUN_1000a48a` calls `FUN_100090ef`→`a33a`
  then `a5c6`, adding no centering term `[CONFIRMED @ 0x1000a48a:11-28]`. The offset is the
  **city-grid origin translation applied by the caller** (SIMCITY/network layer, not yet read). Per
  `FUN_1000b70e:52` the sprite-diamond origin `X0=(tileW/-2)*(W-1)`, `Y0=tileH/-2` is a function of
  **map dimension only, not scroll** — so `(267,-217)` is **INVARIANT across scroll for a 512 map**,
  map-size-specific. iOS `getZeroAltCellFromWs` does the same `cell -= mapExtent/2`.
- **`iso+0x1c/+0x20` are (rotated) MAP DIMENSIONS**, not last-mouse (`FUN_1000b70e` multiplies them
  by tileW/tileH); the old "0,0" note read the object before setup or a colliding struct `[UNCERTAIN
  which]`.
- **`[UNCERTAIN]`** the exact 267/-217 split is not produced by any SIMSPR field; carried as a
  MEASURED anchor per N until the city-grid caller is read.

**Corrected form (validated, rot=0):** `tx = b + 267`, `ty = a - 217` where `a,b` are the diamond
branches. Inverse: `b=tx-267; a=ty+217; wpx=(4<<zoom)(b-a+1); wpy=(2<<zoom)(a+b); sx=wpx-left;
sy=wpy-top`. **`pick.py` updated** (city-grid offset table `{512:(267,-217)}`, rot=0 only, `--cam`
negative-value fix); `--selftest` = **57 checks, 0 failures** including both runtime points as a
regression guard. **Committed** (see below).

**Where this leaves anchoring:** screen↔tile is **runtime-validated for N=512, rot=0, any scroll** —
usable for development-run aiming now. Owed: (a) a code source for the offset-in-N (read the city-grid
caller of `a48a`, likely the SIMCITY grid / `network_layer` area) to generalise + reach C4; (b) a
confirming lease with two NON-collinear drags (and ideally a second zoom).

## Cleanup (done + verified)
`patch_citysize --restore` + `patch_dirtbuf --restore` (both `--check`: SIMUI 256, SIMDIRT shipped
`f1708fc1…`). Re-staged FOUR-recipe SIMSPR from shipped (sha `f5b9f1d9…`, gate 13 runs / 45 bytes;
live 8.0×5 / 2.0 / cave hook `e8 40 b5 05 00`). GZGraphicD untouched (owner-staged, `0x10018570=cd`).
Lease auto-released by `capture.ps1` (DIRTY handoff, pre-existing MODIFIED state). `N512_picktest.sc3`
NOT committed (game-derived).
