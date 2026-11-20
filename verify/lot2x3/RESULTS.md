# lot2x3 results (round 2026-11-20d): can SC3U handle a non-square (2x3) building?

**Verdict.** A 2x3 hand-placed building **works as data but does not draw correctly**. The game places it with a 2x3
highlight, claims all 6 cells, accepts neighbours on every side, saves and reloads it as 2x3, bulldozes it from any cell,
and the Mover moves it. The sprite system is square: it registers the building as a 2x2 sprite (SizeInCellsX x
SizeInCellsX), so in every view rotation a strip half a cell wide at the far (+z) end of the lot is not drawn and plopped
orange-brown ground shows there. The other orientation, 3x2 (X > Z), is unsafe: its sprite claims a 3x3 block, hides
the neighbour's building in the extra row and leaves a ghost after a bulldoze. Growables cannot get one: the zone
developer lays out square lots from SizeInCellsX only. Static evidence and the code changes correct support would need:
`re/analysis/LOT_SHAPES.md`. Importer support was not built (brief).

## 1. Static (LOT_SHAPES.md 1)

| path | X and Z separately? | where |
|---|---|---|
| place tool footprint + highlight | yes | SIMGEOM `0x1000956b` (+0x116 / +0x117), `0x1000968b` |
| placement check, commit | yes | SIMGEOM `0x10006ba6`, `0x100072f6`, `0x10007760` |
| occupant grid | yes | SIMGEOM `0x1000df90` (`0x1000dfda` X, `0x1000dff3` Z) |
| bounds (bulldoze, Mover, sprite remove) | yes | SIMGEOM `0x1001d305`, `0x1001d3af` |
| sprite insert, cell map, registration, clip | **no: n = SizeInCellsX for both** | SIMSPR `0x100192aa` (`0x10019341`), `0x10007b4d`, `0x1000c678`, `0x1000be25` |
| sprite change | no | SIMSPR `0x10019899`, `0x10019830` |
| save footprint field | **no: X, X** | SIMGEOM `0x1001cd38` (`0x1001cd9a`, `0x1001cda8` -> `0x1001cdb4`) |
| load | saved Z ignored, size from the exemplar | SIMGEOM `0x10002cc2` (`0x1000320c`, `0x10003252`) |
| zone developer | **no: X only** | SIMRCI `0x10027699` (`0x10027964`, `0x10027c2d`, `0x10027d43`) |

Footprint never turns with rotation: SizeInCellsX / Z forward to the attrib (SIMGEOM `0x1001d15d`, `0x1001d16c`) without
reading the rotation bits, and placed landmarks have rotation 0 (measured).

## 2. The probe

`verify/lot2x3/work/make_lot2x3.py --game dev\lot2x3\tree` writes the test plugin `Apps\PlugIn\lot2x3\lot2x3.pin` (269
bytes) + `lot2x3.dat` (79,393 bytes) into the test tree only. bldimport.py was not changed: the script imports its
helpers (landmark_table, frame_table, plugin_pin) and adds the non-square prop 0x66 and its own art.

| id | name | prop 0x66 | base |
|---|---|---|---|
| 38900 | Lote 2x3 (X2 Z3) | (2, 4, 3) | stats of stock 2x2 landmark 9507 (Coit Tower), type 18000 |
| 38901 | Lote 3x2 (X3 Z2) | (3, 4, 2) | same |

Art (`owner_shots/00`): a diagnostic drawing, 20 frames, zooms 0-4 native. Lot cells green checker, origin cell tan,
the cells outside the X x X square light blue; a box with world sides coloured -x blue, +x red, -z white, +z yellow, a
black ridge along z. Anchor = the registration point the engine uses (left vertex of the X x X block, LOT_SHAPES.md 2):
2x3 slots 0-3 at zoom 0 `20x16@0,8  20x16@0,10  20x16@4,10  20x16@4,8`, zoom 4 `320x224@0,126 ... 320x224@64,126`.

Lab: `verify/lot2x3/work/lab.py` (camera by the city view's own SetZoomAndRotation, tool arming by building layer
vt+0x54, direct placement by vt+0x38, occupant and sprite cell map reads, Demolish by DefOnHotKey 0x12, posted input).

## 3. In game (dev\lot2x3\tree, Madison, windowed 800x600, posted input and Frida game calls only)

Game PIDs 17380, 3832, 2052, all started by `sc3dev.ps1 run lot2x3`, stopped by PID. Each resize log has only the known
startup line `0xC0000096 at SC3U.exe+0x84122`.

### 2x3 (X 2, Z 3)

| check | result | picture |
|---|---|---|
| landmark dialog | both test entries at the end of the stock list, own preview and description line | `01` |
| tool | the stock tool (SIMGEOM vtable `0x10029504`), key `{0x207EDC0E, 0xB1D10002, 0x97F4}`, `+0x116` = 1, `+0x117` = 2 | |
| highlight | a 2x3 rectangle, blue, $35 | `02` |
| place (posted click) | resize.log `building placement (kind 0) at (177, 213): placed, price 35`; occupant rect [177, 213, 178, 215], SizeInCellsX 2, Z 3, rotation 0, 6 cells in the occupant grid | |
| sprite cell map | cells (177..178, 213..214): one sprite, size byte 2, registration (178, 213); cells (177, 215) and (178, 215): their own size-1 terrain sprites | |
| draw | building drawn; the light-blue third-row art stops exactly 128 px (2 x 64 at zoom 3) right of the left vertex, the tip beyond is not ours | `03` |
| 4 rotations, zoom 4 | orientation correct in all four (long sides, short ends and origin cell turn with the view). The cut is the right tip in rotations 0 and 1, the left tip in 2 and 3, always the +z end, as LOT_SHAPES.md 2 predicts | `04` |
| cut tip colour before reload | sampled (0, 112, 152) and (0, 116, 152); the placement highlight over plain ground sampled (0, 120, 152) and (0, 116, 152): the highlight stays on the two uncovered cells, through camera changes | `04` |
| query dialog | name, description, picture (the dialog's picture shows the full art), "Mover" and "Copiar ID" | `05` |
| Mover | highlight 2x3 at the target (`06`); `MOVE start ... cells [177 213 178 215]`, `moved building (original) cells [177 213 178 215] removed`, `MOVE placement (kind 0) at (179, 206): placed, price 30` (bulldoze 30 = 6 cells x $5). New rect [179, 206, 180, 208]. The old site is plain ground | `07` |
| place inside the third row | park (`{0x207EDC0E, 0x57E, 0xD}`, 1x1) at (179, 208) and (180, 208): refused | |
| neighbours, flat ground (all vertices 31) | parks at (178, 206), (178, 208), (181, 206), (181, 208), (179, 205), (179, 209), (180, 209): all 7 placed, drawn correctly in four rotations | `08` |
| first neighbour try, old site | (176, 214), (176, 215), (177, 216) refused, cost 112 / 118: each cell is sloped (vertex heights 31 / 32 / 33); every flat outside cell was accepted. Not a lot-shape refusal | |
| save | autosave: `207EDC0E B1D10002 38900 at (179,206) rot 0 size 2x2 flags 68100082`: the footprint field is 2x2 | |
| reload (PID 3832) | occupant rect [179, 206, 180, 208], SizeInCellsX 2, Z 3, 6 cells; sprite again 2x2 (reg (180, 206)); the cut tip now shows orange-brown plopped ground | `09` |
| bulldoze | Demolish (hotkey 0x12) over a third-row cell tints the whole building, $30; the click removes the occupant; all 6 cells back to their own terrain sprites | `10` |

### 3x2 (X 3, Z 2), placed next to the park at (181, 206)

| check | result | picture |
|---|---|---|
| place | direct placement at (180, 204): placed; occupant rect [180, 204, 182, 205], 6 cells; the park at (181, 206) still an occupant | |
| sprite cell map | all 9 cells (180..182, 204..206): one sprite, size 3, reg (182, 204). The park's sprite at (181, 206) was replaced | |
| draw, 4 rotations | the park is no longer drawn; fragments of the building appear a second time over the extra row (a second bolt, coloured patches in rotation 0, white wedges and a lower copy in 2 and 3) | `11` |
| bulldoze | occupant gone; cells (180..182, 204..205) back to terrain sprites; cells (180..182, 206) still point at the removed sprite `0xc458b68` (reg (182, 204), size 3) and draw it, through rotation changes; the park stays invisible; no fault | `12` |
| reload (PID 2052) | the ghost is gone, the park has its own sprite again | `13` |

## 4. What it means for the importer (not built)

- **Landmarks and rewards, data only:** possible for w x d with w < d (prop 0x66 = (w, h, d), anchors as the probe's),
  with a visible defect in every view: a (d - w) / 2 cell strip at the +z end is cut and shows plopped ground. A 3x2
  model must be turned so its long side runs along z. Saves record w x w (harmless in game, wrong for offline tools that
  read the footprint field). LOT_SHAPES.md 5.1.
- **Drawn correctly:** a SIMSPR patch for rectangular sprite registration (6 sites, LOT_SHAPES.md 5.2) plus one SIMGEOM
  byte for the save field, or square pieces placed together like the stock 4-piece rewards (5.3). Both are mod code.
- **Growables:** no (5.4).
- **Recommendation:** keep the current rule (the smallest SC3 square that holds the SC4 lot) for the converter, and treat
  2x3 as a choice between the cut end (data only) and the SIMSPR patch. The 5x5 stream is unaffected: 5x5 is square.

## Pictures (`owner_shots/`)

| file | what |
|---|---|
| `00_test_art_2x3_and_3x2_zoom2.png` | the probe art, zoom 2, slots 0-3 (row 1 2x3, row 2 3x2), magenta ring = anchor |
| `01_landmark_dialog_test_entries.jpg` | stock landmark dialog, the two test entries, 2x3 selected |
| `02_tool_highlight_2x3.jpg` | the placement highlight, 2x3 |
| `03_placed_2x3_zoom3_clip_at_2_cells.jpg` | placed, zoom 3, enlarged 3x: the art stops 2 cells right of the left vertex |
| `04_2x3_four_rotations_zoom4.jpg` | view rotations 0-3, zoom 4 |
| `05_query_dialog_with_mover.jpg` | "?" dialog of the 2x3 |
| `06_mover_highlight_2x3.jpg` | Mover tool over the target |
| `07_after_move.jpg` | after the move, old site clean |
| `08_neighbours_on_every_side_four_rotations.jpg` | 7 parks around the moved 2x3, rotations 0-3 |
| `09_after_save_and_reload.jpg` | after reload, rotations 0 and 2: orange-brown cut tip |
| `10_bulldoze_from_the_third_row.jpg` | Demolish over a third-row cell, and after the click |
| `11_3x2_four_rotations_garbage.jpg` | the 3x2, rotations 0-3 |
| `12_3x2_bulldozed_ghost_left.jpg` | 3x2 Demolish hover, after the bulldoze, rotated, back |
| `13_3x2_site_after_reload_clean.jpg` | the 3x2 site after a reload |

## Not tested

- Loading a city that holds a 2x3 with the plugin removed (plop measured empty lots for square landmarks).
- A 2x3 reward or civic look (same plugin route and engine paths as a landmark; rewards are keyed by type).
- sc3undo and the picker (Ctrl+F) on a 2x3.
- The SIMSPR patch of LOT_SHAPES.md 5.2 (described only).
