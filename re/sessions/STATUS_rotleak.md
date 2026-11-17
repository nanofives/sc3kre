# STATUS rotleak (child, 2026-11-17)

## goal
Showcase report on sc3mods-2026-11-17 / LAN 2026-11-17b: every view rotation leaks 10-14 MB, and after about 100
rotations the game dies out of address space. Find the cause and fix it behind an off switch.

## verdict + deciding RVA
**FIXED** (branch child/rotleak c4308d9). This is a stock SIMSPR bug that sc3perf made about 5x faster.
- `cISC3CitySpriteImageMgr::PrepareImage` (SIMSPR 0x10012b98) keeps the image returned by `sc3spr_provider_make_bitmap`
  (0x10012d91). That image already holds the caller's reference. PrepareImage then AddRefs it again at 0x10012bf0 /
  0x10012c5e. `UnprepareImage` (0x10012cd7) releases once at 0x10012d25. So each re-made sprite image and its decoded QFS
  buffer (operator new at 0x1001dd0f) is never freed. Measured with Frida: the AddRef returned 2 on 9,831 of 9,831
  images, the last Release returned 1 on 8,610, and 0 of 9,407 buffers were freed (95.8 MB in 8 rotations).
- sc3perf SPRITES (`spr_budget` 40, sleep 1 ms) decodes about 5x more per rotation, which is why the mods leaked
  15.4 MB per rotation against 2.3 for stock.
- Fix: sc3perf block **SPR_IMGREF** jumps over those two AddRefs, so UnprepareImage's Release frees the image.
  Off switch: `SC3PERF_SPR_IMGREF=0` or perf.ini `spr_imgref=0`.

## built
- `re/harness/src/sc3perf.c`: SPR_IMGREF block (`patch_imgref`, `g_imgref`, cfg `spr_imgref`, called from `spr_watcher`).
- `re/harness/src/sc3winonly.c` (new, TEST CONTROL ONLY, never shipped): a windowed stock game. It sets GZGraphicD
  windowed byte +0x6cdac, NOPs the fullscreen re-force at +0x117d6, applies FIX16 (copied from sc3resize) and DPI v2.
- `re/scripts/build_mod.ps1`: accepts `-Mod sc3winonly`.
- `re/scripts/sc3dev.ps1`: `run -Stock` now loads only sc3winonly.dll (building it on first use) instead of SC3MODS_OFF=1.

## proven game-side vs static only
Game-side (LIVING-PC, Berlin, 800x600, posted clicks on the minimap rotate button, memory read from outside):
- 40 rotations: stock 2.32 MB per rotation. All mods 15.4. Each mod alone matches stock except sc3perf alone at 12.65.
  `SC3PERF_SPR_BUDGET=0` brings that to 2.6.
- 100 rotations: fixed 0.69 MB per rotation (179 -> 248 MB). Control `SPR_IMGREF=0` gained 15.5 MB per rotation,
  reached 0 MB largest free block at rotation 93 and CRASHED at 94 (SIMSPR+0x50E8A write NULL, +0x1DB83 read NULL).
  Stock: 2.30 MB per rotation.
- Use-after-free watch with Frida, fixed build, 8 rotations: 8,615 images destroyed, 142 image vtable methods hooked,
  an address leaves the watch when malloc / operator new returns it again: **0 calls on a destroyed image**.
- Functional checks, fixed and control: rotations, zoom, scroll, minimap jump, Ver datos map views, save to a copy +
  reload. 13 of 13 PASS each, 0 VEH faults, same pictures.
- 15 min soak, sim running, 90 rotations + 15 zoom trips + 30 jumps: fixed 189 -> 284 MB, largest free 1078 -> 831,
  0 faults. Control (`SPR_IMGREF=0`): 190 -> 1,520 MB by minute 11, largest free 15 MB, CRASH in minute 12 (same
  SIMSPR+0x50E8A / +0x1DB83 signature).

## blocked on
nothing

## files owned
worktree `dev\rotleak\wt` (branch child/rotleak, commit c4308d9): re/harness/src/sc3perf.c, re/harness/src/sc3winonly.c,
re/scripts/build_mod.ps1, re/scripts/sc3dev.ps1.
MAIN: verify/rotleak/RESULTS.md, verify/rotleak/*.py, verify/rotleak/*.sh, verify/rotleak/*.out,
verify/rotleak/runs/*.txt, re/sessions/STATUS_rotleak.md.
Do not commit: verify/rotleak/owner_shots/, verify/rotleak/shots/ (game screenshots), verify/rotleak/runs/*.log.

## game-harness need
None beyond the dev tree. All runs used the rotleak tree, posted input and the test slot.

## asks of other sessions
- Incident: before this change, `sc3dev run -Stock` (SC3MODS_OFF=1) started the stock game in exclusive fullscreen.
  On LIVING-PC it switched the display to 800x600 for about 3 minutes (11:4x), then left a topmost 3840x2160 popup
  until I killed my PID. Other children should not use the old -Stock.
- Open: the fixed build still grows 0.62..0.72 MB per rotation, steady over 100. After 12 rotations, 471..793 images
  are still held with more than 3 references after the cache released them (3.7..6.1 MB), plus about 260 destroyed
  images whose decoded buffer was not freed (3.3..3.8 MB). Holder not identified (RESULTS.md, "Residual").
