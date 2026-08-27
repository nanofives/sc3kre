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

## Reconciliation (desk RE 2026-08-27, no lease) — TWO reads, and a CORRECTION of the first
Two decompilation re-reads. **The first's conclusion was WRONG; the second is right. Recording both
because the error is instructive (a confirmed code path is not a confirmed cause).**

**Read 1 (SUPERSEDED):** claimed `+267/-217` was a city-grid origin translation in the caller, a
function of map dimension only (`FUN_1000b70e:52` render origin `(tileW/-2)*(W-1)`), hence scroll-
invariant f(N). It correctly found `rot=0` identity and that `FUN_1000a48a` adds no centering — but it
attributed the residual to `b70e`'s render-cull origin, which **the pick never consumes**.

**Read 2 (CORRECT):** the additive site is **`FUN_100090b7` @ 0x100090b7:6-7** — it adds the VIEW
ORIGIN `iso+0x54/0x58` to the screen coord in the FULL pick path `FUN_1000902f` (the RAW path
`FUN_1000a48a` skips it). **There is NO separate offset.** The pick is exactly: add view origin →
diamond `FUN_1000a33a` → rot `FUN_1000a5c6` (identity at rot 0). The tool tile is `(tx,ty) = (b, a)`
(the +wpx branch b is tile X, the -wpx branch a is tile Y). `[CONFIRMED @ 0x100090b7, 0x1000902f,
0x1000a33a, 0x1000a5c6]`.

**So the earlier `+267/-217` was NOT a real constant.** It equals `(pick_origin − cam_origin)` in tile
space for THIS run's scroll, and does NOT generalise. RETRACTED.

## ⚠️ THE ORIGIN DISCREPANCY — the real, definitive finding
The origin the pick USED does not match the origin `cam` REPORTED:
- `cam` reported view origin **(-396, 672)** (rectA left/top of the 1/1 cellmap it found).
- The pick behaved as origin **~(1540, 772)** — the ONLY origin under which the confirmed mechanism
  `(tx,ty)=(b,a)` reproduces BOTH measured points: `(280,180)@(1540,772)` → a=11,b=465 → `(465,11)`;
  `(360,240)` → `(490,16)`.
- **(-396,672) fits NO branch/corner assignment** — it gives `(198,228)`/`(228,198)`, nowhere near
  the actual `(465,11)`. Checked exhaustively. **Definitive: cam read the wrong origin for the pick.**

Likely cause: `cam` locks the FIRST matching GZWIN cellmap (the code itself warns "the MINIMAP is also
a city view"), while the drag targets the explicit main city-view window `0x6104489A`. So cam and the
drag were reading/using **different cellmap objects**.

## pick.py — CORRECTED to the confirmed mechanism (no offset)
`tx=b, ty=a`, origin-parametrized (`--origin OX,OY --zoom Z`), rot=0. `--selftest` = **122 checks,
0 failures** (round-trip at several origins/zooms + both runtime points reproduced at the pick's own
origin (1540,772) as a regression). Removed the bogus offset table; `--origin` fix for negatives.

## Where this leaves anchoring — NOT anchored yet; blocked on the origin source
The MECHANISM is confirmed and exact. The BLOCKER is that `cam` does not currently report the origin
the pick uses. Owed, in order:
1. **Fix the origin read** — make `cam` (or a new verb) return the cellmap of the window the drag
   targets (`0x6104489A`), not the first GZWIN. Desk + one build + one confirming lease.
2. Confirming lease: read that origin, aim a drag with pick.py at a CHOSEN tile, read the raster back
   — and ideally two NON-collinear drags at two scroll positions to prove origin-tracking.
3. Then rot≠0 / other-zoom coverage (lower priority; dev case is rot0/512).

## Cleanup (done + verified)
`patch_citysize --restore` + `patch_dirtbuf --restore` (both `--check`: SIMUI 256, SIMDIRT shipped
`f1708fc1…`). Re-staged FOUR-recipe SIMSPR from shipped (sha `f5b9f1d9…`, gate 13 runs / 45 bytes;
live 8.0×5 / 2.0 / cave hook `e8 40 b5 05 00`). GZGraphicD untouched (owner-staged, `0x10018570=cd`).
Lease auto-released by `capture.ps1` (DIRTY handoff, pre-existing MODIFIED state). `N512_picktest.sc3`
NOT committed (game-derived).
