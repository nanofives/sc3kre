# STATUS hwyscurve (highway S-curve / lateral jog), child of the 2026-10-29 round

## goal
Owner 2026-10-29: "i need this S curve for highways" (`MAIN\verify\hwyscurve\owner_report.png`). Two parallel elevated
highways one cell apart that overlap leave "Highway Construction" 15149 in the overlap. Wanted: real pieces, drivable.

## verdict + deciding evidence (milestone 1: cause found, 2026-10-29 01:40)
- Reproduced in `dev\hwyscurve\tree` (Roadless Paradise, all mods on, sc3netmod wrote 0 cells in those passes):
  band 1 drag (94,90)->(104,90) = rows z 89/90, x 93..104; band 2 drag (104,91)->(113,91) = rows z 90/91, x 103..113.
  Overlap x 103..104 (2 columns) -> 15149 at (104,89), (103,90), (104,90), (103,91) = the owner's picture exactly.
  Overlap 3 (x 99..101 at z 155..157) -> 5 cells of 15149, same staircase.
- Overlap 1 (one shared column) is resolved by stock: a one-column diagonal 11223.0 / 11224.0 / 11223.2.
- Full-width shift (bands touching side by side, overlap 3) -> 15149 at 4 cells + stray 73 caps (another shape).
- Why 15149 (offline tiler, `netrules explain hwsc_lab.sc3 X Z --net HWAY`, verdict "agrees with the save" on all 4):
  no Simple or Complex HWAY rule matches the cells' neighbour masks (0xdf, 0x7f, 0x36, 0xc9), so the final pass
  fallbacks HWAY_GRND_final.txt #15 / #9 / #6 write 15149.0. The shared middle row holds band 1's -x carriageway and
  band 2's +x carriageway: two directions in one cell, which no stock piece draws.
- Offline mockups (hwpaint, overlap 2 and 3): scratch, sent with the plan.

## startup crash seen 2026-10-29 (for the orchestrator to route; not chased)
Launch = `sc3dev.ps1 run hwyscurve -City "Roadless Paradise.sc3"`: SC3MODS_DIR=dev\hwyscurve\inst, SC3MODS_MULTI=1,
SC3RESIZE_WINMEM=0; tree from release sc3mods-2026-10-29 (584ab1f), all 8 mods mapped (sc3resize, sc3bigcity,
sc3overscroll, sc3simrun, sc3perf, sc3netmod, sc3undo, sc3autosave), freshly built DLLs (first starts after `sc3dev new`).
Display: one monitor, 1536x864 logical. Another SC3U.exe (pid 2676, not mine) was running the whole time.
- launch 1 (pid 8744): `RZ *** VEH FAULT *** code=0xC0000005 at GZGraphicD.dll+0x14904`, READ addr 0x00000000, at
  5826 ms, tid 0x4dbc. regs eax=001AF338 ecx=00000000 edx=001AF318 ebx=02EEDE18 esi=0F224578 edi=001AF338 ebp=001AF340
  esp=001AF308. Stack: GZGraphicD+0x1F328, SC3U.exe+0x3D4F7, SC3U.exe+0x41436, GZWIND+0x1EDAA, GZWIND+0x200F2,
  GZWIND+0x21689, GZGraphicD+0x15AFF, GZGraphicD+0x11EB4, GZGraphicD+0x17E84, win32u+0x12EC, GZGraphicD+0x17EE3,
  GZGraphicD+0x17E11, sc3resize.dll+0x30E8D, GZGraphicD+0x17E2C. Process gone.
- launch 2 (pid 788): same fault, GZGraphicD+0x14904 READ 0, at 1025 ms on the main thread (tid 0x05d0, the thread
  that logged the EARLY GZGraphicD patch), regs eax=001AF940 ecx=00000000 edx=001AF920 ebx=02D92748 esi=0F37E708
  edi=001AF940 ebp=001AF948 esp=001AF910. Stack lines not kept (the next launch overwrote sc3resize.log).
- launches 3..: fine (pid 4980, 21264 and later). Every launch also logs the benign
  `code=0xC0000096 at SC3U.exe+0x84122` at ~0.4 s.
- 0x14904 is inside GZGraphicD FUN_10014894 (the blit dispatcher, null +0x44 surface), the same site as the
  monitor-change crash (memory project-test-display-environment) and the one mod-off crash in verify/simrun/RESULTS.md.
- `-Stock` NOT run: SC3MODS_OFF=1 leaves sc3resize unmapped, so the game starts fullscreen (display mode change),
  which the always-windowed rule forbids and which can crash the other game running on this PC.

## built (milestone 2: fixed, 2026-10-29 02:40)
- `re/harness/src/sc3netmod_hwsc.c` (new block HWSC, off `SC3NETMOD_HWSC=0`), registered in sc3netmod.c (#include
  after hwave) and sc3netmod_rbt.c (prototypes, `hwsc ` table line, `hwsc_run(hp);` in rb_hwy after hwave,
  `hwsc_stats();`). Built in dev\hwyscurve\inst (sc3dev build -Mods sc3netmod).
- `re/tools/netmod/hwsc_build.py` (art / lanes / check / manifest / preview) and package
  `re/tools/netmod/examples/highway_scurve` (manifest, 46 lane specs, README; art gitignored, rebuilt by the script).
- Ids: pieces 28200..28253, lit twins 28300..28353, curve shapes 28400..28495 (grant 28200..28263 / 28300..28363 /
  28400..28599).
- Installed: dev\hwyscurve\tree (stage\src ledger + packs copied in first, cartrees' recipe) and MAIN\stage\src:
  `netpack install re/tools/netmod/examples/highway_scurve --tree MAIN\stage\src` (from the worktree), exit 0. Ledger
  packs 18 -> 19 (+highway_scurve), files 97 -> 101 (new Apps/Res/Sprites/4E3D0030..0033_netpack.DAT), 36 overlay
  files rewritten, tables/highway_scurve.txt (216 lines, 54 `hwsc`), packs/highway_scurve (manifest, README, 46 lane
  specs, art/ 108 folders). Ledger before the install: this session's scratchpad `stage_src_ledger_before.json`.
  The stage's sc3netmod.dll must be rebuilt from the merged source: an older DLL ignores the `hwsc` lines (pieces
  declared, never placed, harmless).

## proven game-side vs static only
Game-side (verify/hwyscurve/RESULTS.md section 3): owner layout + overlap 3 built on load, S3 and Z4 along z built
on edit passes (lit twins), 8/8 router walks, animated cars through S2 + Z4 both ways in a Seoul copy, save holds the
stock layout, reload keeps both. Static only: sloped ground / ramps refused, `SC3NETMOD_HWSC=0`, no-mod load.

## blocked on
Nothing.

## files owned (worktree dev\hwyscurve\wt, not committed)
- M `re/harness/src/sc3netmod.c`, M `re/harness/src/sc3netmod_rbt.c`
- new `re/harness/src/sc3netmod_hwsc.c` (re/harness is ignored: needs `git add -f`, like the other block files)
- new `re/tools/netmod/hwsc_build.py`
- new `re/tools/netmod/examples/highway_scurve/manifest.json`, `README.md`, `hwsc_282*.lanes.json` (46)
- new `verify/hwyscurve/RESULTS.md`
- not for git: `examples/highway_scurve/art/` (108 folders), `MAINerify\hwyscurve\owner_shots\*`

## game-harness need
None running.

## asks of other sessions
None.
