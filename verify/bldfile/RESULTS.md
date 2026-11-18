# bldfile: downloaded Building Architect `.bld` buildings grow as zoned buildings (2026-11-18c)

Verdict: **works, without the Building Architect, with one-view art.** A `.bld` dropped into the models folder becomes
a new growable (ids 38000+, `sc3build\ids.json`), class from its category and lot from the file. In Sacramento all 4
test buildings grew by the first autosave and kept growing: 56 / 6 / 63 / 45 lots after 5 game-run minutes.

The catch is in the file format: **a `.bld` holds no game frames**, only the BA's block model and one 200x200
preview, which is the BA's own render of view slot 0 (`re/analysis/BLD_FORMAT.md`). So the art comes from:

1. **`bat`**: the player's `Apps\BARender\BAT.DAT` already holds the building (matched by the `.bld` id, else by
   name): its real 16 frames, all four views. True for the 15 buildings the game ships, and for any `.bld` the
   player once added in game.
2. **`preview`** (no BAT.DAT entry): the preview, resampled per zoom. Slot 0 is right. **Slots 1 and 3 are the
   mirrored picture and slot 2 the picture itself**, so asymmetric buildings show the wrong facade from three of four
   camera rotations. This is the labelled fallback ("approximate views").

`x_bld.art` per entry: `auto` (default: bat when available, else preview), `bat`, `preview`.

## Real frames for every `.bld` (the orchestrator's question): reachable, not used this round

The BA's batch renderer exists: `sc3_bat_export_rendered_buildings_ixf` (SIMBABLD `0x12001faf`) loads a list of
`.bld` paths, renders each and writes an IXF in BAT.DAT format (BLD_FORMAT.md 4). It is slot +0x10 of the BA
application object (vtable `0x12069a84`, singleton `DAT_12079434`, class `0x79F4AAD1`). **It only runs inside
`Baapp.exe`**: no game module references any SIMBABLD class (searched every exe and DLL export), and the render path
calls the BA's own 3D view object (`this vt+0x24`).

What the real render would need:
- Launch `Apps\Baapp.exe` from a dev tree, attach Frida once its app object exists (`*(0x12079434) != 0`), call
  `vt+0x10(outPath, n, &paths, 0, NULL)` with cRZString objects (vt+0x14 = C string) and
  `{exceptions: 'propagate'}`, then read `outPath` with `bldfile.bat_frames`. One call renders a whole folder.
- Not done because Baapp.exe has no windowed option in `BATConfig.ini` or its strings, so a launch could switch the
  display mode on the owner's PC (hard rule: windowed only). First step next round: check how Baapp opens its
  display (GZGraphicD path, the same windowed patch sc3resize applies to SC3U), on a PC where a mode switch is
  acceptable or under the virtual display.
- The render settings (`[Lights] Preview*` in `Res\BA\BATConfig.ini`) are the ones the preview uses, so the output
  would match the preview at slot 0.

## Measured: preview art against the real frames

`py -3.12 re/tools/bldimport/bldfile.py check --game dev/bldfile/tree <17 .bld>`, 15 buildings in BAT.DAT:

| slot 0 vs BAT.DAT slot 0 | zoom 0 | zoom 1 | zoom 2 | zoom 3 |
|---|---|---|---|---|
| mask IoU, mean (min) | 0.879 (0.824) | 0.932 (0.854) | 0.968 (0.813) | 0.971 (0.793) |
| colour RMS (0-255) | 19.3 | 20.4 | 18.4 | 19.0 |
| anchor T difference, max | 1 px | 2 px | 2 px | 5 px |

The minimum and the 5 px are The Joneses, whose BAT.DAT entry is a different render (its id differs from the
`.bld`'s, batconvert design 1).

| slots 1-3 at zoom 3 | picture as is: IoU / RMS | mirrored: IoU / RMS | used |
|---|---|---|---|
| slot 1 | 0.798 / 64.0 | 0.826 / 54.9 | mirrored |
| slot 2 | 0.796 / 58.3 | 0.872 / 65.8 | as is (lighting: bright wall left in slots 0 and 2) |
| slot 3 | 0.806 / 64.9 | 0.822 / 57.1 | mirrored |

Render style (bldlook, merged c308775): `.bld` preview art defaults to the look of the BA's own BAT.DAT frames,
zoom 4 = zoom 3 doubled and no palette cut. The BAT.DAT zoom-3 frames hold a median of 1,418 colours (max 2,219),
not the at most 255 of Maxis stock art, and a 255-colour cut raised the zoom-3 RMS from 19.0 to 19.5. A style named
in `x_bldrender.style` applies its zoom-4 and palette steps. Its light, contrast and lawn steps are for bldrender's
renders and never touch BA art. For OBJ models `x_bldrender.style` now picks the bldrender style per model
(default `$SC3BLD_STYLE`, else `stock`) and is part of the render cache key.

## Evidence

| check | how | result |
|---|---|---|
| format | `bldfile.py info Buildings\*.bld` (copies) | 17 of 17 parse, every record consumed to its last byte |
| classifier reader | `node re/tools/bldimport/bld_js_check.mjs` against `bldfile.py js-expect` | 17 of 17: name, architect, lot, category, id, class, preview pixels (sha256) |
| classifier page | headless Chrome, `?demo=1&base=<folder>&files=a.bld,...` | thumbnails from the preview, class from the category (Kankakee's 0x20F: no class, starts off), lot from the file; OBJ selftest `"pass":true` |
| install | `bldimport.py build dev\bldfile\bldin --game dev\bldfile\tree` then `check` | 4 of 4, 20/20 frames equal (also after the style change) |
| style | OBJ sample: default -> `stock`, `x_bldrender.style: clean` -> new cache key and frames equal to bldlook's `SC3BLD_STYLE=clean` render, `nope` -> refused | pass |
| in game | `bld_lab.py --tag run1 --ids 38000,38001,38002,38003` (test slot), Sacramento, churn `anarchy_res=5000`, speed 4, autosave 150 s, posted keys only | grown, table below |

| save | stock | 38000 Dupont House (bat) | 38001 Garvey Plaza (preview) | 38002 GuestHouse Building (preview) | 38003 North Shore Cannery (preview) |
|---|---|---|---|---|---|
| 1 (2.4 min) | 11,834 | 48 | 1 | 74 | 37 |
| 3 (5.0 min) | 11,689 | 56 | 6 | 63 | 45 |

Classes: Dupont and GuestHouse 3900 (category 0x208), Garvey 5700 (0x209), Cannery 8700 (0x20A), all 2x2, weight 20
(to see growth quickly; the default is 1). Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every run logs at
start.

Pictures (`MAIN\verify\bldfile\owner_shots\`, game art, not committed):
- `01_preview_vs_real_views_z3.jpg`: five buildings, the 4 views made from the preview next to the 4 real views.
- `02_garvey_plaza_preview_art_zoom4.jpg` (left, brick block with awnings), `03_guesthouse_preview_art_zoom4.jpg`,
  `04_north_shore_cannery_preview_art_zoom4.jpg` (centre), grown in Sacramento.
- `05` / `06_dupont_house_bat_art_zoom4_view0/1.jpg`: BAT art, two camera rotations.
- `07_guesthouse_area_zoom3.jpg`: the GuestHouse towers among stock buildings.
Raw dumps, counts and saves: `MAIN\verify\bldfile\runs\run1\`.

## What a player does

Put `.bld` files in a folder (next to OBJ models or alone), optionally open it in `classifier.html` to check classes
and save `models.json` (or `bldimport.py scan <folder>`), then
`py -3.12 re/tools/bldimport/bldimport.py build <folder> --game <game>`. Buildings whose category is not house /
shop / factory (schools, parks, `0x20F`, `0x212`, `0x217`) start disabled until a class is set.

## Not checked

- A `.bld` downloaded from Simtropolis: only the 17 shipped files (two of them, Tutorial House and Zweikky
  Unpainted, are not in BAT.DAT, so they took the preview path, but both are unpainted templates and were not grown).
- 1x1, 3x3 and 4x4 `.bld` buildings in game (all four test buildings are 2x2), the `stock` palette on `.bld` art
  in game, reload of a save with the buildings, and `restore`.
- Players have no Python. A PowerShell port like `bat_growables.ps1` was not asked for this round.

## Files

Commit from `dev/bldfile/wt`: `re/tools/bldimport/bldfile.py` (new, needs `git add -f`: `/re/tools/*` is ignored),
`re/tools/bldimport/bld_js_check.mjs` (new, `git add -f`), `re/tools/bldimport/bldimport.py`,
`re/tools/bldimport/classifier.html`, `re/analysis/BLD_FORMAT.md` (new), `verify/bldfile/RESULTS.md` (new).
`re/tools/bldimport/bldrender.py` in the worktree is main's c308775 copy (`git checkout main -- <file>`, no edit).
MAIN: `re/sessions/STATUS_bldfile.md`.
