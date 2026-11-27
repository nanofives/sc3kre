# animrot results (2026-11-27): rotated animated buildings draw their image layers turned

**Verdict.** Fixed, behind its own switch, on by default: sc3perf ANIMROT. A Spaceport or Science Center with rotation
1, 2 or 3 now draws whole in all four views at zooms 2 and 3, with no patches, unpowered (static layers) and powered
(game-started, game-ticked animation: the rocket moves in its ring on the turned building). Camera turns and zoom
changes rebuild the animation the way stock does and it stays in place. A TAB-rotated coal plant's smoke now comes out
of its chimneys (round 2 found and fixed that case, including a crash it exposed in the first build). Rotation 0 takes
the shipped code path.
A save written by the current release with rotated animated buildings loads and draws right with the fix, without
re-placing anything. **The defect is a stock SIMSPR bug**: the same save with no mods at all shows the same patches.
Stock cities never hit it because no animated-class building in them has a rotation; ROTPLACE made it reachable.
Switch off (`SC3PERF_ANIMROT=0`, or `animrot=0` in perf.ini `[perf]`) = the defect is back.
Mechanism with RVAs: `re/analysis/BUILDING_ROTATION.md` section 7.

## Cause (deciding RVAs)

Buildings with extra image layers use the SIMSPR sprite class `cSC3CitySpriteInstAnim` (vtable `0x10062a5c`). Its
base frame goes through the shared getter `0x1005aeab` = `((state + rot) & 3) + zoom * 4` (state = occupant rotation),
so the base turns. Its layers are read from per-rotation tables with the RAW view rotation: the attribute's RegRect
vectors (`attrib + 0xc / 0x48 / 0x84 + zoom * 0x30 + rot * 0xc`) when there is no anim machine, the machine's vectors
(`+0x3c0 / 0x5a0 / 0x690`) when there is one. Draw `0x10014a10` / `0x10014c28`, bounds `0x1001421b`, spans
`0x10014444`, hit test `0x10014546`, size `0x100141c7` / `0x100143f0`, Prepare `0x10014695` / Unprepare `0x100148da`
(mask bits keyed on the raw rot) all do it; Tick `0x10014df9` seeds the machine's own rotation from the cell map's
GetRotate at `0x10014e5d`. Result: base from slot `view + rotation`, layers from slot `view` at slot `view`'s offsets,
which is the player's picture.

## Round 2 (2026-11-27, orchestrator review): powered buildings, live machines, camera turns, child sprites

The round-1 test buildings were unpowered. Findings with power (details and RVAs: BUILDING_ROTATION.md section 7):
- **Who starts a machine** [CONFIRMED static + measured]: `cSC3OccupantManagerAnim` (SIMGEOM). On every view message
  (`0x1000d950`) it reconciles the occupants in view (`0x1000f630`): its test `0x10010220` passes only AnimType != 0
  and, for buildings with power demand, a non-zero PowerLayer value at the cell. Up to 31 get `cISC3Occupant::AnimStart`
  (SIMMISC `0x1003553d` for these buildings) -> StartAnimation `0x1001531f`; below zoom 2 everything stops. Unpowered =
  never animates, which is why round 1 saw no machine. Ticks come from the exe's animation tick manager through
  `0x1000fc30` -> occupant vt+0x100 -> sprite Tick (measured 8,852 Ticks in 30 s with the Spaceports in view, 8,340 in 4 s with the coal plants and their smoke).
- **Camera turn / zoom** [measured]: stock stops every live animation and starts it again (reconcile flag 1:
  StopAnimation from `0x1000f6d5`, StartAnimation from `0x1000fa5d`, a new machine each time, re-seeded on its first
  Tick). One turn plus two zooms: 12 stops, 14 starts, slots after = new view + rotation for every rotated building.
- **Child sprites** [measured]: Spaceport and Science Center machines have none. Coal plants have 4 per slot (smoke),
  whose world offsets are the unturned chimney positions in every slot. Switch off: a rotated coal plant puffs smoke
  over its roof or in the air beside it. Fixed (ar_start turns the offsets by the rotation about the lot centre).
- **Two crashes in the round-1 build** (SIMSPR+0x14478, NULL read in GetAllSpans), only with a TAB-rotated coal plant:
  the children got the parent's state after their insertion (prepared for the view slot, ticked at the turned slot),
  and a call on an already marked sprite was passed through unturned although the sprite manager passes the raw view
  there (`0x1000e4ce`). Fixed: the state is set inside ViewChange before insertion (SetAnimMachine call `0x10015758`
  redirected), and every call is turned except Tick's own GetAllSpans (return address `0x10014f59`). Traced with
  `work/childtrace.py` (call order, args, state and masks up to the crash).

## Fix

`re/harness/src/sc3perf_animrot.c` (new, `#include`d after LOTRECT; installed from sc3perf's SIMSPR watcher).
The ten (zoom, rot) slots and this vtable's getter slot are replaced. For a rotated sprite each wrapper passes
`rot' = (rot + state) & 3` to the shipped body (every caller, marked or not, except Tick's own GetAllSpans, whose
argument is already turned) and marks the sprite in a TLS slot for that call; the getter returns
`(rot & 3) + zoom * 4` for the marked sprite, which equals the shipped value, so the base frame does not turn twice.
Tick seeds the machine with `rot'` the way the shipped code seeds it with the view. Child sprites take the parent's
state before they are inserted (ViewChange's SetAnimMachine call `0x10015758` goes through a stub), and StartAnimation
(second vtable +0xc) turns the new machine's child world offsets by the rotation about the lot centre. Every table index, both
prepared masks, the bounds and the hit test therefore agree on one slot. State 0 calls the shipped body with the same
arguments and no TLS access. The mark is per thread and cleared in `__finally`.

Where and why: sc3perf, not sc3resize. It is a SIMSPR draw fix like LOTRECT, SPR_IMGREF and NULLIMG and is patched
from the same SIMSPR watcher, and it is a stock bug (saves can hold rotated animated buildings without ROTPLACE).
Consequence: a player who runs sc3resize (ROTPLACE) without sc3perf keeps the defect. The installer checks all 12
vtable entries, the SetAnimMachine call and Tick's GetAllSpans call bytes, the getter bytes, the Tick seeding bytes and both call targets against the shipped DLL first and
patches nothing on a mismatch. No other mod touches these slots or bodies (grep of `re/harness/src`); the `.rdata`
page is unlocked RWX and never restored (memory `project-mod-startup-races`). Each body has exactly one reference
(its vtable slot) and no direct call in SIMSPR, so the slots catch every caller.

## Runs

Tree `dev\animrot\tree`, mods from `dev\animrot\inst`, windowed 800x600, posted input and Frida game calls only,
pictures by `SC3RESIZE_FRAMEDUMP` (mods) or PrintWindow (stock control, `work/pwgrab.py`). Game PIDs 24780, 23908,
3872, 9440, 13708, 2704, 15776, all started by `sc3dev.ps1 run animrot` and stopped by PID. Scripts in
`verify/animrot/work/` (committed; the test saves and logs beside them are local): `lab.py` (rotplace lab + jobs
`anim`, `tick`, `spr`, `animtypes`), `run_place.py`, `shots.py`, `montage.py`, `animprobe.py`, `scan_saves.py`,
`pwgrab.py`, `hookanim.py`, `childtrace.py`, `power_up.py`, `strip.py`.

Orchestrator review (2026-11-27): the installer's check of Tick's own GetAllSpans call bytes was a string literal
holding raw bytes 0xFF 0x50 0x14, which made the source file non-text. It is now a byte array (`tickspans`), same
three bytes. Rebuilt and started once on `AnimRotPowered2.sc3` (PID 22588, stopped by PID): log `ANIMROT> animated
building sprites ... 11 slots + StartAnimation, ViewChange's SetAnimMachine call`, three machines `starts at zoom 2
slot 3 / 2 / 0 (view 1)` for rotations 2 / 1 / 3, no fault line. Static check of the "every caller but one" rule:
in the ten wrapped bodies plus ViewChange, PrepareAnimMachine and UnprepareAnimMachine the only calls through the
sprite's own vtable are the getter `+0x68` and Tick's single `+0x14` (grep of the SIMSPR export).

City: `AnimRot.sc3` (= rotprobe's RotProbe2, Europolis roads, no zones). Placed with the stock tool armed by key and
TAB pressed k times (ROTPLACE, current build): Spaceports at (129,121) rot 0, (123,128) rot 1, (116,115) rot 2,
(136,134) rot 3; Science Centers at (130,156/165/174/183) rot 0-3 (log `SetRotationFlag(n) 1, now n` each). The
game wrote them into its 5-minute autosave, kept as `AnimRotSaved.sc3` (scan: 8 records, rotations as placed).

| check | result | picture (`MAIN\verify\animrot\owner_shots\`) |
|---|---|---|
| 1. reproduce, current build | rotations 1-3 of both buildings show rectangles of other-view art and sky; rotation 0 clean | `A_repro_spaceport_rot0L_1R_2T_3B_z2.png`, `A_repro_science_rot0to3_z2.png` |
| live probe | all 8 are vtable `0x10062a5c`, state = rotation, anim machine `+0x10` = 0 (layers = attribute RegRects) | `work/animprobe.py` output |
| 2. fix, 4 views x zooms 2 and 3 | both groups whole in every view and zoom, no patches | `B_M_fix_sp_z2/z3.png`, `B_M_fix_sc_z2/z3.png` |
| 3. switch off (`SC3PERF_ANIMROT=0`) | log `ANIMROT> off`; patches back in every view | `D_M_off_sp_z2/z3.png`, `D_M_off_sc_z2/z3.png` |
| 4. stock control (`-Stock`, no mods) | same save: rotated Science Centers and Spaceports show the patches, rotation 0 clean = stock bug | `E_stock_nomods_science_rot0to3.png`, `E_stock_nomods_spaceport_view0/2.png` |
| 5. save written by the current build | `AnimRotSaved.sc3` (game autosave) loads with the fix and draws right (check 2 ran on it) | as check 2 |
| 6a. query tool | click on the rocket tip of the turned rotation-1 Spaceport opens its query dialog ("Base Espacial") | `C_query_click_rocket_tip_rot1.png` |
| 6b. no crash | 96 view/zoom changes over both groups, zooms 1-4, views 0-3, 182 s, plus the runs above: game alive, no VEH fault except the game's own 83 ms startup probe | `work/resize_machine.log` |
| anim machine path | the occupant's own StartAnimation (SIMGEOM `0x10024e50`) on the rotation-1 Spaceport made a machine; masks `+0x14`/`+0x18` = `0x220` at view 0 (zoom 1/2, slot 1 = view + rotation), `0x440` after view 1 (slot 2); Tick driven by hand: log `starts at zoom 2 slot 1 (view 0)`; 8 steps: the rocket rises and drops in its launch ring on the turned art, no patches | `F_machine_rot1_spaceport_8_ticks_z2_v0.png` |
| rotation 0 | rotation-0 Spaceport with the fix and with the switch off: same art (differing pixels are the blinking no-power icon and terrain dither) | `work/fd/rot0_sp_z2_v0.png` |

Round-1 note, superseded by round 2: the round-1 buildings were unpowered, so the game started no machine for them,
and the Europolis probe ran at its default zoom with nothing animated in view.

### Round 2 runs (powered)

City `AnimRotPowered2.sc3` (local): `AnimRotSaved` plus a coal plant on the east side of each Science Center
(`work/power_up.py`, building layer vt+0x38, key `57E:CF`), power lines to the 4 Spaceports
(`re/tools/pw1024_lab.py build surface 3`, 5 straight runs), and coal plants at rotations 0-3 placed with TAB at
(91,162) (97,168) (85,169) (91,174). No-power bolts gone. Game PIDs 19212, 26404, 9548, 20620 (died of the crash above),
26996, 25108, 2604 (fixed build), all started by `sc3dev.ps1 run animrot` and stopped by PID.

| check | result | picture (`owner_shots\`) |
|---|---|---|
| machines started by the game | powered: StartAnimation 10x from SIMMISC AnimStart via the reconcile, 4 Spaceport machines seeded at zoom 3 slot = view 0 + rotation; at view 1 the Science Centers' machines sit at slots 2, 3, 0 for rotations 1-3; no child sprites on either | `work/hookanim.py` output |
| fix, powered, 4 views x 3 frames, rotations 1-3 of both buildings, zoom 3 | whole in every view; the rocket moves in its ring between frames | `G_fix_powered_sp1..3_*.png`, `G_fix_powered_sc1..3_*.png` |
| control, switch off, same shots | patches back; the moving rocket floats in a patch from the wrong slot (the player's report) | `G_off_powered_*` |
| camera turn + zoom with live machines | stock rebuilds the machines (12 stop / 14 start); after the turn rotation 1 at view 1 zoom 4 matches rotation 0 at view 2 (same art slot), rocket in place | `G_fix_after_turn_*.png` |
| coal plants rotations 0-3, smoke | fix: smoke from the chimney tops on all four; switch off: rotations 1-3 puff smoke over the roof or in mid-air | `G_fix_coalplants_rot0to3_smoke.png`, `G_off_coalplants_rot0to3_smoke.png` |
| soak | 120 view / zoom changes over the Spaceports, Science Centers and coal plants, zooms 1-4, 212 s, live machines and smoke children: no fault (only the game's 83 ms startup probe) | `work/resize_powered_soak.log` |
| final build (child offsets turned only on a machine StartAnimation just created: the shipped body keeps an existing machine and returns) | 36 view / zoom changes, then the 4 coal plants: smoke on the chimney tops, no fault | `G_fix_final_build_coalplants_smoke.png` |

## Open

- No mods-page row: the page is height-bound (`mt_build` comments: 8 more pixels put the city checkbox under the
  Volver button). Switch by perf.ini `animrot=0` or env / sc3mods.ini `[env]` `SC3PERF_ANIMROT=0`.
- Other buildings with child sprites (other power plants, ports, airports) take the same path; only the coal plant was
  measured. The turn direction of the child offsets was checked on rotations 1 and 3 (2 is direction-free).
- Stock behaviour kept as is: right after a camera jump the game can leave the animated set empty until the next view
  message (its reconcile is skipped while the view moves). Not changed.
- A third animated building of another size was not placed: the two other civics tried (Medical Research 3x3,
  Performing Arts 2x2) use the plain sprite class, and a full-map scan of Europolis for animated types timed out.
- sc3resize without sc3perf keeps the defect (design choice above).
- Owner check: look at the B pictures against the A and E pictures.

Observation, not changed: `spr_watcher` in sc3perf starts only when one of spr_budget / spr_follow / spr_refcount /
spr_imgref / lot_rect / animrot is on, so `nullimg` alone would not install. Not reported by anyone; left as is.
