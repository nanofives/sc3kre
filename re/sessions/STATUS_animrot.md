# STATUS animrot (rotated animated buildings: the animated part does not turn) - DONE 2026-11-27, round 2 done

## goal
Rotated animated building (Spaceport 57E:1F52, Science Center 57E:1F6A, both 5x5) draws its image layers turned with
it, all views, all zooms, rotations 1-3. Rotation 0 stays stock. Saved buildings come out right without re-placing.

## verdict + deciding RVA
Fixed in sc3perf ANIMROT (on by default, `SC3PERF_ANIMROT=0` / perf.ini `animrot=0` = off). Stock SIMSPR bug
(no-mods control shows it). `cSC3CitySpriteInstAnim` (vtable 0x10062a5c) reads every per-rotation layer table with the
raw view rot while its base frame getter 0x1005aeab adds the state: Draw 0x10014a10 / 0x10014c28, bounds 0x1001421b,
spans 0x10014444, hit test 0x10014546, GetW/H 0x100141c7 / 0x100143f0, Prepare 0x10014695 / Unprepare 0x100148da,
Tick 0x10014df9 (seeds from cell map GetRotate at 0x10014e5d). Fix: the 10 slots + this vtable's getter slot wrapped,
rot' = (rot + state) & 3 with a per-thread mark so the getter does not add the state twice.

## built
dev\animrot\inst\sc3perf.dll (218624 bytes, round 2 build), clean build, no warnings.

## round 2 (orchestrator review: powered buildings)
- Machines are started by the game only for powered buildings in view at zoom 2+ (SIMGEOM reconcile 0x1000f630, test
  0x10010220 reads the PowerLayer). Powered test city: Spaceport / Science Center machines game-started and game-ticked,
  seeded at view + rotation; camera turn / zoom = stock stops and restarts every machine (12 stop / 14 start measured).
- Coal plants have 4 smoke child sprites per slot with unturned world offsets. Round-1 build CRASHED with a TAB-rotated
  coal plant (SIMSPR+0x14478, unprepared slot). Fixed: child state set before insertion (ViewChange's SetAnimMachine
  call 0x10015758 redirected), calls on a marked sprite are turned too (sprite manager passes the raw view, 0x1000e4ce)
  except Tick's own GetAllSpans (return 0x10014f59), StartAnimation wrapped to turn child offsets. Smoke on the chimneys.
- Pictures G_* (fix and switch-off control), soak 120 view/zoom changes with live machines: no fault.

## proven game-side vs static only
Game-side: repro (current build), fix in 4 views x zooms 2/3 on both buildings, switch-off A/B, stock no-mods control,
game-written save loads right, query click on the turned part, 96 view/zoom changes no crash, anim machine path (started
with the occupant's own call, Tick driven by hand: rocket moves in place, masks keyed on view + rotation).
Round 2: powered machines, camera turns, coal plant smoke children all measured. Other buildings with children (other power plants, ports, airports): same code path, not measured.

## blocked on
nothing

## files owned (worktree dev\animrot\wt) - to commit
- re/harness/src/sc3perf_animrot.c (NEW; under an ignored path like the other harness sources: needs `git add -f`)
- re/harness/src/sc3perf.c (include, cfg key `animrot`, watcher call, header config line)
- re/analysis/BUILDING_ROTATION.md (section 7)
- functions.csv (round 1: 16 SIMSPR rows; round 2: +10 rows SIMSPR/SIMGEOM/SIMMISC (8 named C2, 2 notes) and 1 note fix; tracker.py batch, blast radius checked each time)
- verify/animrot/RESULTS.md
Local only (ignored): verify/animrot/work/* (lab scripts, frame dumps, AnimRotSaved.sc3). Pictures:
MAIN\verify\animrot\owner_shots\ (A repro, B fix, C query, D switch off, E stock no mods, F machine ticks, G powered: fix vs switch off,
after-turn, coal plant smoke).

## game-harness need
own tree dev\animrot\tree only; all games stopped by PID.

## asks of other sessions
none. Note for the release: sc3resize (ROTPLACE) without sc3perf keeps the defect. No mods-page row (page height).

## merged (orchestrator, 2026-11-27)
Committed a8ce39c9 on child/animrot (byte-array form of the Tick call check, rebuilt and started once: installs, machines seed at view + rotation), fast-forwarded into main. Lab scripts committed under verify/animrot/work/, test saves and logs kept local there.
