# RESULTS - AUDIO.DLL divide by zero past the map edge (child/audiodiv, 2026-10-27)

Verdict: cause confirmed and reproduced on LIVING-PC, on a 1024 and a 256 city. Stock AUDIO.DLL divides by the number of cells in the camera's cell
box with no zero check. With the camera past the map edge at cityzoom x3 that number is 0, and the game dies with
C0000094 at AUDIO.DLL+0xAEE8, the same address as the owner's crash. sc3overscroll now guards both helpers. Same city,
same posted-input path: guard off crashes (2 of 2 runs), guard on survives (3 of 3 runs, up to 300 s past the edge,
487 guarded calls in the longest). Back inside the map the pipes ambience plays again.

## Cause (static) [CONFIRMED @ re/ghidra_export_audio, AUDIO.DLL SHA-256 5165dd51...]

- `FUN_1000ae7a` and `FUN_1000ae06` (`__fastcall`, ecx = the ambient-sound object) take a cell box from
  `FUN_1000a3d0`: the view box `+0x9a8..+0x9a0` x `+0x9ac..+0x9a4` widened by `(6 - +0x9bc) * 6`, clamped to
  `0 .. +0x9b0/+0x9b4 - 1`. They count the cells `FUN_100097b2` accepts in `[ebp-8]` and the ones cell query vt+0x40 /
  vt+0x3c also accepts in `[ebp-4]`. They return `[ebp-4] * 100 / [ebp-8]`: `idiv dword ptr [ebp-8]` at
  `0x1000aee8` / `0x1000ae74`, no zero test.
- `FUN_100097b2` accepts a cell only if it lies inside the view box and is within Manhattan distance `+0x9b8` of the
  centre cell `+0x998/+0x99c` (plus a quadrant-dependent margin of `(6 - zoom) * 4`). `FUN_1000a459` reads the centre
  from vt+0x2c (world / 16) and the box from vt+0x28 ((world + 16) / 256). They are two separate reads.
- `FUN_10009890` (ambient update, about once a second) calls `FUN_1000ae7a` when `+0x18 == 5` and `+0x9cc == 2`, and
  `FUN_1000ae06` when `+0x9cc == 1`. Measured: `+0x9cc` is the underground view layer, 1 = Metros (subway), 2 =
  Caneria agua (water pipes). The owner's crash (`+0xAEE8`) was in the pipes view.
- The other cell-count divisions on that path already test for 0: `FUN_10009890` (`local_c`, layer 0 branch, and the
  `+0x2c` divisor), `FUN_100096be` (`local_10`), `FUN_1000a995` (`+0xa28`, the per-type counts `+0x10` and the sums
  `local_c` / `iVar7`). `FUN_1000b48b`, the sixth caller of `FUN_100097b2`, divides by no count. So only these two
  helpers needed a guard.

## Trigger (measured, read-only Frida probe `ad_probe.py`)

Not "past the edge" alone. Over 729 helper calls at zoom 1..5 (A1: 394 `FUN_1000ae06`, minimum count 1004; A2: 335
`FUN_1000ae7a`, minimum count 1 at zoom 5, 0 only on the last call, at x3), at both a back edge and a front edge, the
count reached 0 only at x3. The box clamps to the map, and the centre cell stays inside it, down to a 1-row box
(`box [475,526] x [0,0]`, r 0, count 1). The zero needs cityzoom x2/x3 (zoom past 5, the view is 1280x664 stretched to
3840x1984): the box shrinks to the smaller view, and the centre cell can fall outside it. The probe's record right
before the crash:

```
zero fn=ae7a layer 2, zoom 5, centre (543,18), box x 517..534 y 0..6, r 18, rotation 2
```

The centre is outside the box on both axes. The nearest box cell (534,6) is 21 away (r 18, margin 22, but the margin
needs the quadrant test, which fails at x = 534). So no cell qualifies, the count is 0, and the idiv faults. The
owner's log fits this: `TRUECENTER: view stores 2464x1295, visible 4224x2046` is the same smaller-view-than-screen state.

## Fix

`re/harness/src/sc3overscroll.c`, block AUDIODIV (commit bf95d14):

- When AUDIO.DLL is mapped (the watcher loop, then a 5 ms poll for up to 300 s if it was not there yet), it checks the
  14-byte tails at `+0xae6c` and `+0xaee0` against the shipped bytes (`8b45fc 5e 6bc064 99 f77df8 5b c9 c3`, both
  identical, no base relocation in either). Each tail is entered only at its first byte (the loop-head `jg`).
- Each tail becomes `jmp stub` + 2 nops. The stub does the same tail. If the count is 0, it returns 0 instead (the hit
  count is 0 then too, it only grows after the count does). `FUN_10009890` already treats 0 as "stop this sound"
  (vt+0x28), so it does what stock does when no cell is in range. Protection is not restored (project-mod-startup-races).
- Log: one line when patched, a counter line when the guard first fires, then at most one a minute while the
  counters move (`layer N calls / empty box / playing`).
- `SC3OVERSCROLL_AUDIODIV=0` leaves AUDIO.DLL stock (logged). The lateguard is unchanged: nothing runs unless
  sc3mods loads the DLL.

## Proof

Tree `Simcity_audiodiv_t` (`link_tree.py` from `Simcity_release`, configs de-linked), patched exe E5B6330C (the
10-27c `sc3mods_patch.ps1` exe), `sc3mods.dll` 10-27c, mods from `SC3MODS_DIR=re/harness/inst_ad`: the 6 other 10-27c
mods + this branch's sc3overscroll. `SC3RESIZE_WINMEM=0`, windowed, then maximized with `SetWindowPlacement` (no
focus). Input: posted clicks and sc3io scrolling only (posted keys + GetKeyState spoof, no cursor, no focus). Own pids
only. Path (`ad_run.sh`): Europolis 1024, Layers -> Subsuelo -> Caneria agua -> Aplicar, unpause, minimap jump to
the y=0 edge, zoom 5, maximize 3840x1984, rotate twice, zoom + twice (x3), push down+right past y=0, slide along the
edge.

| run | guard | city | result |
|---|---|---|---|
| A2 | off (`SC3OVERSCROLL_AUDIODIV=0`) | Europolis 1024 | **crashed** at the first push past y=0 at x3: `VEH FAULT code=0xC0000094 at AUDIO.DLL+0xAEE8`, `SC3U_stkdmp.txt` INT_DIVIDE_BY_ZERO at the same address. The probe recorded a count of 0 just before (`data/a2/`) |
| B1 | on | Europolis 1024 | **alive** through the push and a 300 s slide along the edge, then closed by WM_CLOSE. `AUDIODIV: ... layer 2 541 calls / 487 empty box / 54 playing`. 0 AUDIO faults. Inside the map before the push: 54 of 55 calls returned nonzero, so the ambient pipes sound was started (vt+0x30 path) as in stock (`data/B1/`) |
| A256 | off | Europolis (256x256) | **crashed** at the first push past the edge at x3: `C0000094 at AUDIO.DLL+0xAEE8`, stack dump INT_DIVIDE_BY_ZERO. The saved rotation was 1, so the push hit the x = 255 edge. Probe zero record: centre (242,137), box x 253..255 y 111..125, r 13. So a 256 city crashes too: the trigger is the x3 view past an edge, not map size (`data/A256/`) |
| B256 | on | Europolis (256x256) | **alive**: push, 120 s along the edge, 75 s back inside. `layer 2 306 calls / 204 empty box / 102 playing`: the empty-box count stopped at 204 once back inside, and playing went from 44 to 102 (`data/B256/`) |
| B2 | on | Europolis 1024 | **alive**: push, 60 s along the edge, 75 s back inside. `255 / 130 / 125`: empty box stopped at 130, playing went from 57 to 125 (`data/B2/`) |

The only VEH line in every run is the game's own `0xC0000096 at SC3U.exe+0x84122` probe at ~30 ms (expected, see
project-mod-startup-races).

Run A1 (guard off, zoom 1..5, window 800x600 then maximized) never hit a count of 0 and ended at 651 s with no fault
line and no stack dump, right when another session's game started (pid 18308, `dev\autosave\tree`). I count it as an
outside kill, not a result.

Defender (real-time on): `Get-MpThreatDetection` 23 before the build, 23 after the runs. The newest
detection is still 2026-10-27 08:42 (`Simcity_release\Apps\version.dll`).

## Open risks

- The probe found only the x2/x3 trigger. Other states where the centre cell leaves the box (a torn read between the
  vt+0x2c and vt+0x28 reads while the camera moves) are covered by the same guard, since it tests the count, not the
  cause.
- The guard lives in sc3overscroll. A player running cityzoom without sc3overscroll can still reach the stock divide if
  the camera can leave the map without overscroll. Not tested.
- Maximized 3840x1984 on a 250% display and x3 is a larger stretch than the owner's 2560x1351. Same mechanism, not the
  same numbers. Only the pipes view (layer 2, `FUN_1000ae7a`) was driven. The subway view (layer 1, `FUN_1000ae06`)
  has the same tail and the same stub, and its patch line is the same write, but no subway run reached a zero.
- "Playing" counts the helper's nonzero returns, which is the branch where `FUN_10009890` starts the sound (vt+0x30).
  Nobody listened to the audio.

## Files

- `re/harness/src/sc3overscroll.c` (force-added): AUDIODIV block, watcher changes, env switch.
- `verify/audiodiv/`: `ad_launch.py`, `ad_setup.py`, `ad_drive.py`, `ad_probe.py`, `ad_run.sh`, this file. Logs and grabs
  under `data/` (local).
