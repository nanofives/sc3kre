# bldbat results (round 2026-11-18e): real four-view frames for any .bld, from the Building Architect itself

Verdict: done, steps 1 to 4. `py -3.12 re/tools/bldimport/bldfile.py render <folder> --game <dev tree> --out x.ixf
[--install]` renders any set of .bld files with the BA's own batch renderer (20 frames, 4 real views) in a windowed
Baapp, and writes a BAT-format IXF that bldimport.py and the classifier page read as "bat" art. 71 Baapp launches,
0 display-mode changes.

## Step 1: Baapp windowed, proven with no display-mode switch

Static (before any launch):
- In the Baapp process only GZGraphicD.dll imports DirectDrawCreate. No module (Baapp.exe, SIMBABLD, the GZ* and SIM*
  DLLs it loads) imports or names ChangeDisplaySettings. Baapp.exe and SIMBABLD only carry an orphan "DDRAW.dll" name
  string, not an import descriptor.
- GZGraphicD holds ONE IDirectDraw::SetDisplayMode call (vt+0x54 in sc3_gfx_set_display_mode `0x10011f73`) and ONE
  exclusive cooperative level (0x11 in `FUN_1001250d` with param 1). Both run only through set_display_mode(1): from
  Init (`0x100119a5`, when the fullscreen flag this+0x48 is set) or its vtable slot (`0x1001ee40`).
- this+0x48 is written by Init from the windowed byte (`0x10011547`), re-forced to 1 at `0x100117d6`, by the ctor
  before Init (`0x10010e0c`) and by set_display_mode itself (`0x10012090`).
- Baapp has SC3U's command line (`FUN_00411637`): `-w` = windowed setter vt+0xe4(1), `-r800x600` = size (vt+0xdc).

Patch: `bawinonly.dll`, imported by a NEW `BaappW.exe` (copy of stock Baapp.exe SHA-256 1829cbe2..., one added import
section; the linked Baapp.exe is never written), `re/tools/bldbat/ba_patch.py`. From a loader notification before
GZGraphicD's DllMain: windowed byte 1, nop `0x117d6`, entry guard on `0x10011f73` (a fullscreen request returns at
once, counted), entry guard on `0x1001250d` (param forced to 0 = DDSCL_NORMAL), FIX16, per-monitor DPI. Every site is
checked byte for byte; a mismatch terminates the process before any display init (fail-closed).
- Offline check (no window, no DirectDraw): `baapp_test.exe` + GZGraphicD.dll: all patterns matched, 2 of 2 fullscreen
  calls refused with a null `this` (returned before touching it).
- Runtime: `re/tools/bldbat/ba_gate.py` samples every display's mode from a separate process every 20 ms. 71 launches
  (gate, A/B batches, renders): 0 mode changes. Window style 0x94CA0000 (caption), not topmost, 806x662 on the
  3840x2160 display. Menu: `owner_shots/01_baapp_windowed_menu.png`.

Stability (two crashes found and fixed, both in Baapp, none from the mode patches):

| config (`-w -r800x600` unless noted) | alive / launches |
|---|---|
| FIX16 off (any bpp) | 2 of 19 (crash in the prop loader at 1.2 to 2.4 s) |
| FIX16 on, STRTOKFIX off | 31 of 37 (batches 27 of 29, single runs 4 of 8) |
| FIX16 + STRTOKFIX | 8 of 8 tests, then 7 of 7 render runs |

- FIX16 is needed even with `-t32`: GZGraphicD creates colour-type-7 surfaces regardless.
- STRTOKFIX: stock Baapp bug. `FUN_00419d88` (prop .met files, `0x419e04`) and `FUN_0041a3b3` (`0x41a429`) read a file
  into `operator new(filesize)` with no terminating zero and run strtok over it (`0x419e2b`, `0x41a44e`): it reads past
  the block and writes `\0` there. Crash at a later free (`BaappW_stkdmp.txt`: free <- `0x41889e` / `0x419faa`). Both
  calls now get size+1, zeroed.

## Step 2: driving the batch renderer

Baapp.exe never loads SIMBABLD.DLL: it carries its own copy of the BA code. `FUN_004044a9` is the same 2,044-byte body
as SIMBABLD's sc3_bat_export_rendered_buildings_ixf. Singleton `DAT_004954e0`, vtable `0x480c78`, slot +0x10 =
`FUN_0040446b`. `re/tools/bldbat/ba_render.py` launches BaappW, waits for the menu, attaches Frida and calls
`vt[+0x10](out, n, &paths, 0, NULL)` on Baapp's main thread (PeekMessageA hook, `exceptions: 'propagate'`), with
cRZString arguments built by Baapp's `FUN_00402c4c`. Works from the main menu (the view object is created on demand).
One call rendered all 17 shipped .bld in 63 to 83 s.

Against the shipped `Apps\BARender\BAT.DAT` (15 of the 17 are in it; 240 frames, zooms 0-3, 4 views):
- geometry: frame size and anchor equal in 237 of 240. Kankakee slot 3, zooms 1-3: 1 to 2 px taller in the render.
  Mask IoU mean 0.9998, min 0.9777.
- colour RMS per building (0-255): Longview Park 1.2-1.4, Dupont House / The Joneses 2-3, Maxis Towers 2.6-6.4,
  Proton, Garvey, GuestHouse, HiTech, Den Burg, Hotel Splash 3.6-6.7, Northeast Nonwovens 6.7-8.6. Dupont zoom 3
  slot 0: 79% of pixels identical, the rest differ by 1 or 2 RGB565 steps along edges (rasteriser rounding).
- North Shore Cannery 13-18, Headquarters 16-25, Trash & Burn 23-39: the shipped entries lack textures the render has
  (Trash & Burn: grey chimney, trucks and conveyor; Headquarters: no window details; `owner_shots/03_*`, `05_*`).
  Why the shipped entries were drawn with fewer textures: [UNCERTAIN].
- The Joneses, matched by name, renders the same building (RMS 2.4), not a different render.
- Group and instance are not the importers': group = an LCG seeded by timeGetTime, new per building per run
  (`FUN_004534bb`, `FUN_004534a0`); instance = a new id (`FUN_00404d73`, `FUN_00404d52`), and two buildings of
  different lots got the same one. Hence the re-keying in step 4.

Real views against the preview-made views the importer used until now: `owner_shots/02_ba_render_vs_preview_z3.png`
(Maxis Towers' logo facade and Trash & Burn's other sides appear; the preview method could only mirror the front).

## Step 3: custom parts

`py -3.12 re/tools/bldimport/bldfile.py parts <bld|folder> --game <tree>` lists every texture name a .bld uses as
color / embedded / stock (Apps\Res\BA) / custom (Apps\BACustom) / missing, with kind (paint, detail, prop) and hash.
The .bld embeds custom textures (record 0xE3F87B0D: name, hash, kind; 0xE3F87B10: the image; BLD_FORMAT.md 5). In the
17 shipped files: 84 embedded parts; the only name resolved nowhere is Kankakee's `bourbo~3.tga` (8.3 form of
`bourbon 03.tga`, same hash).

What the renderer does (Trash & Burn, 3 runs, 16 frames each):

| run | BACustom\Paints | .bld | result |
|---|---|---|---|
| X | as shipped (no blue_*.tga) | original (17 embedded) | full textures |
| X | same | embedded records stripped | the 13 parts with no file drawn flat, untextured (`owner_shots/04_*`); no error |
| Y | + magenta `blue_t05.tga` | both | identical to X: the same-named file with other pixels is ignored |
| W | + the 13 embedded images written as 32-bit TGA | stripped | identical to X original, 16 of 16 frames |

So: embedded copy first; else a BACustom file with the same content (Baapp reads BACustom only at start-up, no file is
opened during a render); else flat. A pack's .bld renders right without its BACustom files when it embeds its parts; a
.bld without the embedded copy needs the exact files. The hash function is [UNCERTAIN] (not a CRC32 of the name, the
file or its pixels).

## Step 4: `bldfile.py render`

```
py -3.12 re/tools/bldbat/ba_patch.py --tree dev\bldbat\tree          # once per tree: bawinonly.dll + BaappW.exe
py -3.12 re/tools/bldimport/bldfile.py render <folder|.bld...> --game dev\bldbat\tree --out x.ixf [--install]
```

Output: BAT-format IXF, group 0xBA1DBF1E, override and table instance = the .bld id, 16 pixel records on a block free
in the tree's BAT.DAT. `--install` merges it into `<tree>\Apps\BARender\BAT.DAT` (entries with the same id replaced,
backup `BAT.DAT.bldbat-orig`, delete-then-write so the stage's hard-linked file is untouched; checked: stage, MAIN and
backup hashes equal).

Checked: 17 of 17 rendered and installed; `bldfile.frames(bld, game, "bat")` returns the BA render for 17 of 17
(including Tutorial House and Zweikky Unpainted, which the shipped BAT.DAT does not hold); `bldimport.py build` on
Zweikky + Trash & Burn installs both with `"art": "bat"`. The classifier page reads BAT.DAT with the same rules
(`bldweb.js` batBuildings / batMatch); not run against the merged file this round.

## Not done / limits
- No in-game growth check of the new art this round (the "bat" install path was grown in game in round bldfile).
- Player-side route: needs Frida + Python today (orchestrator decides).
- `.bld` with lot 5 (the BA offers 5x5): batgrow flags lot 5 as a problem; untested.
- A .bld the BA cannot load is reported as "not in the render output".

## Files
Runs: `verify/bldbat/runs/` (gate*, ab*.log, r1 to r4). Pictures: `verify/bldbat/owner_shots/` (game art, not
committed). Ghidra: project `ghidra/SC3_Baapp`, export `re/ghidra_export_baapp/`, anchor `original/modules/Baapp.exe`
(all gitignored).
