# lotdraw results (round 2026-11-20e): non-square buildings drawn whole (SIMSPR patch)

**Verdict.** Done. sc3perf block **LOTRECT** draws X x Z buildings whole in both orientations (2x3, 3x2 and 1x3 tested),
in all four view rotations and at zooms 2, 3 and 4, with neighbours on every side drawn in the right order, and the
save records the true footprint. Placement highlight, tool placement, direct placement, the Mover, bulldoze from the far
row and save + reload work; the 3x2 leaves no ghost. Square buildings: pixel for pixel identical with the patch on and off in 20 of 20 views of Berlin (5 zooms x 4 rotations), outside the pixels the game animates while paused. Draw time: no measurable cost (display-list build per rotation and per builder call within the run-to-run spread).

Switch: `lot_rect=1` in `perf.ini`, env `SC3PERF_LOT_RECT=0` turns it off; mods page C row "Edificios no cuadrados" /
"Non-square buildings" (7 languages). Code: `re/harness/src/sc3perf_lotrect.c`. Static map of every site and why:
`re/analysis/LOT_SHAPES.md` section 8.

## 1. Why sc3perf

sc3perf already owns SIMSPR's sprite internals (SPRITES loader, SPR_REFCOUNT, SPR_IMGREF) and patches SIMSPR from a
watcher thread the moment the DLL maps, which is what this needs (every Insert must go through the patched code from
the first city on). sc3resize hosts the mods page, so it only got the row (one table entry, `MT_FEAT_DY` 17 -> 16 so 17
feature rows end where 16 did and the city checkbox stays at local y 418, clear of Volver at 436). If sc3perf.dll is
turned off on page C the feature is off with it.

## 2. What changed against the probe's plan (LOT_SHAPES 5.2)

| probe plan | found | done |
|---|---|---|
| Z in a free byte of the 0x14-byte cell record | `+0x12/+0x13` are stock padding, but sc3bigcity ANCHOR16 keeps the 16-bit registration cell's high bytes there. The first build wrote Z to `+0x12` and was refused at load (`LOTRECT> SIMSPR+0x07BE6 differs`, bigcity's cave was in) | flag bit 0x400 (unused in all of SIMSPR) + a side grid of Z keyed by the 16-bit registration cell; works with and without bigcity |
| registration, clip, depth bounds | as planned, plus the display-list **sort key**: cell sprites are ordered by the key of their registration view cell alone (comparator `0x1000c7a6`), which is the block's centre only for squares. First build: a park behind the 2x3 drew over its front face in rotation 2 (`owner_shots/06`, left) | key - (B - A) * 0x2000 (`0x1000c14b`, `0x1000d63f`): `06`, right |
| a 1 x Z lot | the draw lists treat `n = 1` as a single cell (`0x1000bf8d`, `0x1000d4aa`, `0x1000ca88`) | 0x400 records take the multi-cell path |
| save: SIMGEOM `0x1001cda8` vt+0xd4 -> vt+0xd8 | the Z argument (bits 6-11) is the `0x1001cd9a` call; and a landmark is a SIMMISC class (vtable SIMMISC `0x100405e8`) that saves through SIMMISC's own copy of the filler. A first build patching only SIMGEOM still saved `2x2` / `3x3` (measured) | the `0x1001cd9a` call in all 9 module copies of the filler (`LOTRECT> save footprint: 9 of 9`) |

## 3. In game (dev\lotdraw\tree, Madison, windowed 800x600, posted input and Frida game calls, PIDs started by `sc3dev.ps1 run lotdraw`)

Test plugin `verify/lotdraw/work/make_lotrect.py` (from the probe's generator): 38900 "Lote 2x3 (X2 Z3)", 38901 "Lote 3x2
(X3 Z2)", 38902 "Lote 1x3 (X1 Z3)", anchors at the true lot's left vertex (L = 0 in every slot, LOT_SHAPES 8.4).

| check | result | picture |
|---|---|---|
| load | `LOTRECT> 29 SIMSPR sites patched`, `save footprint: 9 of 9`, sc3bigcity `ANCHOR: 43 SIMSPR sites detoured` in the same run (both orders seen across launches); every mod log free of `differs` lines except the known FIX16 duplicates (sc3resize installs it first) | |
| sprite cell map, 2x3 at (177, 213) | 6 cells (177..178, 213..215), one sprite, size byte 2, reg (178, 213), flag 0x400 on all 6; corners 0x2000 (177, 213), 0x4000 (178, 213), 0x800 (178, 215), 0x1000 (177, 215) | |
| sprite cell map, 3x2 at (180, 204) | 6 cells (180..182, 204..205), reg (182, 204); row z = 206 untouched (the probe's 3x3 block covered it) | |
| 1x3 at (174, 208) | 3 cells, reg (174, 208), size byte 1, flag 0x400, corners on the 1 x 3 rect | |
| draw, 4 rotations, zooms 2-4 | all three whole: the light-blue cells (outside the short side's square) drawn in every view, no cut strip, no duplicated fragments | `01`-`05` |
| neighbours | 1x1 parks on every side (22 placed in the final session; in an earlier session 4 cells were refused, all sloped: vertex heights 31-35, as in the probe) drawn in front of / behind the buildings correctly in all four rotations | `01`-`03`, `06` |
| placement highlight | 2x3 rectangle (stock already did this) | `07` |
| placement with the tool (posted click) | `RELOCATE> building placement (kind 0) at (181, 212): placed, price 10`; whole, no highlight colour left on any cell (the probe saw it stuck on the two uncovered cells) | `08` |
| query dialog, Mover | dialog with Mover; 2x3 highlight at the target; `moved building (original) cells [181 212 182 214] removed`, `MOVE placement (kind 0) at (186, 214): placed`; old site clean | `09`, `10` |
| bulldoze from the far end | Demolish hovered at the +z (yellow face) end of the lot tints the whole building, $30 (the hovered cell was not read back); after the click the 6 cells are 1x1 terrain records, no 0x400 left | `11`, `12` |
| 3x2 bulldoze | parks at (180..182, 206) keep their own sprites (size 1, self-registered); site clean | `13` |
| save (autosave) | `38902 at (174,208) size 1x3`, `38900 at (177,213) size 2x3`, `38901 at (180,204) size 3x2` (occupant_layer.py: bits 0-5 x, bits 6-11 z); before the fix the same file said 2x2 / 3x3 | |
| reload of that save (`lotdraw test.sc3`) | occupants 1x3 / 2x3 / 3x2 and sprite maps X x Z with 0x400 again; whole in all four rotations | `14` |
| switch | page C row unticked + OK: `MODTOGGLE> SC3PERF_LOT_RECT off at the next start`, `sc3mods.ini [env] SC3PERF_LOT_RECT=0`; restart: sc3mods `[env] SC3PERF_LOT_RECT=0 (sc3mods.ini)`, sc3perf `LOTRECT> off (lot_rect=0)`, the saved 1x3 drawn as one cell over plopped ground; ticked + OK: key removed | `16`, `17` |
| faults | none in any of these runs (resize.log VEH lines: only the game's own 0xC0000096 probe) | |

One autosave faulted inside the game's save (`SAVE> autosave is OFF ... the game faulted inside its own save`, a call to
address 0 from SIMGEOM `0x10024331`) while a Frida Interceptor sat on the patched instruction `0x1001cd9a` itself
(`work/savetrace.py`). With no Frida attached the patched fillers saved 4 autosaves in two sessions without a fault, the class's slot 0xd8
is a valid SizeInCellsZ (SIMGEOM `0x1001d16c`), and later tools never hook that instruction. `[UNCERTAIN: cause not traced;
the evidence points at the Frida hook on that call]`

## 4. Square buildings unchanged (pixel A/B)

Berlin, Germany (busy, 800,944 people), map area 700 x 540 of the 800 x 600 frame (the HUD's ticker scrolls), sc3perf
overlay off, city PAUSED as loaded, posted keys only (numpad +/- zoom, PageDown rotate), FRAMEDUMP.

- **Two loads cannot be compared.** Control: the same build loaded twice with LOTRECT off (`abtest.py off` vs `off2`)
  differs in every view outside the animation (744 to 30,209 px, small spots scattered over buildings, trees and roads;
  `work/results/compare_cross_session_off_vs_off2.txt`). The off vs on runs differed by the same amounts
  (828 to 29,189 px, `compare_cross_session_off_vs_on.txt`), so a cross-session A/B says nothing.
- **So the A/B toggles the patch inside one session** (`work/intoggle.py`): the 29 SIMSPR sites are written from outside
  (WriteProcessMemory: the live patched bytes vs `Apps\SIMSPR.DLL.shipped`), then 4 PageDown steps (full repaints with
  that code, back to the same view) and 3 dumps per state. Square records carry no 0x400 flag and the cell map is the
  same in both states, so only the draw code differs. Pixels that change between the dumps of either state are
  smoke plumes and are masked (0 to 9.5% of the area, none at the two far zooms).

| views | result (`work/results/intoggle_berlin_20_views.txt`) |
|---|---|
| zoom A, B (8 views) | identical, 0 px differ |
| zoom C, D, E (12 views) | 12 to 1,656 px differ outside the mask; all but 10 of them lie within 8 px of a smoke plume, i.e. plume frames the 3 samples missed (`intoggle_berlin_residue.txt`) |
| re-run of zooms C and E with 6 samples per state (`intoggle_berlin_zoomC_E_6_samples.txt`) | 6 of 8 identical; zoom C r0: 1 px, at a different place than in the first run (an animation); zoom E r3: one 4 x 2 px block at (318..321, 92..93), green 132 vs 128. In the first run it was 132 with the patch ON, in the re-run 132 with the patch OFF: its colour follows time, not the patch (a slow two-state animation) |

So 20 of 20 views match outside animation. **Positive control** (`intoggle_control_fixture.txt`, `owner_shots/15`): the
same toggle on the test city with the three non-square landmarks differs by 13,288 to 23,758 px in all 4 rotations
(with the code off the flagged 1x3 is drawn as fragments), so the method does see a draw change.

## 5. Draw time

Same session, Berlin, game running, camera fixed, LOTRECT toggled between the patched and the shipped bytes per round
(`work/benchhook.py`): read-only Frida hooks time every call of the two display-list builders (SIMSPR `0x1000be25` zooms
0-2, `0x1000d0f5` zooms 3-4) with QueryPerformanceCounter while 8 posted PageDown rotations redraw the view. 3 rounds.
(A first attempt called the full repaint iso vt+0x14c from Frida (`lab.py bench`): the game exited silently on that
call, no VEH line. An earlier session of the same attempt also exited, 14 s after a WriteProcessMemory to SIMSPR+0x19341
failed with no error code recorded `[UNCERTAIN: cause not traced]`. So the game draws by itself here.) Results `work/results/bench_zoom3.txt`, `bench_zoom1.txt`:

| zoom | builder ms per rotation, on | off | us per builder call, on | off |
|---|---|---|---|---|
| 3 (high-zoom builder) | 25.65, 25.75, 24.01 (median 25.65) | 29.34, 27.49, 21.96 (median 27.49) | 4.06, 4.05, 4.07 | 4.36, 4.46, 3.88 |
| 1 (low-zoom builder) | 4.16, 4.46, 4.19 (median 4.19) | 4.50, 5.24, 3.96 (median 4.50) | 17.6, 17.6, 19.0 | 17.9, 21.1, 19.8 |

The sim runs during the measure, so the number of builder calls per round varies (45,242 to 53,882 at zoom 3). The
patch's cost is below the run-to-run spread; per square sprite it adds one `test word [rec+0x10], 0x400` and a
not-taken jump at each patched site, and the two C copies of the registration functions.

## 6. Not tested / open

- |X - Z| >= 2 (1x3, 2x4, 3x5): one neighbour cell behind the far end and one in front of the near end share the
  centre depth key, no single key orders both (LOT_SHAPES 8.3). The 1x3 showed no wrong overlap at zoom 4 with parks
  around it; a tall neighbour exactly there is not tested.
- Effect anchors that centre on an occupant with SizeInCellsX only (fire, riots: SIMSPR `0x10032e3e`, `0x10039850`,
  `0x1003ccbd`, `0x1002249b`) are not changed: on a non-square lot they sit (Z - X) / 2 cells off centre `[not run]`.
- A non-square reward or civic look, sc3undo and the picker on a non-square building, and a city with one loaded with
  sc3perf turned off (the sprite then registers X x X again and the art is off by (d - w) x W / 2 in two rotations).
- 1024 maps with a non-square building (the side grid is sized per city, the 16-bit anchors come from bigcity): static
  only.

## Files

Code: `re/harness/src/sc3perf_lotrect.c`, `sc3perf.c`, `sc3resize.c`, `re/harness/lang/*.txt`. Tools (MAIN
`verify/lotdraw/work`): `lab.py` (probe lab + `bench`, record flags), `make_lotrect.py` (test plugin), `shots.py`,
`abtest.py` (cross-session A/B, kept for the control), `intoggle.py` (in-session A/B), `benchtog.py`, `savetrace*.py`.
Pictures: MAIN `verify/lotdraw/owner_shots` (01-17). The tools expect to run from `dev\lotdraw\wt\verify\lotdraw\work`
(paths relative to the worktree, as the probe's lab). The test plugin is still in `dev\lotdraw\tree\Apps\PlugIn\lotdraw`
(`make_lotrect.py --game <tree> --restore` removes it) and the test city is `dev\lotdraw\tree\Cities\lotdraw test.sc3`.
