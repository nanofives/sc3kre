# STATUS bldfile (round 2026-11-18c): DONE

## goal
Downloaded Building Architect `.bld` files grow as new zoned buildings (ids 38000+) without the player importing
them into the Building Architect. Brief: `re/sessions/ROUND_2026-11-18c_buildings_look_bld.md`, stream bldfile.

## verdict + deciding RVA
- Works: 4 `.bld` buildings grew in Sacramento (56 / 6 / 63 / 45 lots at 5 game-run minutes). `verify/bldfile/RESULTS.md`.
- A `.bld` holds NO game frames: block model `0xE3F87B0C` (SIMBABLD `0x1200a849`), info `0xE3F87B0F`
  (`0x1200b7ef`), one 200x200 RGB565 preview `0xE3F87B0E` (`0x12003bf6`) = view slot 0 (IoU 0.971 mean at zoom 3
  against BAT.DAT, 15 buildings). `re/analysis/BLD_FORMAT.md`.
- Art: BAT.DAT's real frames when the player's BAT.DAT has the building, else the preview (slots 1 / 3 mirrored:
  the labelled fallback, wrong facades on asymmetric buildings).
- Real 4-view render: BA batch renderer `0x12001faf` (vtable `0x12069a84` +0x10, class `0x79F4AAD1`) runs only in
  Baapp.exe. Reachable by one Frida call, not driven: no windowed option found, a launch could switch the display
  mode. Next step written in RESULTS ("Real frames").
- bldlook follow-up done: `x_bldrender.style` per model, passed to bldrender, in the cache key. `.bld` preview art
  defaults to the BA look (zoom 4 doubled, no palette: BAT.DAT frames hold a median of 1,418 colours).

## built
- `re/tools/bldimport/bldfile.py` (new): reader, preview to 20 frames, BAT.DAT frames, class suggestion, CLI
  `info` / `sheet` / `check` / `js-expect`.
- `re/tools/bldimport/bldimport.py`: `.bld` in the models folder (default entries, `scan`, lot from the file), style
  per entry.
- `re/tools/bldimport/classifier.html`: opens `.bld` (own preview as thumbnail and in the view, class from the
  category); `&base=` / `&files=` demo hooks. `bld_js_check.mjs` (new): page reader = Python, 17 of 17.
- `re/analysis/BLD_FORMAT.md`, `verify/bldfile/RESULTS.md` (new).

## proven game-side vs static only
- game-side: growth of 4 x 2x2 buildings (1 bat art, 3 preview art), pictures in `MAIN\verify\bldfile\owner_shots\`.
- static: format (17 of 17), preview fit table, install readback 20/20, classifier in headless Chrome.
- not checked: 1x1 / 3x3 / 4x4 `.bld` in game, reload, `restore`, a downloaded Simtropolis `.bld`.

## blocked on
nothing

## files owned
From `dev/bldfile/wt`: `re/tools/bldimport/bldfile.py` (new, `git add -f`), `re/tools/bldimport/bld_js_check.mjs`
(new, `git add -f`), `re/tools/bldimport/bldimport.py`, `re/tools/bldimport/classifier.html`,
`re/analysis/BLD_FORMAT.md`, `verify/bldfile/RESULTS.md`. `re/tools/bldimport/bldrender.py` shows modified but is
byte-identical to main c308775 (checked out from main, no merge commit). MAIN: `re/sessions/STATUS_bldfile.md`.
Not committed: `MAIN\verify\bldfile\owner_shots\*.jpg`, `MAIN\verify\bldfile\runs\`.

## game-harness need
none left. The game run is stopped. `dev/bldfile/tree` still has the 4 test buildings installed.

## asks of other sessions
none
