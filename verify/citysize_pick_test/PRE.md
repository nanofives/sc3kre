# PRE-REGISTRATION — screen→world projection validation at 512 (committed before any run)

Owner: `bigcities`. Written and `git`-committed BEFORE taking the game lease (BOARD rule:
pre-registration must carry an independent, tamper-evident timestamp). No run has fired when this
is committed.

## Question
Does `re/tools/pick.py` predict, from the live camera state alone, which world tile a scripted drag
lands on at N=512 — i.e. is the screen→world isometric projection correctly anchored? This validates
the FORWARD pick against the running game; the INVERSE (aim: tile→screen) is then guaranteed by the
`--selftest` round-trip (580/580) because inverse = forward⁻¹ algebraically.

Secondary: does the new `cam`-triggered occupant-bridge capture (SIMSPR `0x10016eba`, this session's
additive `sc3probe.c` change) make `### CAM:` print `MAP 512x512` instead of `dimensions UNAVAILABLE`.

## Why this design is clean (independence of prediction and check)
- The PREDICTION is computed from the **camera state** (`### CAM:` left/top/zoom/rot) fed to
  `pick.py --to-tile` on the drags' FIXED screen endpoints (fixed here, before the run).
- The CHECK is the **saved zone raster** (which tiles flipped).
- Camera state and raster are independent measurements, so predicting from one and checking against
  the other is not circular. The only run-derived prediction input is the camera state, an
  independent instrument from the raster.
- The drag endpoints are frozen in this file before the lease; only the camera state is measured.

## Fixture and oracle
- `verify/citysize_mod_test/N512_city.sc3`: n=512, all 262,144 tiles unzoned (`{0:262144}`). Baseline
  all-zero ⇒ every non-zero tile in the saved file is necessarily the tool's work.
- Working copy: `cp N512_city.sc3 → verify/citysize_pick_test/N512_picktest.sc3` (keep original
  pristine; Save overwrites the loaded path in place, as item 1 established).
- Parse: `re/tools/city_write.py` `City.load(...).zone_histogram()` and per-value bbox
  (min/max x,y over tiles equal to the value).

## Config (matches the documented shippable config + measurement discipline)
- Restore SHIPPED SIMSPR first (`Copy-Item Apps\SIMSPR.DLL.shipped Apps\SIMSPR.DLL -Force`).
  Measurement discipline, and it also removes any cave at `0x10016eba` so the fnlog capture detour
  is unambiguously safe. (SIMSPR camera mods are neutral for tool-placement drags anyway — the pan
  divisor affects right-drag pan, not the move/down/sweep/up tool events.)
- `py -3.12 re/tools/patch_citysize.py --n 512` + `py -3.12 re/tools/patch_dirtbuf.py --n 512` (a
  512 city needs the dirtbuf SIZE group to render). `--check` both green before launch.
- Bare absolute-path auto-load of the working copy. `SC3_SESSION=bigcities` so `capture.ps1` reuses
  my lease (never wrap it in an outer acquire). `-AtSec` ≤ 800.

## Sequence (frozen before firing)
```
0xE2FA5BC2@20;fire:0x10003101@60;cam;drag:280,180,360,240;fire:0x10003201;drag:520,360,600,420;cam;fire:0x10009002;wait:6000
```
- `0xE2FA5BC2@20` dismiss the load tip if present.
- `fire:0x10003101@60` select Res-Low tool; also the load-gate (palette must exist) — SKIP loudly at
  60 s on a load failure rather than hang.
- `cam` — read #1: THE camera anchor for both drags (zoning does not scroll, so load-state == drag-state)
  and the map-dims sub-check.
- `drag:280,180,360,240` — Res-Low rectangle (raster value 1). Central, clear of palette (x>96) and
  top menu; open ground (all-zero map).
- `fire:0x10003201` — switch to Com-Low tool.
- `drag:520,360,600,420` — Com-Low rectangle (raster value 5). Separated from drag A in screen space
  so their tile regions do not collide.
- `cam` — read #2: confirm the camera did not drift between the drags (should equal read #1).
- `fire:0x10009002` — Save. On a bare-path-loaded city this overwrites in place with NO confirm
  dialog (item 1, Run 1 established `0x02DFDD6A` is not needed here).
- `wait:6000` — let the write finish.

## Prediction procedure (run AFTER the lease, from the committed inputs)
Using left,top,zoom,rot from `### CAM:` read #1 and N from the MAP line (or N=512 known a-priori):
```
py -3.12 re/tools/pick.py --cam <left>,<top>,<zoom>,<rot> --n 512 --to-tile 280,180   # A start
py -3.12 re/tools/pick.py --cam <left>,<top>,<zoom>,<rot> --n 512 --to-tile 360,240   # A end
py -3.12 re/tools/pick.py --cam <left>,<top>,<zoom>,<rot> --n 512 --to-tile 520,360   # B start
py -3.12 re/tools/pick.py --cam <left>,<top>,<zoom>,<rot> --n 512 --to-tile 600,420   # B end
```
Predicted value-1 bbox = tile-space rectangle spanned by A's two endpoint tiles; predicted value-5
bbox = rectangle spanned by B's two endpoint tiles. (SC3 zone-drag fills the tile-space axis-aligned
rectangle between the start tile and the end tile.)

## Pre-registered outcomes (decided before firing)
| # | observation | verdict |
|---|---|---|
| PASS | value-1 raster bbox == predicted A bbox AND value-5 bbox == predicted B bbox (exact, integer) | **Projection anchored at 512.** Forward pick matches the game; the inverse (aim) is validated by the selftest round-trip. Delivers targeted authoring for the development run. |
| PARTIAL | one region matches its prediction, the other does not | Projection validated on the matching drag; investigate the other (hit chrome / off-open-ground / off-screen). One match = the claim holds (as item 1 pre-registered "one rectangle = PASS"). |
| FAIL-projection | both regions present but bbox(es) ≠ prediction | **Informative negative:** the formula or a field read is wrong at runtime. Report measured−predicted: a constant offset ⇒ origin/field error; a scale error ⇒ zoom/tilepx; axis swap/flip ⇒ rotation handling. Do NOT rescue with "close enough". |
| FAIL-noregister | zero raster change | Tool/drag did not apply (mechanism, not projection; unlikely on an all-open map). |
| FAIL-camread | `### CAM:` REFUSE, or >1 cell-map candidate (ambiguous `!!` line), or the USED candidate's rect is implausible | **VOID (instrument):** the anchor is unavailable, so no prediction can be made. Report which; do not interpret the raster. |
| VOID | no frame / crash / save did not write back | Report; re-fixture. |

Map-dims sub-check (independent of the above): a `### CAM: MAP 512x512` line ⇒ the `0x10016eba`
capture works. If it still prints `dimensions UNAVAILABLE`, the projection check still stands **iff
rot==0** (N enters only the rot 1/2/3 remap); note it and use N=512 known a-priori. If rot≠0 and
map-dims are UNAVAILABLE, the rot remap is unanchored ⇒ treat as FAIL-camread for that reason.

Record in `RESULTS.md` (write full per-run numbers — the `.sc3` is not retained): both `### CAM:`
readings verbatim, the four `--to-tile` outputs, predicted vs actual bbox for values 1 and 5, the
histogram, the follow/track gate line, and whether the MAP line appeared.

## Cleanup contract (final actions, every path including abort)
1. `patch_citysize.py --restore` + `patch_dirtbuf.py --restore`, both `--check` green.
2. Re-stage the owner's live build per BOARD standing rule (2026-08-26): FOUR-recipe SIMSPR
   (`scroll_speed=8 + drag_divisor=4 + drag_deadzone=2 + resize_rectfix`, gate 13 runs / 45 bytes)
   and TWO-recipe GZGraphicD (`resizable_frame + close_button_quit`). Read the exact gated command
   from BOARD.md; do not reconstruct it. Verify with the `--read` checks there.
3. Release the game lease `-DirtyOk` (SIMSPR/GZGraphicD staged = expected, not debris).
4. Never commit `N512_picktest.sc3` (game-derived).
