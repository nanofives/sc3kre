# sirens: RESULTS (child stream sirens, 2026-11-02)

Owner, 2026-11-02: "avoid looping sirens sounds during gameplay, lower their chances significantly".

## Verdict

In stock, sirens depend on uninitialized memory. When the shared field starts non-zero, every emergency vehicle in
view plays a looped siren, one after the other. When it starts at 0, no siren plays all session (C0). The cause is a sound-side state bug, not just the 20% roll: AUDIO's Actor object keeps one siren-state field
(+0x90) per sound id instead of per vehicle, the ctor never initializes it (live value 1145980204 = ",END", heap text),
and event 5 only updates it for the vehicle already tracked. The latch switches off only when the tracked vehicle itself
re-rolls 0, and after that the id stays silent for the rest of the session.
Full code path with RVAs: `re/analysis/SIRENS.md`.

Fix: sc3simrun SIRENS block (worktree `dev\sirens\wt`), three parts with their own switches (orchestrator 2026-11-02):

| part | what | ini `[sirens]` | env | part off |
|---|---|---|---|---|
| (a) | per-vehicle siren state (the real loop bug) | `per_vehicle=1` | `SC3SIMRUN_SIREN_PERVEH` | 0 |
| (b) | roll at both STRTSIM sites, % of stock chance | `chance_pct=20` | `SC3SIMRUN_SIREN_PCT` | 100 |
| (c) | per-id cooldown after a siren was audible | `cooldown_s=30` | `SC3SIMRUN_SIREN_COOL` | 0 |

Whole block off: `SC3SIMRUN_SIRENS=0` or `enabled=0`. Defaults are compiled in, so no ini file is needed.

## Method

`re/tools/siren_probe.py` (read-only Frida, posted keys only): launches `dev\sirens\tree` windowed with the arm's env,
loads Berlin, unpauses (P), zooms in with 2 posted numpad '+' (zoom 5), and counts for 300 s. Per-siren START is
actor +0xb4 going from 0 to above 0 in the tick 0x10013730. STOP is the fade to 0 or removal by event 4 (0x10013b5a).
`--force-visible` is a test amplifier: for the three siren actors only, it replaces the off-screen 0 from
0x1001349f with the on-screen volume of the same formula. Without it, A0 heard no siren in 5 min because no fire
engine crossed the zoom-5 view. Only fire engines (id 113) carried a siren id in Berlin. Police 114 and ambulance 130
got no events in any run. All batches ran in the test slot. Every game was killed by its own pid at the end.

## Per part: siren starts per 120 s (orchestrator's A/B; Berlin, zoom 5, `--force-visible`, final build)

| arm | parts | runs | starts | per 120 s | on vehicles whose own roll was on | rolls with a siren, all ids (STRTSIM 0x100198c0) |
|---|---|---|---|---|---|---|
| stock, latch ",END" at start | none | A1b (120 s) | 5 | 5 | 0 of 5 | not counted |
| stock, latch ",END" at start | none | B0 (300 s) | 1 (in the first 60 s) | 0.4 | 0 of 1 | 107 / 585 = 18% |
| stock, latch 0 at start | none | C0 (300 s) | 0 | 0 | n/a | 127 / 586 = 22% |
| (a) only | a | C1 (300 s) | 1 | 0.4 | 1 of 1 | 126 / 600 = 21% |
| (a)+(b)+(c) | a b c | C2 (300 s) + B1 (300 s, same parts) | 1 | 0.2 | 1 of 1 | 19 / 606 = 3.1%, 19 / 603 = 3.2% |

How to read it:
- Stock depends on what the heap left in +0x90: ",END" in A0, A1b and B0, 0 in C0 (and on the police actor in A1b).
  With ",END", the loop the owner hears: every on-screen fire engine plays, none of them had rolled a siren (A1b). It
  ends for the session the first time the tracked vehicle re-rolls 0 (B0). With 0, no siren plays at all, even for
  rolled vehicles (C0).
- (a) alone: sirens only on vehicles whose own roll was on, about 1 fire engine in 5. (b) cuts the roll to about 1
  in 30 (expected 4%, measured 3.1-3.2% over all ids). (c) spaces what is left by 30 s (B3 below, at 100% chance).
- Berlin spawns 6 to 11 fire engines per 5 min, so start counts per arm are small. The roll share is the
  larger-sample measure of (b). C2's one siren stopped when that vehicle re-rolled 0 (`fire:state0:tracked`, faded).
  The stock shared latch never does that per vehicle.

## Development runs (300 s each unless noted, Berlin, zoom 5)

| arm | env | siren starts | on vehicles that rolled a siren | audible s | gaps stop -> next start | notes |
|---|---|---|---|---|---|---|
| A0 stock, natural | none (fix not built yet) | 0 | n/a | 0 | n/a | rolls 497 / 54 / 58 (0 / 1 / 2); +0x90 = 1145980204 on all 3 actors |
| A1b stock, forced, 120 s | none (fix not built yet) | 5 | 0 of 5 (no state 5 ever sent to them) | n/a (probe missed removal stops then) | back to back, each starts after the previous vehicle despawned | the loop the owner hears |
| B0 stock, forced | SC3SIMRUN_SIRENS=0 | 1 | 0 of 1 | 7 | none | the tracked fire engine re-rolled 0 (`fire:state0:tracked`), +0x90 -> 0, silent for the remaining ~290 s |
| B1 fix default, forced | defaults (20%, 30 s) | 0 | n/a | 0 | n/a | 13 rolls, all 0 (4% chance each) |
| B2 fix 100% chance, no cooldown | SC3SIMRUN_SIREN_PCT=500, _COOL=0 | 4 | 3 of 4, the 4th placed before attach | 161 | <1 s, 15-60 s, >=60 s | per-vehicle sirens still work, each ends when its vehicle goes |
| B3 fix 100% chance, 30 s cooldown | SC3SIMRUN_SIREN_PCT=500, _COOL=30 | 7 | 7 of 7 | 82 | all 6 in the 15-60 s bin | mod counters: 489 cooldown blocks, 24 states on, 15 removals |
| B4 = B3 on the final build | same | 1 | placed before attach | 30 | none | final DLL (cooldown clock limited to siren actors); fewer fire engines this game (position events stop after 120 s); 136 cooldown blocks |

Logs and full JSON snapshots are in this folder. `run_ab.sh` ran B0 to B2, `run_abc.sh` ran C0 to C2. B1 to B4 used
the build before the three switches (same code for all parts on; B0 = whole block off).

## What this shows / does not show

- Shown game-side: the shared-latch cause (A1b, B0), both roll sites patched (`SIRENS> CHANCE ... 2 of 2 sites`),
  a siren only on vehicles whose own state is on (B2, B3), and the cooldown spacing (B3 against B2's under-1 s gap).
  No crash or fault in the fix-armed games (B1 to B4, C1, C2, 5 min each). The C-series build is the one to commit.
- The probe bins gaps by bucket. B3 shows them between 15 and 60 s, not the exact seconds.
- Not measured: the natural (non-forced) rate under the fix in a city where emergency vehicles are often on screen.
  By construction it is at most the forced rate. With the defaults, a siren needs a 4% roll and then waits 30 s
  after the last one.
- Stock reference for the owner's ear: until the latch dies, every on-screen fire engine sounds. With the fix at the
  defaults, about 1 in 25 of the fire-engine rolls gives a siren.
- No audio capture (brief: log the calls). No pictures: nothing visible changes.

## Owner check

Play a city zoomed in near a fire station for a few minutes with the release mods. Expected: an occasional siren, not
one siren after another. `simrun.ini [sirens] chance_pct` raises or lowers the rate (100 = game's chance, 0 = none).
