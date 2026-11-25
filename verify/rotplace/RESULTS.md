# rotplace results (2026-11-25): TAB turns a plopped building while placing it

**Verdict.** Done, behind its own switch, on by default. While a square plopped building is being placed, TAB turns
it 0 -> 90 -> 180 -> 270 -> 0 degrees, the cost label shows the angle as its own line, and the building is placed
turned. The rotation holds through a game-written save and a reload in a fresh game, in all four camera views. The
Mover keeps a moved building's rotation. A non-square lot ignores TAB. TAB with no building tool does nothing. Switch
off = stock. Mechanism, RVAs and the hook: `re/analysis/BUILDING_ROTATION.md` section 6.

Code: `re/harness/src/sc3resize_rotplace.c` (new), `sc3resize.c` (RELOCATE commit stub passes the occupant vector,
layer wrappers record the tool, Mover reads the rotation, key, ini and env), `sc3resize_placehints.c` (label line),
`re/harness/lang/*.txt` (key `resize.rotplace_label`; fr/de/it/nl/sv are machine translations marked for review).
Switch: `sc3resize.ini [buildings] rotate=0` or `SC3RESIZE_ROTPLACE=0`.

Why sc3resize and not sc3simrun: the placement hooks this needs are already there. RELOCATE detours the commit
`SIMGEOM 0x10007760` and wraps the 8 building-layer slots that tell a building tool's call from any other, PLACEHINTS
owns the cost label, and `rz_wndproc` owns the mod keys and the text-focus test. A second mod hooking the same commit
would have to chain on those bytes.

Choice made (brief allowed either): the rotation resets to 0 when the tool changes. It stays for a tool that stays
(parks and other non one-shot tools keep it between placements). Esc, another tool, or a one-shot tool ending after its
placement drops it.

## Runs

Tree `dev\rotplace\tree`, mods from `dev\rotplace\inst`, city `RotPlace.sc3` (= rotprobe's `RotProbe2.sc3`: Europolis
roads, 8 buildings, no zones), 800x600 windowed. Driving: posted keys and clicks only (sc3io), the stock building tool
armed by its key through building layer `vt+0x54` (`work/lab.py arm`), camera and reads by Frida game calls, pictures by
`SC3RESIZE_FRAMEDUMP`. Game PIDs 2440, 19040, 15252, 6304, 6908, all started by `sc3dev.ps1 run rotplace` and stopped
by PID. Scripts: `work/lab.py` (from lotshape's lab), `work/run_place.py` (arm, move, k x TAB, picture, click, read back).

| check | result | evidence |
|---|---|---|
| label | "$0" + new line "Giro 0 grados (TAB)", TAB re-posts it at once: "Giro 90 grados (TAB)", no mouse move needed | `mayor_rot0_label.png`, `mayor_rot1_label.png` |
| Mayor's House (10110, 2x2) at rotations 0-3 next to the road | all four placed; occupant `GetRotationFlag` read back 0, 1, 2, 3 at (125,124), (122,124), (125,129), (122,129); log `SetRotationFlag(n) 1, now n` each | `mayor_rot{0..3}_label.png` |
| four camera views | each view shows the four houses facing four different ways, and each house turns with the view | `mayor_4rot_view{0..3}.png` |
| City Hall (10120, 3x3) at rotation 1 | placed at (130,124), rotation 1 | `cityhall_rot1_label.png`, `cityhall_rot1_view0.png` |
| Mover keeps the rotation | "?" on the rotation-2 house, Mover: log `MOVE start ... rotation 2`, the move tool's label says 180 before any TAB, placed at (125,132) with rotation 2 (log `SetRotationFlag(2) ... (Mover)`), original removed, $20 charged as RELOCATE's policy | `query_dialog.png`, `mover_label.png`, `mover_placed.png` |
| save | autosave #2 (game-written, after the move): `occupant_layer.py` reads 10110 at (122,124) rot 1, (122,129) rot 3, (125,124) rot 0, (125,132) rot 2, 10120 at (130,124) rot 1. An earlier autosave of the first run also held the rotation-1 house as rot 1 | `work/lab.py occsave` |
| reload in a fresh game | new process, that save loaded: live occupants read the same five rotations, the four views draw them turned as before the save | `reload_view{0..3}.png` |
| non-square lot | importer test landmark 2x3 (38000, `make_testmodels.py --lotshape`, installed in the dev tree only): TAB logged `TAB ignored: footprint 2x3 is not square`, no rotation line, placed at rotation 0 | `nonsquare_label.png` |
| TAB with no plop tool | current tool NULL, two posted TABs: no ROTPLACE line, nothing changed | `work/resize_on.log` (local) |
| switch off | `SC3RESIZE_ROTPLACE=0`: log `ROTPLACE> off`, two TABs did nothing, no line (a $0 building shows no label, as stock), placed at rotation 0 | `off_rot2_label.png` |

Pictures: `MAIN\verify\rotplace\owner_shots\` (local, not committed).

Bug found and fixed on the way: the commit's vector holds the occupant's `0xe0faadc7` interface, not `cISC3Occupant`.
The first build called `vt+0xd0` on it, faulted inside its `__try`, and placed at rotation 0. Fixed with the game's own
QueryInterface(`0xc14f8955`). Second: two arms in a row reused the freed tool's address, so pointer + key carried the
old rotation into the new tool; fixed by dropping the rotation when the tool is no longer current and after a one-shot
placement.

## Owner hand check

- Press TAB on the real keyboard while placing the Mayor's House, and Shift+TAB (turns back). Posted keys cannot carry
  Shift, so Shift+TAB is untested.
- Look at the turned buildings: lighting follows the world axis (BUILDING_ROTATION.md risk 1), so a turned building is lit
  like stock odd-state art. The pictures show no odd shading on the four houses; the owner should judge.
- The $0 buildings (Mayor's House and other free rewards) now show a cost label ("$0" plus the line) where stock shows
  none. Keep, or show the line only after the first TAB?

## Open

- No row on the mods page (ini key and env only).
- Importer buildings with lot props: props are placed in world space and will not turn with the building (not run).
- A turned placement under sc3undo, and a turned building on a sloped site, were not run.
- The 4-piece rewards (Theme Park, Military Base, Generic University) use another tool class and slot: TAB passes, no line.
- fr/de/it/nl/sv strings are machine translations.
