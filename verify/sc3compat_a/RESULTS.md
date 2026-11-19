# sc3compat-a (round 2026-11-19e): 1999 .bld files and the player-side render tool

Verdict: **done, steps 1 to 4.** The 1999 Building Architect's `.bld` files read in Python and in the page (36 of 36
samples identical), the SC3U Building Architect renders them, and a player can now render any folder of `.bld` files into
real four-view game frames with no Python and no Frida: drop the folder on `render_bld.cmd`. The importer (page and
`bldimport.py`) uses that render as the art. Player route = Frida route, frame for frame (576 of 576). 0 display-mode
changes over every launch. New DLL 0 of 13 on Jotti. Installed by the page with that art, 3 of 4 1999 buildings grew in Sacramento within 10 game-run minutes.

## 1. The 1999 .bld format (BLD_FORMAT.md section 6)

Model record version 7, the v8 byte layout. Baapp's model reader `FUN_00413e1a` has a v7 branch: the u16 at 0x05 is
stored plus 1, and the u32 after each texture name is kept per name (`FUN_0041a852`) where v8 has a hash the loader reads
and drops; after the loop `FUN_0040f398` rewrites some cells [UNCERTAIN purpose]. The info record ends after the architect:
no owner string, no id (`FUN_004063c8` then draws a fresh random id at every load, `FUN_00409142`). Records `0xB9EC8F72`
and `0x99F88B9E` are absent (defaults in `FUN_00415a07`). Part records `0xE3F87B0D` are version 7 and end after the image
key (no kind u32; byte 36 holds 6 or 7 [UNCERTAIN: read as kind from the values]); part images are format `0x0AF1`, 4
bytes per pixel. Offsets checked on all 19 files (the orchestrator's note from sc3compat-b agrees: 85 against 89 bytes for
a 12-character name).

Tools: no id in the file, so the stand-in id is CRC-32 of the whole file (`bldfile.derived_ident`, same in `bldweb.js`
and the page block), and such a file never takes a BAT.DAT entry by name (the 1999 Hotel Splash, 58 texture names, is not
the SC3U one, 115).

| check | result |
|---|---|
| `bldfile.py info` / `parts` | 36 of 36 parse; every texture of the 19 resolves (stock or embedded), none missing |
| `bld_js_check.mjs --reader bldweb` (importer) | 17 of 17 and 19 of 19: name, architect, lot, category, id, id source, model version, height, grid, texture and part counts, preview pixels |
| `bld_js_check.mjs --reader page` (classifier.html block) | 17 of 17; 19 of 19 after the page fix (before it: 0 of 19, "Offset is outside the bounds of the DataView") |
| golden case `bld1999` (no render beside them) | Python pack = page, every file and 300 frames; preview art |

## 2. The SC3U Building Architect renders them

All 19 in one batch call: Frida route 72 s, player route 43 s, 0 mode changes. Picture: `owner_shots/01_*`.
The 1999 previews are less useful than SC3U ones: in 8 of 19 the stored preview is another camera rotation than view
slot 0 (silhouette IoU 0.97 to 0.99 against slot 1, 2 or 3; RMS 58 to 82), so preview-made art would show the wrong side.
Why the 1999 BA saved other rotations: [UNCERTAIN] (no 1999 BA binary here). In the "x" test files the preview walls
are flat where the SC3U render draws a tiled texture.

## 3. The player-side render tool (no Python, no Frida)

| piece | what |
|---|---|
| `re/harness/src/bawinonly.c` batch mode | `BAWIN_BATCH=<folder or list>`: after the GZGraphicD display guards (unchanged), hooks Baapp.exe's PeekMessageA import slot `0x4802b0` (only caller: main loop `FUN_0045f6de`), and on the main thread, 4 s after the menu window shows, makes the call ba_render.py made through Frida: `(*0x4954e0)->vt[+0x10](out, n, &paths, 0, NULL)` (`FUN_0040446b` -> `FUN_004044a9`). Writes `<folder>\bld_frames.ixf` + `bld_frames.txt`, then exits with a code. Checks every address it uses (app vtable `0x480c78`, slot `0x40446b`, cRZString vtable `0x480344`, import slot = user32!PeekMessageA), SEH around the calls, watchdog, never writes BAT.DAT or under BARender / Res\BA, deletes an old output first (FUN_004044a9 would move it into Res\BA\RenderedBuildingsBackup.IXF) |
| `re/tools/bldbat/player/baappw_patch.ps1` | Windows PowerShell 5.1 port of `ba_patch.add_import`: BaappW.exe from the player's own Baapp.exe. Accepts GOG 2.0.949 (1829cbe2...) and its signed copies (sc3mods_patch normalisation), refuses anything else with its hash, checks the result against the known output hash b377e796... before writing, writes only what differs, `-Remove`. Same bytes as ba_patch.py (checked) |
| `render_bld.ps1` / `render_bld.cmd` | one click (drop a folder on the .cmd): patch, launch `BaappW.exe -w -r800x600` with the batch env, sample every display's mode every 20 ms from outside (C# Add-Type) and kill the PID on any change, report, list the rendered buildings |
| `re/tools/bldbat/player/README.md` | what a player reads |
| `build_mod.ps1 -Mod bawinonly` | VERSIONINFO resource (AVVERSION); `ba_patch.py` builds through it |

Fail-closed checks (each a real launch): out = BAT.DAT -> exit 0xBA15 in 0.4 s, list with no .bld -> 0xBA10 in 0.4 s,
both before any window; the script also refuses a BAT.DAT / BARender / Res\BA out before launching. Unknown Baapp.exe
(one byte changed) -> refused, nothing written; simulated signed copy -> accepted, same BaappW.exe.

## 4. Proof

| check | how | result |
|---|---|---|
| player route, 17 shipped | `ba_batch_check.py` (render_bld.ps1 under powershell.exe 5.1, plus ba_gate's sampler in a second process) | rendered in 64.5 s, exit 0, mode samples 2,549 (script) + 3,465 (Python), 0 changes |
| player route, 19 from 1999 | same | 43.3 s, exit 0, 1,824 + 2,380 samples, 0 changes |
| frames = Frida route | `ba_compare.py frames` (size, anchor, every pixel, 16 per building) | 272 of 272 (17 shipped), 304 of 304 (19 from 1999) |
| importer reads the side IXF | golden case `bldside` (19 .bld + the player's bld_frames.ixf; one entry forced to preview) | Python pack = page: every file + 300 frames; 15 enabled buildings take "bat" art from bld_frames.ixf |
| page | the grid shows each .bld's four real views when bld_frames.ixf is beside it (`owner_shots/02_*`), Install uses them (`owner_shots/03_*`, pagetest bldside) | PASS |
| full suite | `run_all.sh` with all six arguments + BLD1999 + BLDSIDE (9 new steps) | 33 of 33, twice (the second on the final code); in a dev worktree it needs `SC3PACK_PACKS=<MAIN>\stage\st_packs` (sc3compat-b's default resolves to dev\stage) |
| antivirus | Jotti, bawinonly.dll SHA-256 f6b985f9... | 0 of 13 (BitDefender, eScan, G DATA, Kaspersky, ... found nothing; zxcore: filetype not supported) |

In game (`bld_lab.py --tag grow1`, test slot, posted input only, windowed): the page installed Licks (1x1, class 3300),
Maxis Plaza (3x3, 6300), Royal Arms Deluxe (2x2, 3900) and Whitley Manufacturing (2x2, 8700) from 1999 files with
`bld_frames.ixf` art, weight 20, into the dev tree (`pagetest.mjs --models inst\grow --apply`, `owner_shots/03_*`).
The tree's Apps also held BaappW.exe and bawinonly.dll the whole run (inert in SC3U: it checks the exe name).

| save | stock lots | 38000 Licks | 38001 Maxis Plaza | 38002 Royal Arms Deluxe | 38003 Whitley Manufacturing |
|---|---|---|---|---|---|
| 1 (2.4 min) | 11,701 | 705 | 0 | 86 | 34 |
| 5 (10.0 min) | 11,010 | 849 | 0 | 112 | 83 |

Maxis Plaza: the stock building its entry copies (179, the 3x3 class-6300 base) has 0 lots in both saves, so this city
did not develop that class and size in the run. The 3x3 path is not checked in game. Faults: only the
`0xC0000096 at SC3U.exe+0x84122` start-up line every run logs. Pictures `owner_shots/04_*` (Licks, four camera
rotations, each showing another side), `05_*`, `06_*`, `07_*`. After the run the tree was restored (`bldimport.py
restore`, its mods folder equal to the stage again).

## Changes to existing behaviour (needed by the fix)

- `bldfile.frames` / `bldweb.js bldFrames`: "bat" art now comes from `bld_frames.ixf` beside the .bld first, then
  BAT.DAT, then the preview. The import report names the source ("bat art from bld_frames.ixf / BAT.DAT").
- `bldimport.py` cache key includes `bld_frames.ixf` (else a cached preview render would survive a later render).
- `bldfile.ixf_buildings` keeps render order (groups in the order of their first override) instead of sorting groups.
- classifier.html: 1999 info record, grid thumbnails from the side render, the pack route keeps `bld_frames.ixf`,
  `window.bc.openFiles` exposed for pagetest's `--action open` on a plain folder.

## Not done / limits

- Only one Baapp.exe build is known (GOG 2.0.949; MAIN, original\modules and original\gog_2.0.949 hold the same file).
  A Steam or retail Baapp.exe that differs in code is refused until its hash is added (after checking every address
  bawinonly uses).
- `render_bld.ps1` shows the Building Architect window for the length of the render (normal window; it may take focus
  when launched, as any program does). Not tested minimised.
- Paths with characters outside the system ANSI code page: the Building Architect takes ANSI paths [not tested].
- 1999 part records: the kind byte is read from values only.

Files: runs in `verify/sc3compat_a/runs/` (frida1999, frida17, player17, player19, failclosed, golden, webtest, grow,
jotti; local, game art). Pictures `owner_shots/` (game art, not committed). Page fix for gamefont's file, applied:
`classifier_1999.patch` (kept for reference).
