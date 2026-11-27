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

## 7. Rotated animated buildings: the image layers did not turn (child `animrot`, 2026-11-27)

Player report (Simtropolis, release sc3mods-2026-11-25/26): a Spaceport or Science Center turned with TAB shows
rectangles of another view's art, and of empty sky, on top of the turned building, in every rotation. Evidence and
pictures: `verify/animrot/RESULTS.md`. Fix: sc3perf ANIMROT (`re/harness/src/sc3perf_animrot.c`).

**It is a stock SIMSPR bug** [measured]: the same save loaded with no mods at all (`sc3dev run -Stock`, only the
windowed shim) draws the three rotated Science Centers and Spaceports with the same patches, rotation 0 clean. Stock
cities never show it because no animated-class building in them has a rotation: powered stock Europolis has 776
animated-class sprites, all with state 0 (live probe). ROTPLACE made the case reachable.

**The class** [CONFIRMED, SIMSPR static + live]. Buildings with extra image layers get `cSC3CitySpriteInstAnim`
(Linux names, `[LINUX-HINT]`; Windows vtable `0x10062a5c`, second vtable `0x10062a44` at `+0xc`, QI id `0x7101`).
Live: all 8 test buildings (Spaceport key `57E:1F52`, Science Center `57E:1F6A`, both 5x5) have that vtable, state
`+4 >> 30` = their rotation. Medical Research (3x3) and Performing Arts (2x2) use the plain class `0x10068ca8`.
- Base frame: shared getter vt+0x68 `0x1005aeab` = `((state + rot) & 3) + zoom * 4`, so the base turns (section 2).
- Layers, no anim machine (`+0x10 == 0`: unpowered, out of view or below zoom 2, see below): the attribute's RegRect vectors,
  frames `attrib + 0xc + zoom * 0x30 + rot * 0xc`, x offsets `+0x48`, y offsets `+0x84`, indexed with the RAW `rot`.
- Layers with a machine: `machine + 0x3c0 / 0x5a0 / 0x690 + zoom * 0x30 + rot * 0xc` (frames, x, y), raw `rot`;
  `+0x798` = draw the base too.

So the layers come from slot `view` at slot `view`'s offsets while the base comes from slot `view + state`. Every
method of the class that takes (zoom, rot) does the same (Windows slot, body, stack args):

| slot | body | method [LINUX-HINT] | per-rotation data read with the raw rot |
|---|---|---|---|
| 0x0c | 0x100141c7 | GetW(zoom, rot) | machine frame [zoom][rot][0] |
| 0x10 | 0x100143f0 | GetH(zoom, rot) | same |
| 0x14 | 0x10014444 | GetAllSpans(zoom, rot, rect) | machine frames + y offsets |
| 0x18 | 0x1001421b | GetAreaFromPt(zoom, rot, rect, x, y) | RegRect or machine frames + offsets (bounds union) |
| 0x30 | 0x10014546 | IsPixelOpaque(x, y, zoom, rot) | same, hit test |
| 0x34 | 0x10014695 | Prepare(zoom, rot, bool) | RegRect frames; mask bit `rot + zoom*4` in `+0x14`, machine bit in `+0x18` |
| 0x38 | 0x100148da | Unprepare(zoom, rot) | mirror of Prepare |
| 0x3c | 0x10014c28 | Draw(buf, rect, zoom, rot, clip) | RegRect or machine frames + offsets |
| 0x40 | 0x10014a10 | Draw(buf, x, y, zoom, rot, clip) | same |
| 0x44 | 0x10014df9 | Tick(dt) | machine script for `[+0x780 zoom][+0x784 rot]`, seeded at `0x10014e36..0x10014e79` from the cell map (SL::CSCM `0x1005a952`, GetZoom vt+0x34, GetRotate vt+0x44 = raw view) when `+0x780` is out of 0..4, then ViewChange `0x100155bf` |

Each body is reached only through this vtable: one `.rdata` reference each, no direct call in SIMSPR (byte scan).

**When the game runs a machine** [CONFIRMED static + measured, round 2]. `cSC3OccupantManagerAnim` (SIMGEOM) owns the
animated set. Its DoMessage `0x1000d950` gets every view message (`0xa36cf3d1`): below zoom 2 it stops all animations
(vt+0x58(1)); otherwise it calls `sc3_geom_reconcile_visible_set` `0x1000f630` with flag 1 when zoom or rotation
changed, flag 0 otherwise, and skips it while its `+5` byte is 0 (the view still moving: after a jump the set can stay
empty until the next view message, stock). The reconcile iterates the occupants in view (cap 201) through the test
`0x10010220`: AnimType (vt+0x60) != 0, and for an occupant whose `0xe0faadc7` interface reports vt+0x5c > 0 the
**PowerLayer** (city vt+0x150) value at its cell must be non-zero: unpowered buildings never animate. Up to
`DAT_100309c4` (31) are started with `cISC3Occupant::AnimStart` (vt+0x64; Spaceport / Science Center occupants live in
SIMMISC, AnimStart `0x1003553d`) and the ones leaving get AnimStop (vt+0x68 `0x100355af`); flag 1 first stops every
current one (`0x1000f6d5`). AnimStart -> sprite QI `0x7101` -> StartAnimation `0x1001531f` (second vtable +0xc,
args x, y, z, SizeInCellsX) -> attribute vt+0x94 `0x10003f2b` builds a new machine (`+0x780/+0x784 = -1`, own copies of
the per-slot scripts and child entries). The tickable's DoAnimationTick `0x1000fc30` (exe animation tick manager,
about 118 ticks/s) calls occupant vt+0x100 -> sprite Tick, which seeds the machine on its first tick. So **a camera
turn or zoom change rebuilds every live machine** (StopAnimation frees it, StartAnimation makes a new one, Tick re-seeds
from the view): measured 12 StopAnimation + 14 StartAnimation during one turn and two zooms, new machine pointers, slots
= new view + rotation. ViewChange `0x100155bf` is reached only from that first-tick seed.

Measured in the test city with power (coal plants + power lines placed by the game's own calls): the 4 Spaceports and
4 Science Centers get machines (drawbase 1, no child sprites). Coal plants get machines with **4 child sprites per slot**
(the smoke, drawbase-0 animated sprites of their own, "unaligned" sprites in the sprite manager). Their child entries
hold the same 4 world offsets in every slot (x 390/825, z 177/974 in 1/256 cell from the lot corner, y 3682), i.e. the
chimneys of the unturned plant.

**Fix** (sc3perf ANIMROT, switch `animrot=0` in perf.ini or `SC3PERF_ANIMROT=0`). The ten slots above and this
vtable's getter slot 0x68 are replaced (the other 13 vtables keep `0x1005aeab`). For state `s != 0` and rot 0..3 a
wrapper calls the original with `rot' = (rot + s) & 3`, so every table index, both prepared masks, the bounds and the
hit test use slot `rot'`; the sprite is marked in a TLS slot while the original runs, and the getter returns
`(rot & 3) + zoom * 4` for the marked sprite, which equals the shipped `((s + raw) & 3) + zoom * 4`. The argument is
turned also when the sprite is already marked, because callers outside the class bodies pass the raw view even inside a
Tick (measured: `0x1000e4ce` from the sprite manager's ChangeUnalignedSpriteInst). The one call that already carries the
turned slot, Tick's own GetAllSpans(`+0x780`, `+0x784`) at `0x10014f56`, is recognised by its return address and passed
on. Tick: same mark; when the machine's `+0x780` is out of 0..4 the wrapper does the shipped seeding with `rot'`
(`+0x780 = GetZoom`, `+0x784 = (GetRotate + s) & 3`, ViewChange with them). Child sprites: (a) ViewChange's only call
to SetAnimMachine `0x10014083` (`0x10015758`, before the child's SetLocation and insertion) goes through a stub that
copies the marked parent's state to the child, so the manager prepares the child for slot `rr` (the slot its machine
`+0x784` gets) and its draw, hit test and tick agree with it; (b) StartAnimation is wrapped and turns each child entry's
x / z offset of the new machine by `s` quarter turns about the lot centre (`SizeInCellsX * 128`; one turn:
`x' = span - z, z' = x`), once per machine, before any ViewChange. State 0 calls the shipped bodies with the same
arguments and no TLS access.

Why sc3perf, not sc3resize: it is a SIMSPR draw fix like LOTRECT / SPR_IMGREF / NULLIMG, patched from the same
SIMSPR watcher, and it is a stock bug (saves can hold rotated animated buildings without ROTPLACE). A player who runs
sc3resize without sc3perf keeps the defect. No other mod touches these slots or bodies (grep of the harness sources).

Two crashes found and fixed on the way (both NULL reads at `SIMSPR+0x14478` in GetAllSpans, an unprepared slot's empty
frame vector, only with a TAB-rotated coal plant): the first build set the children's state after ViewChange had
inserted them (prepared for `view`, ticked at `rr`); the second passed calls on a marked sprite through unchanged and
so gave the raw view from `0x1000e4ce` to a child prepared for `rr`.

Open: a mods-page row was not added: the page is height-bound (the comments at `mt_build` record that 8 more pixels put
the city checkbox under the Volver button). Other buildings with children (other power plants, airports, ports) share
the code path; only the coal plant was measured.
