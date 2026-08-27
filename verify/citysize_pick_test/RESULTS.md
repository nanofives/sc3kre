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

## Object-chain trace (desk read 3) — the drag's cellmap is `*(iso+0x158)`, reached by POINTER
`[CONFIRMED @ SIMSPR 0x1001d503:19,26 → 0x100090b7:6-7]`. Three distinct objects:
- class-A "city-view window": CLSID `0x0410c5c7`, main vt `0x10067894`, cIGZWin sub-vt **`0x100676ac`**
  at +4 (what the harness DFS matches), holds the iso view pointer at **+0xb8**.
- iso `cSC3CityViewIso`: main vt `0x10063224`, `Translate`=`FUN_1001d503` at vt+0x244; reads client
  w/h from **iso+0x20/+0x24**; reads its cellmap from **iso+0x158**.
- cellmap `cISC3CitySpriteCellMap`: vt `0x1006250c`, origin **+0x54/+0x58**, tile dims **+0x14/+0x18**.

**Root cause of the origin split:** the harness `cam` SCANS for a `0x6250c` object within 0x280 bytes
and can pick a **second, independently-allocated cellmap instance** rather than the pick's
`*(iso+0x158)`. The full-city cellmap on the `iso+0x158` path is a shared singleton fetched under
resource key `0xfffe1060` (`FUN_10031948:36-42` / released `FUN_10031a60:19-25`, only two sites in the
whole fleet). **Deterministic recipe:** `cellmap = *(*(classA+0xb8)+0x158)`; origin = `cellmap+0x54/0x58`;
discriminate MAIN via `cellmap+0x14 == N` and iso rect `iso+0x20/+0x24`.

## ⚠️ RESIDUAL PUZZLE — desk analysis is now at its limit; a run is the right instrument
The object `cam` found had rectA **span 800x600 = the full client** (windowed 800x600 this run), i.e. a
FULL-view cellmap, NOT a small minimap. So the clean "cam grabbed the minimap" story is NOT proven —
there appear to be **two full-view cellmaps with independent origins** (`-396,672` vs `~1540,772`), and
one ambiguous rectangle (my `1540,772` rests on assumed bbox-corner→endpoint and `(b,a)` axis order)
cannot separate the remaining possibilities by reading alone. Four desk reads converged on a confirmed
MECHANISM + a fix RECIPE; the specific-origin reconciliation is now empirical, not textual.

## Where this leaves anchoring — NOT anchored; next step is a run, not more reading
1. **Harness change:** read origin via the deterministic chain `*(*(classA+0xb8)+0x158)+0x54/0x58`,
   AND enumerate/log ALL `classA→iso→cellmap` candidates with origin/dims/span (turn `cam` into a
   diagnostic that resolves the two-cellmap puzzle in one shot). Desk + one build.
2. **Confirming lease:** an UNAMBIGUOUS single-tile placement (no corner/axis guessing) at a KNOWN
   screen point; read every candidate origin; feed the pick's own origin to `pick.py` and check the
   predicted tile == the placed tile. Ideally two scroll positions to prove origin-tracking.
3. Then rot≠0 / other-zoom (lower priority; dev case is rot0/512).

## Single-tile lease (SINGLETILE_PRE.md) — FIRED 2026-08-27. Two-cellmap REFUTED; ty sign CORRECTED.
Probe `sc3probe.dll` 292352 B sha `799F9630…` (the CAM-CHAIN build). No crash, 9 steps. Shot
`single_154544.png` (800x600).

**⭐ CAM-CHAIN works, and it refutes the two-cellmap theory.** Both `cam` reads logged:
```
### CAM-CHAIN: 1 class-A city-view window(s) with cIGZWin vt SIMSPR+0x676AC
### CAM-CHAIN[0]: classA=0x12CECA80 iso=0x12CEFAC8(vt=0x033C3390?) isoRect=704x544 | cellmap=0x0EC56298(vt=0x033C250C CELLMAP)
### CAM-CHAIN[0]: origin(+0x54/58)=-396,672 dims(+0x14/18)=512,512 span=800x600 rot=0 zoom=0 tilepx=8  <== dims==N: the DRAG's cellmap; feed this origin to pick.py
```
**Exactly ONE class-A window; its chain cellmap `0x0EC56298` (dims 512, origin -396,672) is the SAME
object the scan reported** (`### CAM: candidate 1/1 ... 0x0EC56298 rectA=-396,672`). So there is **one
cellmap, origin (-396,672)** — the "two full-view cellmaps / cam grabbed the wrong one" hypothesis is
**REFUTED**. The pick DOES use origin (-396,672); my back-solved `~1540,772` was an artifact of a wrong
ty-sign assumption. (Minor: `SIMSPR_ISO_MAIN_VT_RVA` should be `0x63390`, not `0x63224` — the iso vt
printed `0x033C3390?`; the `?` is a cosmetic label mismatch, the cellmap `CELLMAP` match is the real
discriminator and it worked.)

**Placements — only 1 of 3 registered (a NEW instrument problem).** Saved raster `{0:262143, 5:1}`:
Com=5 at **(498,38)** from screen (500,200); Res=1 (screen 300,200) and Ind=9 (screen 400,400) placed
NOTHING. Degenerate single-tile drags (`drag:x,y,x,y`) are UNRELIABLE — and run 1's real-extent drags
were too (a different tool registered each run). **Zone placement reliability is now its own blocker
for clean multi-point data.** But the one Com tile is CLEAN and UNAMBIGUOUS (single tile, single
screen point, no corner guessing).

**The clean point disambiguates the transform — ty sign was wrong.** With `(500,200)→(498,38)` plus
run-1's two rectangle corners under the CORRECT diagonal:
`(280,180)→(465,16)`, `(360,240)→(490,11)`, `(500,200)→(498,38)` — all fit
```
tx = b + 267 ;  ty = -a + 244        (a,b = diamond branches; origin -396,672, zoom0, rot0, N=512)
```
The **`-a`** corrects the earlier `+a` (which came from assuming run-1's rectangle mapped start→min-y;
the single tile shows it's the anti-diagonal). And **CX+CY = 267+244 = 511 = N-1** — a strong lead that
these are map-dimension reflection terms (likely f(N), origin-independent), NOT yet proven.

**pick.py CORRECTED** to `tx=b+CX, ty=-a+CY` with `{512:(267,244)}`; `--selftest` **33/0** incl. all
three runtime points; inverse round-trips (tile (498,38) → screen (500,202), within the 2px centre
margin).

**Per SINGLETILE_PRE.md this is FAIL-nomatch + FAIL-noregister(partial)** — pick.py-as-fired did not
predict, and 2/3 placements were absent — BUT it delivered the pre-registered "definitive new data":
the cellmap identity (refuting the puzzle) and the corrected transform.

## Still open after this lease
1. **(CX,CY) origin-dependence UNPROVEN** — all data is at origin (-396,672). Need a run at a SECOND
   scroll to see if (267,244) hold (CX+CY=N-1 says they might). This is the last thing between "fits
   3 points at one camera" and "anchored".
2. **Zone-placement reliability** — only 1/3 (and 1/2 in run 1) drags register. Need a reliable
   single-tile method (more settle time after `fire:`, a real-extent drag, or `at:`) before a
   multi-point run is worth a lease.
3. Then rot≠0 / other-zoom / the f(N) form of (CX,CY).

## Cleanup (done + verified)
`patch_citysize --restore` + `patch_dirtbuf --restore` (both `--check`: SIMUI 256, SIMDIRT shipped
`f1708fc1…`). Re-staged FOUR-recipe SIMSPR from shipped (sha `f5b9f1d9…`, gate 13 runs / 45 bytes;
live 8.0×5 / 2.0 / cave hook `e8 40 b5 05 00`). GZGraphicD untouched (owner-staged, `0x10018570=cd`).
Lease auto-released by `capture.ps1` (DIRTY handoff, pre-existing MODIFIED state). `N512_picktest.sc3`
NOT committed (game-derived).
