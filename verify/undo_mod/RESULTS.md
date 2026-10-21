# sc3undo: undo / redo while paused (2026-10-20)

New mod `re/harness/src/sc3undo.c`, build `re/harness/build_undo.ps1`, loaded by `mods_launch.exe` (added to its
list). Evidence for the method: `verify/undo_spike/RESULTS.md`.

## What it does

- While paused, before each tool click on the map (Demolish or a build tool), the city is saved with the
  game's own Save command into a ring in `%TEMP%\sc3undo_<pid>\`. A save identical to the newest snapshot is
  dropped.
- Undo: Ctrl+Z or the new Undo button. Redo: Ctrl+Y / Ctrl+Shift+Z or the Redo button. Undo puts the active
  tool down, then loads the previous snapshot with the game's own Load command.
- A tool action after an undo ends the redo branch. Unpausing empties the ring.
- The city's file name is put back after every snapshot and load, so the player's Save still goes to their file.
- Buttons (owner calls 2026-10-20, "smaller buttons on the bottom of the minimap", then "closer together near the
  bottom edge of the map"): the minimap's rotate arrows shrunk at load from 26x29 to 18x20 frames (the game has no
  smaller arrow art; the image button blits 1:1), side by side under the map diamond's bottom tip, minimap-local
  (60,142) and (82,142). Greyed when there is nothing to undo / redo. Tooltip "Deshacer (Ctrl+Z)" shown on hover.
  `placement=bar` keeps the first version (full size, right end of the news ticker row).
- `undo.ini` beside the DLL: `[undo] enabled=1 steps=10 keys=1 buttons=1 placement=minimap button_x=-1 button_y=-1 lang=es`.
- Run t13: start (both greyed), one Demolish drag (Undo lit), click on the small Undo button (snapshot 0 loaded,
  Undo greyed, Redo lit). Frames: `t13_tip/fd_mm_zoom.png`, `t13_tip/tip_states.png`.

## Measured (London, 256, paused; frames from sc3resize FRAMEDUMP, the monitor was asleep)

| step | ms |
|---|---:|
| snapshot before a click | 1,265 - 1,422 |
| undo, first after an action (save + load) | 1,390 + 2,360 |
| undo / redo after that (load only) | 2,343 - 2,610 |

Run t10: two Demolish drags, then Undo button, Undo button, Redo button. Each loaded the expected snapshot
(1, 0, 1), the city object was replaced each time, the button greyed/enabled state followed the ring, P
(unpause) cleared the ring and greyed both buttons. Frames: `t10/states.png` (start, after two actions, after
an undo, unpaused).

## Found and fixed while building

1. Subclass race: the game thread can call the new WndProc before `g_oldproc` is set; it killed the game
   during the city load. The old proc is now read before the swap.
2. Patching the bar vtable as soon as SIMUI mapped killed the game at ~0.4 s. Patched once the window
   exists, 4 bytes per slot.
3. Input held during the 1.3 s snapshot is posted back after the press, so the game runs frames between
   press, drag and release.
4. A save right after a load is not byte-identical to the snapshot it loaded, so hash dedupe alone made every
   undo after a redo save a new state and drop the redo branch. The city is now marked "is snapshot N" after a
   load until the next tool click.

## Not tested (owner hand test)

- Real Ctrl+Z / Ctrl+Y. Posted keys do not update `GetKeyState(VK_CONTROL)`, so the key path could not be
  driven from a script. Holding Ctrl also switches the view to its temporary query tool; check that Ctrl+Z
  then Ctrl release behaves.
- Real mouse clicks with a tool. Scripted Win32 clicks reached the mod (map hit test and snapshot worked) but
  did not make the tool act, so the tool actions in the tests were GZ engine events (`SC3UNDO_TEST=1`).
- Hover / pressed frames of the buttons, the tooltip text, and the placement against a maximized window
  (sc3resize BARKIDS / BAR800 / HUDSCALE).
- After an undo the tool is put down; the player has to pick it again.
- Bigger maps: snapshot and load time grow with the save.

Known limit carried from the spike: the SIMSERV crime and SIMECO pollution modules keep one zero cache entry
per undone action (the stock Load does the same).

## Version 2: instant undo by operation journal (default since 2026-10-20 evening)

Owner hand test of version 1: every click froze ~6 s on a live screen (1.3 s in the asleep-monitor runs) and the
clicks did not act. Owner call: "i don't need to save everything, just the change, and it has to be instant";
order zoning, networks, buildings.

How it works: a tool's Apply (vtable slot +0x48) opens a recording scope while paused. Inside it the mod logs every
change the game makes through its own primitives: SIMGEOM occupant Insert / Remove (network pieces, buildings, trees
are all occupants), SIMRCI zone cell and zone rect writes, SIMDIRT terrain vertex, water-table and block-cell writes.
Undo replays the log backwards and refunds the funds the action took (budget Deposit); Redo replays forwards and
charges again (Withdraw, refused if the money is not there). Removed occupants are kept alive (AddRef) and re-inserted
as the same objects. Before a re-insert the preview tint on the sprite is cleared (else the object stays cyan).
Tools wrapped: zone (all types + DeZone), road, highway, rail, subway, pipe, power, on-ramp, the five building plop
classes, demolish. Addresses: header of `re/harness/src/sc3undo.c`.

Check method: a save before the action, after, after undo, after redo. A paused city saves byte-identically, so
"after undo == before" and "after redo == after" are exact tests. Benign sections, ignored by the check:
the SIMSERV crime and SIMECO pollution module-global lookup caches (one entry per new building id, never cleared by
the stock Load either) and SIMSERV flammability (recomputed by the sim's scan; a re-insert stamps the real value).

| action (city) | ops | money | undo vs before | redo vs after | undo / redo time |
|---|---|---:|---|---|---|
| Residential low zone, 58 cells (Roadless Paradise) | 58 zone cells | $580 | byte-identical | byte-identical | 0 ms |
| road, 6 pieces through a tree | 6 ins, 1 rem, 1 terrain vertex | $272 | exact (benign only) | byte-identical | 0 ms |
| rail, 2 pieces | 2 ins | $250 | exact (benign only) | byte-identical | 0 ms |
| power line | 33 ins, 11 rem | $125 | exact (benign only) | byte-identical | 0 ms |
| highway | 26 ins, 2 rem, 24 zone cells | $7,650 | exact (benign only) | byte-identical | 0 ms |
| water pipe | 25 ins | $125 | exact | byte-identical | 0 ms |
| police station 3x3 | 1 ins, 9 zone cells | $500 | exact (benign only) | byte-identical | 0-15 ms |
| small park 1x1 | 1 ins, 1 zone cell | $100 | exact (benign only) | byte-identical | 0 ms |
| bulldoze (London), since 2026-10-21 | 11-45 rem + 194-222 deferred occupant swaps | $55-$335 | exact (benign only), second drag byte-identical | byte-identical | 0-16 ms |
| raise terrain, one drag (Roadless Paradise) | 20 terrain, 3 trees removed | $140 | exact (benign only) | byte-identical | 0 ms |
| lower terrain, one drag | 20 terrain | $125 | byte-identical | byte-identical | 0 ms |
| level terrain, one drag | 20 terrain | $187 | byte-identical | byte-identical | 0 ms |
| place water, one drag | 16 water-table | $600 | byte-identical | byte-identical | 0 ms |
| place tree | 1 ins | $3 | byte-identical | byte-identical | 0 ms |

Terrain tools (added 2026-10-20 night): raise, lower, water and trees commit on every mouse move while the button is
held, so for them the recording scope spans the press (button down +0x20 opens it, button up +0x28 closes it); one
drag = one undo entry. Level commits once on release. Every write they make already went through logged slots.

Not covered / open:
- Terrain levelled by a network drag on an illegal slope (network manager +0x118): since 2026-10-21 kept in the entry, no
  longer clears the history. Its terrain writes (DirtBag +0x120 FUN_1000c5d0) are all vtable calls to +0x84 and +0x88,
  both logged [CONFIRMED @ SIMDIRT 0x1000c5d0]. Runtime: not reached in 3 runs (verify/undo_leftovers/tf1-tf3, roads over
  hills raised 3, 6 and 12 times; 8 roads that applied, all exact or byte-identical). `SC3UNDO_TFIX=0` restores the barrier.
- ~~Bulldoze undo leaves SimTransit and 23-26 B of the network layer different.~~ Fixed 2026-10-21, see below.

## Bulldoze made exact (2026-10-21, verify/undo_leftovers/bd1-bd4)

Bytes per save section across before / after / undo (`re/tools/undo/secbytes.py`):

- SimTransit `029ca804`: every differing byte held its post-bulldoze value after undo. The TrafficSimulator
  (city+0xac, vtable SimTransit `0x1001a368`) zeroes its per-cell grids under a removed piece, and a re-insert does not
  put them back. Its save `0x10004c8d` names the grids: bytes at +0x60..+0x74, bits at +0x7c / +0x80.
- Network `2147c2dd` instance 1: 8-byte {cell, u32 descriptor} records. The neighbours of the removed pieces kept their
  post-bulldoze descriptors.
- Both happen after Apply returns. Inside the scope: 0 retiles and 18 of 74 traffic bytes (bd2). The retile and the
  occupant swaps it makes run from the game's deferred processing on the next frames.

Fix: the entry stays PENDING after its scope closes, until the next action or an undo / redo. Occupant Insert / Remove
calls in that window go into the same entry (194-222 per bulldoze), and the traffic grids are compared against a copy
taken at scope open (64-180 changed bytes kept per entry). Re-running the recorded retile (SIMNTWRK `+0xb0`
FUN_100151f1) instead left 2 cells with other descriptors (bd3), so retiles are logged only.

| run | after undo vs before | redo vs after |
|---|---|---|
| bd1 (stock v2) | SimTransit 74 B, network 22 B | identical |
| bd3 (traffic copy + retile re-run) | network 6 B | identical |
| bd4 (traffic copy + pending occupant log), 2 drags | exact (benign only); second drag byte-identical | identical |
| reg1, Roadless Paradise: zone, road, power, highway, pipe | zone byte-identical, others exact (benign only) | identical |
- Tool classes tested 2026-10-21, see "Tool classes" below. Still not reached: on-ramp, shoreline (marina), the
  multi-cell building class.
- Version 1 (full save / load) stays as `mode=snapshot`.
- Real keyboard and mouse input still need the owner's hand test.

## Tool classes (2026-10-21, verify/undo_leftovers/tc*, picker*)

One fresh launch per tool (Roadless Paradise, drag (480,40) -> (630,140) on open grass; the placement lands at the drag's
END point). Picker buildings: the picker dialog was opened with the palette command, the item and OK clicked with posted
clicks (they work on dialogs), then the GZ-event drag. `re/tools/undo/savecheck.py` now prints NOT APPLIED when a drag
changed nothing (earlier FAIL rows of that kind were drags on water or illegal spots).

| tool (id) | class wrapped | ops | money | undo vs before | redo vs after |
|---|---|---|---:|---|---|
| subway (0x10004201) | subway | 40 ins, 15 rem | $3,750 | exact | byte-identical |
| rail (0x10004101) | rail | 5 ins, 2 rem | $260 | exact (benign only) | byte-identical |
| subway station (0x10004202) | subway building | 2 ins, 1 zone | $500 | byte-identical | byte-identical |
| train station (0x10004102) | building | 1 ins, 4 zone | $250 | byte-identical | byte-identical |
| big park 3x3 (0x10006602) | building | 1 ins, 9 zone | $1,000 | exact (benign only) | byte-identical |
| zoo 4x4 (0x10006604) | building | 1 ins, 16 zone | $5,000 | exact (benign only) | byte-identical |
| school (0x10006402) | building | 1 ins, 9 zone | $500 | byte-identical | byte-identical |
| hospital (0x10006401) | building | 1 ins, 9 zone | $500 | exact (benign only) | byte-identical |
| power picker: wind turbine (0x10005002) | building | 1 ins, 1 zone | $250 | exact (benign only) | byte-identical |
| water picker: pumping station (0x10005009) | plumbing building | 2 ins, 1 zone | $300 | exact (benign only) | byte-identical |
| landmark picker: SF City Hall (0x10006008) | building | 1 ins, 25 zone, 2 terrain | $12 | **SC3ZoneLayer 1 B differs** | byte-identical |

Landmark residue [UNCERTAIN]: two zone-layer cells far from the 5x5 footprint (index z*192+x: (33,159) and (121,159))
hold 0x10 / 0x40 before, 0x00 / 0x59 after placing, 0x19 / 0x40 after undo. Neither was written through a logged slot,
inside the scope or in the pending window (op dump `SC3UNDO_OPLOG=1`, picker6). Missing evidence: the writer of those
two bytes (a TTD `writers` run on the zone grid during a landmark placement).

Not reached: the marina (shoreline class): 8 placements on and near the Roadless Paradise shore all previewed red. On-ramp
and the multi-cell building class: not tried (the on-ramp needs a highway end; the tool that uses the multi-cell class is
not identified). Garbage and reward pickers use the same dialog and the building class; not run.
