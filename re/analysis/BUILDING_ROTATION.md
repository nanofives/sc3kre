# Building rotation: does an occupant's own rotation turn the drawn art? (probe `rotprobe`, 2026-11-25)

Player request: "rotatable buildings, e.g. align the front of the Mayor's House to the street." Static reading of
SIMGEOM / SIMSPR (CodeView names) plus live checks in `dev\rotprobe` (stock-sized test city, mods on, windowed, posted
input and Frida only). Pictures and scripts: `verify/rotprobe/` (`owner_shots/`). Addresses are Ghidra VAs.

## Verdict

**Yes. A building occupant with rotation 1, 2 or 3 is drawn turned, as the view-slot sprite `(view + rotation) & 3`, and
it survives save and reload.** Measured on 2x2 growables (types 0x90 and 0x92). Not measured on a Mayor's House: no
shipped city contains one (type 10110 / 0x277e), and the code path is the same for every building occupant.
What does NOT work today is turning a building that is already placed: changing the rotation of a live occupant
does not change what is on screen (section 4).

## 1. The save and load side [CONFIRMED]

- Occupant `+0x10` bits 30-31 = rotation (`re/analysis/QUERY_ID.md`), the same word as the save record.
- Offline test (`verify/rotprobe/mk_city2.py`): Europolis, 8 buildings kept (two types, four of each), rotations 0, 1,
  2, 3 written into the position word of each type's four records, all zones cleared. Loaded in game: Frida read
  `+0x10 >> 30` of the 8 live occupants = 0,1,2,3 / 0,1,2,3 as written.
- Game-written save: the autosave (`RotProbe2 (auto 5 min).sc3`) after a live change of one occupant from 0 to 1 holds
  that record with rotation 1 and the other seven unchanged (`occupant_layer.py`). So the writer takes the bit from
  the same word. Reload of an offline-edited file is the case in section 2.
- Stock saves already contain them: Europolis has 116 type-0x92 2x2 buildings with rotation 2, Farmsville 586
  buildings with rotation != 0 in 2,520.

## 2. The draw side [CONFIRMED]

- The sprite instance of each building (class vtable `0x10068ca8`, `occupant+8`) carries the state in its `+4`
  bits 30-31. Read live for the 8 occupants: state = occupant rotation in all 8 (`peek.py`: `w4` = 0x40020000 ...
  0xc0040000).
- The frame is `((state + viewRot) & 3) + zoom * 4`: SIMSPR `FUN_1005aeab` (vtable slot 0x68), reached from slot 0x14
  `FUN_1005ad34`, `FUN_100159e2` for the offset tables. A hook on `0x1005aeab` during camera moves saw states 0-3
  against view rotations 0-1 (about 313,000 calls in 45 s, `hook3.py`).
- Where the state comes from: `FUN_1001cb87` (SetSprite) and `sc3_occupant_set_orientation_index` `0x1001d23e` free
  the old sprite chain (`vt+0x138` = `FUN_1001ce6d`) and build a new one with `vt+0x134` = `FUN_1001ce12`, which calls
  the sprite's slot 0x24 with `occupant+0x10 >> 30`. So the state is read when the sprite is attached.
- Picture (`owner_shots/tight_92.png`): top row = the same type-0x92 building with rotation 0, 1, 2, 3 at view 0;
  bottom row = the rotation 0 building at views 0, 1, 2, 3. Rotation k at view 0 shows the same face, roof notch and
  lawn corner as rotation 0 at view k (rotation 2 against view 2 and rotation 3 against view 3 match closely; the
  bottom view 1 tile is framed differently). `compare_90.png` is the same for type 0x90. A first look at the busy
  city missed it: the lit wall follows the world axis (`BUILDING_ART.md` section 5), so the shaded sides barely
  change. Compare roofs and lawns.
- Only the occupant's own sprite turns. The footprint does not (the getters ignore rotation, `LOT_SHAPES.md` section 1).

## 3. Why stock growables look unturned

`BUILDING_ART.md` ("Grown buildings do not turn to their road"): the developer writes rotation 0, so 99% of saved
buildings have it. The mechanism is intact and 1% of stock buildings use it.

## 4. Live rotation of a placed occupant: does not draw [measured, cause UNCERTAIN]

On a rotation 0 building, with Frida (`live_rot.py`, `live_reins.py`; calls with `exceptions: 'propagate'`, game paused
while calling):
1. `vt+0x108(0x4000)` (90 degrees, `0x1001d293` -> `0x1001d23e`): `+0x10` goes `12c3180c` -> `52c3180c`, a new
   sprite instance (state 1) replaces the old one in `occupant+8`. Screen unchanged.
2. Then `cISC3CitySpriteManager::InsertCellAlignedSprite(occ, 1)` (`0x100192aa`, manager found by its vtable
   `0x100630e4` in memory, returned 1): screen still unchanged (`owner_shots/live_check.png`, middle tile against left;
   the right tile is a building loaded with rotation 1, turned).
The cell map keeps drawing the old sprite state. Not read: how the cell map holds the sprite, or whether a sprite
manager remove then insert (as the Mover does) refreshes it. The game did not crash.

## 5. Rotate-on-place: what it would take (the 2026-11-25 sketch; built in section 6)

**Set the rotation before the occupant is inserted.** The state is read at sprite attach, and `vt+0x10c` / `vt+0x108`
rebuild the sprite chain, so the setter must run on the new occupant before the manager's insert (not after, section 4).
- Where: the placement tool creates the occupant in `sc3_geom_create_occupant_from_key` `0x10007e64` (class ctor
  `FUN_1000a246` for plain buildings) and `sc3_geom_commit_occupants_region` `0x10007760` positions and inserts it
  (loop over occupant `vt+0xbc`, then the grid insert `0x1000df90`). The placed word has rotation 0 because nothing
  writes bits 30-31. Hook point: after creation and position, before insert, call `vt+0x10c(rotIndex)`. The ZoneLayer
  path (`PlaceBuilding` `0x10032dfc`) already takes degrees and calls `vt+0x108` (`LOT_SHAPES.md` section 8), so a
  build through that call turns without a hook; the interactive plop tool does not use it. The exact call site of
  the tool's rotation 0 was not isolated in this probe [UNCERTAIN]: the commit loop above is the candidate.
- Rotation state: a mod global 0-3 changed by a hotkey (P and 1-4 are taken by sc3resize; pick a free key) and shown
  in the placement cost label (`PLACEHINTS`). The tool highlight (`0x1000968b`) is a rectangle, no ghost sprite, so there
  is no preview to turn. A text line in the label is enough for a first version.
- Save and reload: nothing to do (sections 1 and 2). Mover (RELOCATE.md): it removes and re-places the occupant, so
  its rotation must be carried (read `vt+0xb4`, set before insert), else a moved building snaps back to 0.
- Scope: square lots only. The footprint getters ignore rotation, so a 2x3 lot cannot turn. LOTRECT draws X x Z in
  both orientations but never turned.
- Risks: (1) lighting follows the world axis, so turned buildings light like stock odd-state art. (2) Lot props from
  the importer are placed in world space and do not turn with the building. (3) Art has a front only in slot 0 of the
  model, so "front to the street" means choosing the rotation whose slot faces the street. All four slots turn
  together with the view, so the choice stays right in every camera angle. (4) The query dialog and the one-per-city
  landmark rule see only the rotation bits. (5) Growables rebuilt by the developer reset to 0.
- Effort: the plop hook and a hotkey are about one day in sc3simrun or sc3resize behind its own off switch, plus a lab
  check in all four views on Mayor's House 10110, City Hall 3x3 and one 2x2 reward. A button that rotates an already
  placed building is separate and blocked on section 4: the cell-map refresh has to be worked out (likely remove and
  insert through the sprite manager the way the Mover does).

## Reproduce

`verify/rotprobe/mk_city.py` then `mk_city2.py` (offline rotations into a test city), `shoot3.py` (camera and frame
dumps via `cam.py`, game running and unpaused), `peek.py` (sprite state of live occupants), `hook3.py` (draw hook),
`live_rot.py` / `live_reins.py` (section 4). Each needs `SC3_PID`; never attach while the game is paused.

## 6. Rotate on place: built (sc3resize ROTPLACE, child `rotplace`, 2026-11-25)

Owner request: while placing a plopped building, TAB turns it 0 -> 1 -> 2 -> 3 -> 0 and it is placed turned.
Code: `re/harness/src/sc3resize_rotplace.c` (#included after PLACEHINTS), hooks shared with RELOCATE in `sc3resize.c`.
Evidence: `verify/rotplace/RESULTS.md`.

**Where the plop tool's rotation-0 occupant is made** [CONFIRMED @ SIMGEOM, disassembly 0x10006d26..0x10006d7f]:
`sc3_geom_place_footprint_region` `0x10006ba6` (reached from the 8 building-layer Place slots, RELOCATE.md section 1),
after the site check and funds test:
1. `0x10006d45` layer `vt+0x20(key, riid 0xe0faadc7, &out)` = `sc3_buildinglayer_create_building_reskey` `0x10003731`:
   the new occupant, pushed into a local vector (`0x100089ec`). Nothing writes bits 30-31, so it is rotation 0.
2. `0x10006d6a` QueryInterface(`0xc14f8955`) of it = the `cISC3Occupant` interface (8 bytes after the vector's
   pointer, measured: vector `0x16D62E20`, manager occupant `0x16D62E28`), then `vt+0xec` SetLocation(bounds).
3. `sc3_geom_commit_occupants_region` `0x10007760(bounds, &vector, ...)`: inserts each one (layer `vt+0x58`) after
   the flora / power-line clearing.

So the hook is the commit's entry, which RELOCATE already detours (`rl_commit_stub`): it now passes the vector to
`rl_commit_pre`, and `rp_commit` runs QI `0xc14f8955` + `cISC3Occupant::SetRotationFlag` `vt+0x10c` (building
occupants: `sc3_occupant_set_orientation_index` `0x1001d23e`) before the stock insert. The RELOCATE layer-slot wrappers
(already the test for "a call made by a building tool": key pointer - 0x108 has a tool vtable) now also record the
tool, so scripts and other callers of the layer stay stock. Read back with `GetRotationFlag` `vt+0xb4`: the set value
every time. Calling `vt+0xd0` / `vt+0x10c` on the vector's own pointer (the 0xe0faadc7 interface) faults: use the QI.

**Key and state.** `rz_wndproc` -> `rp_key`: WM_KEYDOWN VK_TAB, no Ctrl / Alt, no text field focused (`rz_text_focus`),
the city view's current tool (`SIMGEOM 0x1001be16()` -> view `+0x228`) has one of the four building tool vtables
(`0x10029504`, `0x100295e4`, `0x1002968c`, `0x10029734`) and a square footprint (`tool+0x116 == tool+0x117`, size - 1).
Then rotation + 1 (Shift+TAB - 1), the key and its WM_CHAR / key-up are swallowed, and the cost label is posted again
(`ph_repost`). Anything else passes TAB on. The game binds nothing to TAB: no VK 9 row in any `Apps\Res\Hotkeys\*.IXF`
(all 7 languages read 2026-11-25). The rotation belongs to the tool object while it is the current tool: a new tool
starts at 0, and Esc, another tool or the end of a one-shot tool (`tool+0x115`) drops it (`rp_poll` on mouse messages,
keys and labels, plus a reset after a one-shot placement). That rule was needed: two arms of the Mayor's House in a row
got the same tool address, so pointer + key alone carried the old rotation into the new tool (measured).
The 4-piece rewards (Theme Park, Military Base, Generic University) use another tool class (`FUN_1000a2a9`, vtable
`0x100297a4`) and the unwrapped multi-cell slot `+0x34`: TAB passes, no line. Non-square lots (importer 2x3 etc.) pass
TAB and the commit refuses to turn an occupant whose cell rect is not square (footprint getters ignore rotation).

**Label.** PLACEHINTS' label wrapper (SIMSPR view `+0x50`) adds "Giro N grados (TAB)" / "Rotation N degrees (TAB)"
(key `resize.rotplace_label`, 7 tables) as its own line of the TIPLINES tooltip (a "|" group when 3 lines are taken).
Side effect: a $0 building (Mayor's House) now shows a label ("$0" + the line) where stock shows none.

**Mover.** The "Mover" click reads the original's `GetRotationFlag` into `g_rl_rot0`; the move tool starts there
(label and placement), TAB changes it as for any tool. Measured: rotation 2 moved, placed with rotation 2.

**Switch.** `sc3resize.ini [buildings] rotate=0` or `SC3RESIZE_ROTPLACE=0`: no key, no line, no SetRotationFlag
(log `ROTPLACE> off`). The RELOCATE hooks install while any of RELOCATE / PLOPOVER / ROTPLACE is on.
No mods-page row yet.

Open: Shift+TAB and a physical TAB press (posted keys cannot carry Shift); importer buildings with lot props (props
are placed in world space, risk 2 above); a rotated building under sc3undo; slope levelling with a turned building
(no difference expected: the footprint does not turn).
