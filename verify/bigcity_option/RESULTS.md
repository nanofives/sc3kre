# RESULTS - sc3bigcity, the "Enorme" New City option (2026-10-06)

Mod: `re/harness/src/sc3bigcity.c` + `bigcity_launch.exe`. Fifth size radio "Enorme" in the New City
dialog with a slider 512..1024 in steps of 128 (square map). Everything is patched in memory, no game
file changes. Logs from every run are in this folder (`runN.log`, not committed).

Not pre-registered. These were iterative owner hand tests, each run's finding drove the next build.
The owner's verdict on run 5: "all of those things works perfectly".

## Runs

| run | build | who | result |
|---|---|---|---|
| 1 | first build | owner | Option appears, slider drives 512..1024, 512 and 1024 cities created. Radio drawn over the "Tamaño" title, slider crossed the column divider. Ran FULLSCREEN (no windowed patch). Owner: 512 camera bugged, 1024 terrain "spikes on every tile" + camera bug |
| 2 | + layout, windowed, depth 9 | owner | 1024 terrain "much better", spikes left every few blocks, worst on rivers. Right-drag "barely works then stops". Zoom 3 and 4 draw nothing at 1024. Minimap clicks near the north inconsistent |
| 3 | + river 4096 samples | owner + `re/tools/bigcity_camtrace.py` | Camera Translate (SIMSPR `FUN_1001d503`) refused EVERY step on three 1024 cities: 0 accepted of about 950, at zoom 0, 2 and 4. Screen centre was on valid tiles (494,497) and (796,803), both >= 256 (`camtrace3.log`) |
| 4 | + 16-bit cell anchors | Claude | Regression: Europolis (256) loads, 43 SIMSPR sites detoured, renders correctly at close zoom with multi-tile buildings (`shot4_europolis.png`) |
| 5 | same | owner | Right-drag, arrows, zoom 3/4, minimap and rivers all work at 1024. Remaining: slider has no frame |
| 6 | + frame (Preferences recipe) | owner | CRASH opening New City. The GZCOM create in `FUN_10058c80`'s recipe handed back an object whose vt+0xc is a message handler, `0x22` read as a pointer |
| 7, 8 | + fault guard, step logs | Claude | Fault caught (`0xC0000005`) at the first call on that object, frame skipped, game kept running |
| 10 | frame via the dialog's own `FUN_1002d3c4` | Claude | Frame drawn around the slider (`frame10_crop.png`) |
| 12-14 | + hide unless Enorme, + invalidate | Claude | Hide works. Without an invalidate the slider stayed drawn until the mouse moved. With `vt+0x154` it repaints within 1 s (`hide14_strip.png`) |
| 15 | release candidate | owner | "looks good" |

## What each fix is, and its evidence

| defect | cause | fix | evidence |
|---|---|---|---|
| Renderer crash at N > 256 | SIMDIRT terrain buffer sized for 257x257 | 12 sites set ONCE for the max: size `2*1025*1025`, stride 1025, corner `0x804`. All 13 references to `DAT_10025bac+0x2c` go through these sites | inherited (`verify/citysize_mod_test`), every run here |
| Per-tile spikes at N > 512 | subdivision depth 8 at `0x10017f2f` only reaches every vertex up to 512 | `push 9` when N > 512, stock 8 otherwise | runs 1 and 2 |
| Dashed rivers at 1024 | river carved at a fixed 1024 Bezier samples | 4096 samples when N > 512 (4 sites) | runs 2 and 5 |
| Camera refuses every step, zoom 3/4 blank | cell record anchor X/Y stored as bytes (+8/+9) | high bytes in unused record bytes +0x12/+0x13, 8 writes + 48 reads detoured (`re/tools/gen_anchor16.py`) | run 3 trace, run 5 |
| Vertical extent = N | SIMINIT `FUN_1000c09c` writes N into the 8-bit Z range | clamp +0x40 to 256 | desk only, matches what shipped 256 cities get |

## Still open
- Minimap indicator near the map edges: the owner saw it fixed in run 5, but the edge clamp in `FUN_1000aa4b` / `FUN_1000a707` was never traced. Not specific to big maps.
- SIMSPR `FUN_100071a3` / `FUN_10008835` pack a cell rectangle into 4 bytes on a zoom change when the memory class is below `0x14`. Not reached on this machine. Untested.
- Development (zones growing) at 512+ has still not been measured in an instrumented run. The owner has played the cities by hand.
- Combining with `sc3resize.dll`: each launcher injects only its own DLL. Untested together.
- Above 1024 the generator overflows (`W*H*255*12` in `FUN_10017c2d`) at 2048. The slider stops at 1024.
