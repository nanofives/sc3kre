# Child protocol, 2026-10-21: owner hand-test bugs on the LAN build (highways + avenues)

You are one child of the orchestrator session titled **"SC3: owner hand-test bugs 10-21 (highways + avenues)"** (find it
with `mcp__happy__list_peers`). The owner hand-tested the LAN build of main `664a685` (= `<workspace>\Simcity_release`, published 2026-10-21) and reported 7 problems with screenshots in
`MAIN\verify\ownerbugs_1021\owner_shots\img1..img9.png`. Each child owns ONE problem group (table below). MAIN =
`<workspace>\Simcity`. LOOK at your screenshots first.

Rules otherwise as `re/sessions/CHILD_PROTOCOL_2026-10-18_highways.md` sections 1-4 (read it, and section 4's "how the
existing pieces work") and `CHILD_PROTOCOL_2026-10-19_avlanes.md` (avenue lanes, one direction per half). In short:
claude2 policy (no git add / commit: the orchestrator commits by path; launch via `cmd //c` or `pwsh -c`), never kill by
name, only your own PID, always windowed, light testing (memory `feedback-light-testing`), owner reviews pictures,
STATUS file `MAIN\re\sessions\STATUS_<name>.md`, message the orchestrator at every milestone.

## Your paths (already created)
| what | path |
|---|---|
| worktree (edit ONLY here) | `<workspace>\Simcity_wt_<name>`, branch `child/<name>` from main `664a685` |
| test tree (hard-linked copy of `Simcity_release`, INCLUDING its `mods\netmod` overlay and tables = what the owner ran) | `<workspace>\Simcity_stock_<name>` |
| instance folder | `Simcity_stock_<name>\re\harness\inst_<name>\` (`lab.sc3` = Roadless Paradise lab of the highway program, `perf.ini`, `menu_bg.bmp`) |

The instance folder has NO mod binaries yet. Build ALL of them from your worktree into it (the owner's game runs all):
```
for m in mods_launch sc3resize sc3bigcity sc3overscroll sc3simrun sc3perf sc3netmod sc3undo:
  pwsh -NoProfile -Command "$env:CL=$null; & <WT>\re\scripts\build_mod.ps1 -Mod <m> -Src <WT>\re\harness\src -Out <TREE>\re\harness\inst_<name>"
cmd //c "<TREE>\re\harness\inst_<name>\mods_launch.exe -multi -- <TREE>\re\harness\inst_<name>\<copy of lab.sc3>"
```
Never put a mod DLL in the tree's `Apps\` (a second copy crashes the game). Table / package changes: netpack install
into your tree (`--tree <TREE> --allow-tree`, link-safe), never edit a hard-linked file in place. Lab driving:
`re/tools/netmod/hw_lab.py` (`hway`, `funds NOW`), `rb_lab.py` (road / avenue drags), `nr_drive.py save`. Several
children run games at once: `-multi`, `SC3_PID` / `SC3_LAB_DIR` set, 15 s between launches.

## Streams
| stream | owner report (screenshot) | expected |
|---|---|---|
| `hwlone` | 1. "placing one highway piece should behave like the original game" (img1: a 1-cell highway shows a raised deck block with a ramp). 2. "same with a longer highway piece that's unconnected with anything else" (img2: an unconnected straight run with ramp caps at both ends) | an unconnected highway (1 cell, or a run joined to nothing) looks and behaves exactly as stock (`verify/highways/STOCK.md`; check stock in a tree WITHOUT sc3netmod first). Find which block draws it (the capped-joins / seam work on main, memory `project-highway-program` "capped joins (never extend, 1087376)"), keep what the owner did not reject (caps where a highway really ends against something, if that is what they are for), and say exactly what changes |
| `hwtee` | 3. "connecting two highways like a T should prompt for creating the T intersection and it doesn't" (img3: a stem ending on the side of a through highway, both just meet, no interchange) | the hwt T interchange (child/hwt, merged) forms for this drag. Reproduce img3's layout (stem length, which side, drag order, distance from the through highway's ends), find why the hwt rule refuses it (its log lines, `SC3NETMOD_HWT`), fix the rule or report the exact condition. "Prompt" = the owner expects the interchange to be offered/built; if stock has a prompt dialog for this, say so |
| `avrbtfix` | 4. two parallel straight avenues, one end not converting ("sometimes don't trigger, this is fine", img4); then "I add one more road below and everything disappears" (img5: the right avenue became a column of overlapping roundabout pieces) | adding a road next to / below an avenue never turns the avenue into roundabouts. Find which block (automatic roundabouts `sc3netmod_rbt*.c`, memory `project-roundabout3-auto`, or another) matched the avenue cells and why; fix the match so it refuses avenue cells. Also look at why img4's avenue ends did not convert (owner says fine, report only) |
| `avx32` | 5. "3 road avenue intersecting with 2 road avenue is not working" (img6: boulevard x avenue X: a plain grey box, the lanes and medians do not continue). 6. "asymmetrical intersection is not working for 3 lanes and 2 lanes" (img7, img8: offset / asymmetric boulevard x avenue crossings) | boulevard (3-wide, BVX / bvlanes) x avenue (2-wide, AVX / avjunc) crossings, centred and offset, build a proper junction with lanes per the avlanes rules (one direction per half, 3 lanes on the boulevard). Inventory what exists (BVX 20900..20911, AVX, avjunc / bvlanes results), what the owner's drags produced, and build the missing pieces |
| `avramp` | 7. "avenues are not connecting to the ramp of the highway" (img9: an avenue ending at a highway on-ramp's foot, not joined) | an avenue that reaches a highway ramp end joins it (the hwave transition 21600..21609 and RAMPFIRST exist: find why this drag does not use them, or what piece is missing). Lanes must follow the avlanes rule |

Ids: reuse the free ids of the program that owns the piece (hwt 21200..21259, hwcore 21100..21119, AVX free 20805..20849,
BVX/bvlanes 21900..21949, hwave 21600..21699, rbt free ranges). Before taking an id, grep every worktree on main for it
and write it in your STATUS file; two streams must never use the same id. Ask the orchestrator if you need a new range.

## Milestones
1. **Reproduce + cause** (light): the owner's case in your tree, the log lines, the code path, the exact cause. Message
   "cause found" with a 3-line summary and a frame dump (`SC3RESIZE_FRAMEDUMP`) of the reproduction.
2. **Fix**: in your worktree, one in-game check of the owner's case + its neighbours (both drag orders, the other
   rotation), save + reload, frame dumps before / after into `MAIN\verify\<name>\owner_shots\`, `verify/<name>/RESULTS.md`,
   files to commit listed in STATUS. Message "fixed".
Do not change behaviour the owner did not report unless your fix needs it; if it does, say so in the message.
