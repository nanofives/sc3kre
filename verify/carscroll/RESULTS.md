# carscroll: RESULTS (2026-10-16)

Pre-registration `PRE.md` (62a2792) with addenda 1 (e5d0f12), 2 (a46ba95), 3, 4, 5, each committed before the arms it
covers. Raw per-second jsonl, per-arm summaries (`<arm>_sum.json`), game logs and frames are in the stock tree
`C:\Users\maria\Desktop\Proyectos\Simcity_stock_pausetrips\re\harness\inst_cs_{stock,full,n0}\`; the summaries are
copied to `data/` here. Tools: `re/tools/cs_probe.py`, `cs_run.py`, `cs_summary.py`, `cs_gif.py`.

## Answer for the owner

**Yes: with the mod, cars, trains, subway, people, boats and aircraft keep moving while the camera moves**, in
right-drag, held right button, arrow scrolling and overscroll past the map edge (edge scroll is the same code; the
test tools cannot drive it, so it is on the hand-test list). They stay on their roads, with no trails or ghost copies
in the captured frames. Pause still stops everything, also while dragging. Zoom and rotate needed no change.

With the full mod set (sc3perf, 60 fps cap) the frame rate does not change: 55-60 fps during camera moves with and
without the animation on the 1024 city and Berlin, and 17 minutes of continuous camera moves at speed 4 on the 1024
city ran at 59.9 fps with no fault. Without the frame cap (stock threading, 100-190 fps) animating costs about 1.4 ms
per scroll frame: 83-93% of today's frame rate during moves.

Moving the camera already dropped and added cars, out of sight because everything was frozen. Once the cars move,
that showed: cars appeared in the middle of the screen while scrolling. The mod now adds new cars only on the ground
the camera has just uncovered. Measured on the final build: 0 cars popping in on screen during any camera move with
stock cars (76 a minute pop in with the camera still, the stock game's own behaviour), and 9-41 a minute with route
cars as filler (68 with the camera still; the ones that do pop in are route cars starting their trip).

One thing to know with route cars on (cartrips replace): during a long back-and-forth drag the street thins out
(6-30 cars against 33-100 with the camera still), because route cars only start on trips through the new view. It
fills again after the camera stops. Today the frozen cars stay on screen during the drag instead.

## What changed (sc3simrun, `[sim] animate_while_scrolling=1`, default on, final build **5eaa8a2e**)

1. **ANIMATE.** The camera's scroll step renders each frame without running the heartbeat that moves the street
   agents: it hands the render view an animation rate of 0 (three copies of that write in SIMSPR, `0x10043de7`,
   `0x10043f60`, `0x10044003`), and the frame only runs the heartbeat when the rate is >= 0.1. The mod writes 60, the
   value the still camera uses. Zoom and rotate already reset it inside one call, nothing to change there.
2. **STRIPS.** With the agents moving, the camera's own car bookkeeping became visible. Moving the view removes the
   cars on the ground that left the sim rect (in their next tick, so today nothing is removed until the camera stops)
   and refilled the **whole** new rect, so cars appeared in the middle of the screen (K0d, arrows: 52 of 197 placements
   drawn within 3 frames). Now the refill only covers the ground the camera has just revealed.
3. **TICKSTRIP.** The stock producer tick then filled the gap at random cells of the rect, also on screen (S1: drag
   219 on-screen pop-ins a minute against 98 with the camera still). While the camera moves it now places only on the
   last revealed strip, or not at all (addendum 5).
FREEZE (pause) still wins. `animate_while_scrolling=0` is today's behaviour, byte for byte (no patch installed).
Both changes 2 and 3 are only active while animating; sc3cartrips replace mode never runs the code they touch.

## Verdict per camera-move kind

| camera move | agents during the move (A1) | frame rate, today / mod | cars added or removed on screen during the move (final build) | verdict |
|---|---|---|---|---|
| right-drag (`H`) | per frame 89-99% of idle; per second 99% with the 60 fps cap (F1r, C2) | capped 55 / 57 (C2), 60 / 60 (F1r); uncapped 152 / 126 (C1), 144 / 124 (S1e) | stock cars 0 pop-ins (idle 76), 5 removals / min (idle 45); filler 41 (idle 68); route cars thin out | **works**; uncapped frame rate below the 90% bound |
| held right button (`HB`) | per frame 94-105% | capped 58 / 56 (C2); uncapped 166 / 148 (C1) | stock cars 0 pop-ins, 49 removals / min (idle 45) | **works**; uncapped frame rate 89% |
| arrows (`AR`) | per frame 92-122% | capped 57 / 56 (C2), 60 / 60 (F1r); uncapped 145 / 135 (C1), 108 / 133 (C3, speed 4) | stock cars 0 pop-ins, 9 removals / min; filler 9 | **works** |
| overscroll past the map edge (`OS`, full set) | per second 101-108% of idle (F1r, F2) | 60 / 60 (F1r), 59 / 60 (F2) | route cars 17 pop-ins / min (idle 45), 0 removals | **works** |
| edge scroll | not measured: posted mouse moves at the edge start no scroll (K0, K1), as `verify/resize_edgescroll` found | - | - | same scroll step (`+0x1e1..+0x1e4`), **owner hand test** |
| zoom, rotate | no change needed: rate set to 0 and back to 60 inside one call, no frame between | - | stock: zoom below the birth zoom removes every car | unchanged |
| pause + drag (`PH`) | street agents frozen (FREEZE): 0 car moves, 0 removals in drive, 94-96% of ticks frozen | - | 0 | **FREEZE wins** |

## Predictions

| # | prediction | result |
|---|---|---|
| 1 | agent ticks / s during the move within 10% of idle; car cell moves within 25% | **met with the 60 fps cap** (F1r 99-106%, C2 98-99%, L2 98-103%). **Not met per second without the cap** (60-94%): scroll frames run slower than idle frames on both sides, and the ticks follow the frames; per frame (addendum 1) 83-122%. Cell moves: F1r 91-115% of idle; stock-car Berlin drag 55% (S1e 35 vs 64: cars on the strips that leave the view are removed before they cross a cell) |
| 2 | today reproduced (A0, N0) | **met**: N0 (`animate_while_scrolling=0`) 0 agent ticks in drag and arrows, log `armed=0`, STRIPS and TICKSTRIP not installed. A0 scroll frames run no agent pass in any arm; A0 arrow phases contain some non-scroll frames (gaps in the spoofed key) where the idle path runs as in stock |
| 3 | every kind covered | drag, held, arrows, overscroll: scroll frames in every counted second. **Edge scroll: fallback** (posted moves start no scroll) |
| 4 | frame rate A1 >= 90% of A0, gap <= 1.25x | **met with the cap** (C2 98-105%, gaps 0.68-1.05x; F1r 100%). Uncapped Berlin C1: arrows 93% met, held 89% and drag 83% **not met**; gaps drag 1.00x, arrows 1.48x, held 1.30x **not met**. Speed 4 (C3): arrows 123%, drag 89.9% (not met by 0.1 point), gaps <= A0 |
| 5 | camera-driven car changes not made visible | **met on the final build with stock cars (S1e) and filler (S3d)**: 0 on-screen pop-ins in context `view` in every A1 move of every arm; S1e 0 on-screen pop-ins of any kind in drag, held and arrows (idle 76 / min), removals 5 / 49 / 9 (idle 45); S3d 41 / 9 (idle 68), removals 5 / 32 (idle 48); 4,246 (S1e) and 202 (S3d) placements on revealed strips, 0 of them on screen. Earlier builds failed it and were changed (addenda 1, 2, 5). **Route cars (replace)**: S2 arrows 62 vs 40 idle (155%) and F1r drag 78 vs 45 (173%) are above the bound; those are route cars starting at a trip origin in view (cartrips' design); same-code idle A0 vs A1 in F1r reads 68 vs 45, so the noise floor is as wide as the excess |
| 6 | FREEZE wins | **met**: every P and PH phase 0 car cell moves, 0 removals in context drive, agent passes continue with 94-96% of ticks frozen |
| 7 | faults 0, games alive, soaks | **met**: 0 faults in every counted arm; L1 (17 min), L2 (17 min), L3 (11 min), L4 (9 min) alive to the end. F1's first launch died 0.2 s after start, before SIMSPR loaded and before any sc3simrun patch (its log has only `loaded`); the rerun F1r passed |

## Tables

Columns: frames per second today (A0) / with the mod (A1) during the move; agent ticks per second during the A1 move
(A1 idle in brackets), the same as % of idle per second and per frame; car cell moves per second A0 / A1 (A1 idle);
on-screen pop-ins per minute A0 / A1 (A1 idle); on-screen removals per minute A0 / A1; cars alive A0 / A1.

**S1e** (final build, stock cars, Berlin; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 144 / 124 | 54499 (63038 idle) | 86% | 91% | 0 / 35 (idle 64) | 0 / 0 (idle 76) | 0 / 5 | 149 / 93 |
| HB | 132 / 99 | 50038 (63038 idle) | 79% | 105% | 0 / 42 (idle 64) | 0 / 0 (idle 76) | 0 / 49 | 36 / 30 |
| AR | 92 / 88 | 48994 (63038 idle) | 78% | 116% | 0 / 48 (idle 64) | 3 / 0 (idle 76) | 0 / 9 | 131 / 125 |
| P | - / 176 | 117531 (63038 idle) | 186% | 139% | - / 0 (idle 64) | - / 0 (idle 76) | - / 0 | - / 111 |
| PH | - / 101 | 73964 (63038 idle) | 117% | 152% | - / 0 (idle 64) | - / 0 (idle 76) | - / 0 | - / 118 |

idle cars A0/A1 81 81 idle rem_box A1 45

**S3d** (final build, filler, Berlin; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 46 / 83 | 35078 (42387 idle) | 83% | 89% | 0 / 34 (idle 60) | 0 / 41 (idle 68) | 0 / 5 | 124 / 72 |
| AR | 51 / 55 | 28842 (42387 idle) | 68% | 111% | 0 / 54 (idle 60) | 2 / 9 (idle 68) | 0 / 32 | 118 / 116 |

idle cars A0/A1 94 86 idle rem_box A1 48

**S2** (f3d94920, route cars, Berlin (replace never reaches TICKSTRIP); on-screen rule of addendum 1; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 109 / 96 | 30545 (49352 idle) | 62% | 74% | 0 / 20 (idle 39) | 0 / 49 (idle 40) | 0 / 0 | 38 / 6 |
| HB | 119 / 83 | 33484 (49352 idle) | 68% | 94% | 0 / 46 (idle 39) | 0 / 28 (idle 40) | 0 / 12 | 23 / 57 |
| AR | 99 / 82 | 40307 (49352 idle) | 82% | 114% | 0 / 35 (idle 39) | 0 / 62 (idle 40) | 0 / 9 | 46 / 17 |
| P | - / 150 | 96683 (49352 idle) | 196% | 150% | - / 0 (idle 39) | - / 0 (idle 40) | - / 0 | - / 12 |
| PH | - / 109 | 72620 (49352 idle) | 147% | 155% | - / 0 (idle 39) | - / 0 (idle 40) | - / 0 | - / 12 |

idle cars A0/A1 27 33 idle rem_box A1 7

**F1r** (full set, Europolis 1024, route cars, 60 fps cap; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 60 / 60 | 203417 (204782 idle) | 99% | 99% | 0 / 352 (idle 386) | 0 / 78 (idle 45) | 0 / 5 | 78 / 30 |
| AR | 60 / 60 | 216131 (204782 idle) | 106% | 106% | 3 / 445 (idle 386) | 2 / 62 (idle 45) | 0 / 18 | 200 / 200 |
| OS | 60 / 60 | 207549 (204782 idle) | 101% | 101% | 7 / 358 (idle 386) | 0 / 17 (idle 45) | 0 / 0 | 57 / 10 |

idle cars A0/A1 112 100 idle rem_box A1 10

**F2** (full set, Berlin, route cars; its frame columns carry the full probe overhead (idle A0 57 vs A1 47 on the same code); faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 59 / 56 | 25041 (24353 idle) | 103% | 85% | 0 / 24 (idle 35) | 0 / 53 (idle 41) | 0 / 11 | 40 / 16 |
| AR | 59 / 41 | 28690 (24353 idle) | 118% | 134% | 0 / 37 (idle 35) | 0 / 19 (idle 41) | 0 / 19 | 33 / 36 |
| OS | 59 / 60 | 26359 (24353 idle) | 108% | 84% | 0 / 34 (idle 35) | 0 / 51 (idle 41) | 0 / 0 | 19 / 8 |

idle cars A0/A1 30 31 idle rem_box A1 16

**C1** (lite, Berlin, route cars, uncapped; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 152 / 126 | 53122 (74476 idle) | 71% | 97% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 32 / 4 |
| HB | 166 / 148 | 65018 (74476 idle) | 87% | 101% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 31 / 25 |
| AR | 145 / 135 | 53772 (74476 idle) | 72% | 92% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 22 / 7 |

idle cars A0/A1 33 20 idle rem_box A1 0

**C2** (lite, full set, Europolis 1024, route cars, 60 fps cap; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 55 / 57 | 195035 (197728 idle) | 99% | 99% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 51 / 37 |
| HB | 58 / 56 | 195627 (197728 idle) | 99% | 101% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 61 / 69 |
| AR | 57 / 56 | 193537 (197728 idle) | 98% | 100% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 44 / 52 |

idle cars A0/A1 62 59 idle rem_box A1 0

**C3** (lite, Berlin, route cars, speed 4; faults 0)

| kind | frames A0 / A1 | agent ticks / s A1 (idle) | % per s | % per frame | cell moves A0 / A1 (idle) | on-screen pop-ins / min A0 / A1 (idle) | on-screen removals / min A0 / A1 | cars A0 / A1 |
|---|---|---|---|---|---|---|---|---|
| H | 169 / 152 | 61772 (89480 idle) | 69% | 83% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 95 / 16 |
| AR | 108 / 133 | 63665 (89480 idle) | 71% | 98% | 0 / 0 (idle 0) | 0 / 0 (idle 0) | 0 / 0 | 66 / 14 |

idle cars A0/A1 74 65 idle rem_box A1 0

Lite arms record no car events (cell moves and on-screen columns read 0 there). Soaks (lite, A1 only): L1 Berlin route
cars speed 4: 18-27 fps pooled with gaps to 9 s, idle included (a slow game state; C3 on the same configuration ran
108-183 fps with A1 gaps <= A0); L2 1024 full set speed 4: 59.9 fps, longest gap 64 ms; L3 Berlin stock cars speed 4:
123-162 fps; L4 (final build) 56-79 fps. 0 faults in all four.

## Deviations

- Smokes K0, K0c-K0g, K1 before the counted arms (addendum 1); they found the three rate-write sites and the camera car
  churn, which changed the build twice before any counted arm.
- TICKSTRIP was added after S1 (addendum 2) and changed after S1c (addendum 5). S1, S3, S1b, S3b, S1c, S3c document
  the intermediate builds; the final-build arms are S1e, S3d, L4, plus every replace-mode arm, whose code path the
  change does not reach.
- The on-screen rule for placements changed after S1b (addendum 4); arms launched before it keep the earlier rule and
  are labelled. My own first looks at S1c and S1d ran while those arms were in their last phases; every table here is
  from the complete jsonl.
- `HD` and `ED` dropped (addendum 1). Edge scroll is covered only by the code path.
- F1's first launch died at start-up before any patch; F1r ran instead (same schedule, final build).
- S1d void: the monitor went to sleep and the frame loop spun at 1,200-4,600 fps (addendum 6); S1e replaced it. A
  keep-awake helper (SetThreadExecutionState) ran from 14:41 to the end of the queue.
- A few seconds per long arm showed a frame gap of exactly 2^32 us (a counter artifact); gaps >= 10 s are excluded and
  counted (`maxgap_artifacts`).
- Pictures: V1 (fast drag and arrows) and V3 (slow drag) are used. V2's "slow pan" held the mouse still, which does
  not pan (the right-drag pans by mouse movement), so its frames show a still camera. V3's later phases reached the map
  edge (sea), kept as the boat GIF.
- Not done: zoom and rotate were not measured (decode only). Speed 4, the fastest, is covered by C3 and the soaks.

## Owner material

- Pictures: `MAIN\verify\carscroll\owner_shots\` (6 GIFs, today vs mod in the same game, `captions.md`). Frames
  inspected for smears: cars stay in their lanes between consecutive frames, no trails or ghost copies in drag,
  arrows or slow drag.
- Hand-test build: `MAIN\re\harness\handtest_carscroll\` (sc3simrun.dll 5eaa8a2e = the build of S1e / S3d / L4 /
  V3, and README.txt with what to check, edge scroll included).

## Route cars during camera moves (owner decision 2026-10-16; PRE addenda 7-15)

### Answer for the owner

**Partly.** With route cars on (cartrips replace) the street now keeps its cars during ordinary camera moves:
holding the right button and a gentle back-and-forth drag keep 0.9-1.1 of the still-camera count, in Berlin's busy
centre and on the 1024 city (without the fix those moves emptied the street to 0.1-0.5). Arrow scrolling holds on the
1024 city (0.95) and in Berlin it is back to the still count right after the scroll (1.0), but during the scroll
Berlin's centre shows about half its route cars. A very fast drag that swings the view a screen width every second
still thins the street to 0.3-0.65 during the move, and it fills back over the next 10-30 s (without the fix 0-0.25).

New route cars come in from the screen edge or with the ground the camera uncovers: on-screen pop-ins during moves stay
at or under what stock cars show with the camera still (76 a minute). The pause still stops everything, no faults in any
arm or soak, route cars still follow their routes (99%) and are never density-deleted. Frame rate during moves with the
fix: 86-116% of fix off, except arrows on the 1024 city under the heavy probe (68%). Side effect: somewhat more route cars
at a still camera (Berlin centre 58 -> 72 in view), because trips are now collected a little beyond the view.

### What was decoded and changed

Where the loss came from (B0, the build before this fix, animation on): during arrows and drags the route cars fell
to 8-12 against 31 with the camera still. Each camera step deletes the cars on the ground that leaves the car area
(the view box + 2 cells), and replace mode had nothing to refill the ground the camera reveals: routes were only
collected and solved inside the old view, every route ended at the old view edge, and spawns discarded routes that
started outside the current view. Camera-edge removals ran at 1.7-2.8 a second during moves (0.05 still) against
refills of 1.3-2.7 a second from an empty route queue.

Staged build: **sc3simrun 0b903bb6** (CARMARGIN: car area = view box + 5 cells, `[sim] car_margin=5`) + **sc3cartrips
3f9a2c82** (`[cartrips] scroll_fill=1 margin=4`): trips collected and solved over the car area + 4 cells; a 256-route
history (up to 8 cars per route, 120 s); spawns enter a route at its first step inside the car area; each strip of
ground the car area takes in gets a quota at the still-camera density, filled from routes crossing it, the car
entering mid-path off screen (<= 24 a tick, never above the still-camera count); a top-up to the still-camera count
until 8 s after the camera stops; a car whose route was cut by the collection area drives on and leaves once off
screen; no density despawn for route cars, as before. Both switch off (`X0`) to the old behaviour byte for byte.
The builds tried on the way (053963fa, cb74f872, dba17e77, 268d6676, d5e98b81) and why each changed are in addenda
8-15; the last two did no better and put cars on visible ground, so the staged build is the R1c / R2d one.

### Verdict per camera move (staged build; route cars in the view box, ratio to the still-camera count; fix on vs off)

The reference is the still count at the place the move ends (addendum 11), since the game's own car target follows
the local density; the before-the-move ratio is in the tables. Bound: median 0.75-1.25, worst move >= 0.60.

| move | Berlin centre (R1c) during / after | 1024 city (R2d) during / after | fix off (R1c / R2d) | on-screen pop-ins / min (fix on, bound 76) | verdict |
|---|---|---|---|---|---|
| held right button | 1.10 / 0.97 | (not in R2d) | 1.06 / 0.90 | 5 | **holds** |
| gentle back-and-forth drag | 0.91 / 0.93 | 0.90 / 1.00 | 0.42 / 0.53, 0.14 / 0.39 | 72, 79 | **holds** (1024 pop-ins 79, at the bound) |
| arrows | 0.51 / 1.02 | 0.95 / 0.94 | 0.16 / 0.27, 0.77 / 0.65 | 67, 7 | **holds on the 1024 city; in Berlin's centre half the cars during the scroll, back after** |
| extreme drag (view swings a screen width a second) | 0.33 / 0.37 | 0.65 / 0.40 | 0.00 / 0.24, 0.01 / 0.12 | 64, 76 | **does not hold** (better than off) |
| overscroll past the map edge (R3c, Berlin, full set) | during: ~0 for both (the view shows the ground past the edge: no roads) / after the return: 0.82 (worst 0.69) | | after: 0.19 | 0 | **holds after the move**; nothing to hold during it |
| edge scroll | not drivable by the tools | | | | owner check |

Other checks: FREEZE: every pause and pause + drag phase 0 car moves, 0 spawns (R1c, R1e). Faults: 0 in every arm.
Soak: L5 (first fix build, 1024, speed 4, 15 min of moves) alive, 0 faults, 0 spawn faults, 0 lost route cars, 99.4% of
lane decisions answered from the route; L8 (staged build, 1024, speed 4, ~11 min of moves, lite probe) alive, 0 faults, 0 spawn faults, 0 lost route cars, 99.1% of lane decisions from the route, 103-115 fps. Frame rate, fix on vs off, during moves: R1c (Berlin, full probe)
86-106%; C4 (1024, lite probe, first fix build) 86-116%; R2d (1024, full probe) 68% for arrows (70 vs 103 fps; other
kinds 89-100%). Still-camera on-screen pop-ins fell with the fix (Berlin 52 -> 25 a minute) and still-camera route
cars in the view rose (Berlin centre 58 -> 72), because trips are now collected a little beyond the view.

### Tables (all route-car arms; "fix" = X1 / X0, except B0 where it is animation on / off)

**B0**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| held button | off | 0 | - (-) | - (-) | - (-) | - (-) | 0.00 | 0 | 96 |
| held button | on | 0 | - (-) | - (-) | - (-) | - (-) | 1.16 | 0 | 109 |
| extreme drag | off | 0 | - (-) | - (-) | - (-) | - (-) | 0.02 | 0 | 87 |
| extreme drag | on | 0 | - (-) | - (-) | - (-) | - (-) | 0.25 | 111 | 60 |
| arrows | off | 0 | - (-) | - (-) | - (-) | - (-) | 0.04 | 0 | 99 |
| arrows | on | 0 | - (-) | - (-) | - (-) | - (-) | 0.08 | 32 | 78 |

still camera (I phases): pop-ins / min off 59, on 40; frames off 94, on 85; faults 0

**R1**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 26 | 1.13 (0.93) | 1.20 (1.00) | - (-) | - (-) | 1.42 | 45 | 52 |
| gentle drag | on | 34 | 1.08 (0.71) | 1.16 (0.90) | - (-) | - (-) | 0.89 | 35 | 33 |
| held button | off | 66 | 0.99 (0.97) | 1.12 (0.83) | - (-) | - (-) | 1.84 | 16 | 73 |
| held button | on | 81 | 1.04 (0.93) | 1.00 (0.87) | - (-) | - (-) | 1.01 | 40 | 58 |
| extreme drag | off | 34 | 0.34 (0.06) | 0.88 (0.20) | - (-) | - (-) | 0.44 | 78 | 76 |
| extreme drag | on | 48 | 0.76 (0.34) | 0.46 (0.39) | - (-) | - (-) | 0.87 | 52 | 82 |
| arrows | off | 37 | 0.47 (0.19) | 0.28 (0.05) | - (-) | - (-) | 0.92 | 117 | 91 |
| arrows | on | 56 | 1.38 (1.02) | 1.29 (1.08) | - (-) | - (-) | 1.30 | 37 | 55 |

still camera (I phases): pop-ins / min off 47, on 41; frames off 89, on 80; faults 0

**R1b**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 59 | 0.64 (0.61) | 0.71 (0.64) | - (-) | - (-) | 0.58 | 99 | 88 |
| gentle drag | on | 86 | 0.76 (0.74) | 0.66 (0.60) | - (-) | - (-) | 0.97 | 51 | 80 |
| held button | off | 61 | 1.39 (1.39) | 1.34 (1.34) | - (-) | - (-) | 1.05 | 0 | 165 |
| extreme drag | off | 79 | 0.00 (0.00) | 0.04 (0.00) | - (-) | - (-) | 0.01 | 118 | 103 |
| extreme drag | on | 44 | 0.31 (0.15) | 0.34 (0.17) | - (-) | - (-) | 0.28 | 45 | 104 |
| arrows | off | 78 | 0.08 (0.02) | 0.18 (0.15) | - (-) | - (-) | 0.09 | 56 | 108 |
| arrows | on | 51 | 0.83 (0.44) | 0.36 (0.26) | - (-) | - (-) | 1.00 | 48 | 100 |

still camera (I phases): pop-ins / min off 33, on 19; frames off 144, on 138; faults 0

**R1c**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 72 | 0.43 (0.37) | 0.57 (0.52) | 0.42 (0.34) | 0.53 (0.52) | 0.42 | 74 | 125 |
| gentle drag | on | 104 | 0.88 (0.83) | 0.84 (0.72) | 0.91 (0.84) | 0.93 (0.80) | 0.44 | 72 | 124 |
| held button | off | 92 | 1.14 (1.06) | 1.04 (0.90) | 1.06 (1.01) | 0.90 (0.83) | 1.18 | 7 | 134 |
| held button | on | 103 | 1.13 (1.11) | 1.02 (0.99) | 1.10 (1.09) | 0.97 (0.89) | 1.14 | 5 | 142 |
| extreme drag | off | 56 | 0.00 (0.00) | 0.25 (0.16) | 0.00 (0.00) | 0.24 (0.21) | 0.00 | 90 | 109 |
| extreme drag | on | 66 | 0.28 (0.26) | 0.27 (0.18) | 0.33 (0.31) | 0.37 (0.27) | 0.59 | 64 | 94 |
| arrows | off | 68 | 0.12 (0.06) | 0.10 (0.06) | 0.16 (0.10) | 0.27 (0.10) | 0.16 | 118 | 104 |
| arrows | on | 56 | 0.69 (0.20) | 1.11 (0.59) | 0.51 (0.28) | 1.02 (0.73) | 0.78 | 67 | 107 |

still camera (I phases): pop-ins / min off 52, on 25; frames off 151, on 147; faults 0

**R1d**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 79 | 0.26 (0.11) | 0.34 (0.33) | 0.28 (0.14) | 0.51 (0.33) | 0.26 | 41 | 173 |
| gentle drag | on | 62 | 1.30 (1.18) | 0.89 (0.60) | 1.16 (0.89) | 0.65 (0.60) | 0.91 | 152 | 168 |
| held button | off | 96 | 1.16 (1.03) | 1.16 (0.90) | 1.05 (1.04) | 0.97 (0.96) | 1.02 | 0 | 157 |
| held button | on | 121 | 0.99 (0.98) | 1.01 (0.99) | 1.02 (1.00) | 1.07 (1.02) | 0.98 | 21 | 167 |
| extreme drag | off | 66 | 0.00 (0.00) | 0.02 (0.00) | 0.00 (0.00) | 0.03 (0.00) | 0.00 | 69 | 128 |
| extreme drag | on | 56 | 0.38 (0.22) | 0.54 (0.40) | 0.34 (0.17) | 0.42 (0.27) | 0.42 | 535 | 102 |
| arrows | off | 74 | 0.01 (0.01) | 0.19 (0.07) | 0.01 (0.01) | 0.38 (0.14) | 0.06 | 183 | 152 |
| arrows | on | 72 | 0.64 (0.23) | 0.81 (0.32) | 0.66 (0.32) | 0.95 (0.68) | 0.78 | 697 | 125 |

still camera (I phases): pop-ins / min off 39, on 34; frames off 194, on 186; faults 0

**R1e**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 58 | 0.16 (0.15) | 0.48 (0.40) | 0.17 (0.15) | 0.54 (0.49) | 0.09 | 118 | 212 |
| gentle drag | on | 58 | 0.86 (0.81) | 0.87 (0.50) | 0.81 (0.71) | 0.74 (0.52) | 0.85 | 34 | 202 |
| held button | off | 78 | 1.03 (1.00) | 1.06 (0.92) | 0.97 (0.92) | 0.93 (0.91) | 0.82 | 16 | 221 |
| held button | on | 100 | 1.03 (0.95) | 1.04 (0.94) | 1.00 (0.99) | 1.00 (0.94) | 0.96 | 7 | 212 |
| extreme drag | off | 67 | 0.00 (0.00) | 0.01 (0.00) | 0.00 (0.00) | 0.01 (0.00) | 0.00 | 28 | 204 |
| extreme drag | on | 50 | 0.13 (0.04) | 0.28 (0.16) | 0.19 (0.04) | 0.44 (0.37) | 0.25 | 44 | 190 |
| arrows | off | 70 | 0.07 (0.03) | 0.11 (0.04) | 0.10 (0.04) | 0.19 (0.12) | 0.04 | 58 | 196 |
| arrows | on | 92 | 0.31 (0.21) | 0.24 (0.14) | 0.41 (0.31) | 0.48 (0.40) | 0.37 | 147 | 183 |

still camera (I phases): pop-ins / min off 46, on 22; frames off 261, on 255; faults 0

**R2**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 45 | 0.32 (0.32) | 0.32 (0.32) | - (-) | - (-) | 0.57 | 53 | 42 |
| gentle drag | on | 38 | 1.16 (1.16) | 1.34 (1.34) | - (-) | - (-) | 0.00 | 2 | 0 |
| extreme drag | off | 26 | 0.33 (0.00) | 0.89 (0.59) | - (-) | - (-) | 0.92 | 33 | 69 |
| extreme drag | on | 20 | 5.29 (0.58) | 6.55 (1.34) | - (-) | - (-) | 2.10 | 159 | 62 |
| arrows | off | 28 | 1.22 (1.17) | 1.98 (1.58) | - (-) | - (-) | 1.74 | 83 | 89 |
| arrows | on | 16 | 4.43 (3.78) | 5.81 (4.61) | - (-) | - (-) | 4.41 | 96 | 75 |
| overscroll | off | 24 | 0.00 (0.00) | 0.00 (0.00) | - (-) | - (-) | 0.02 | 28 | 87 |
| overscroll | on | 16 | 0.41 (0.41) | 0.44 (0.44) | - (-) | - (-) | 0.41 | 35 | 93 |

still camera (I phases): pop-ins / min off 57, on 34; frames off 85, on 75; faults 0

**R2c**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 110 | 0.68 (0.51) | 1.00 (0.76) | - (-) | - (-) | 0.74 | 159 | 76 |
| gentle drag | on | 132 | 1.04 (0.97) | 0.81 (0.71) | - (-) | - (-) | 1.55 | 90 | 67 |
| extreme drag | off | 160 | 0.32 (0.31) | 0.28 (0.11) | - (-) | - (-) | 0.34 | 96 | 21 |
| extreme drag | on | 104 | 0.92 (0.86) | 0.96 (0.92) | - (-) | - (-) | 0.55 | 14 | 11 |
| arrows | off | 150 | 0.91 (0.89) | 1.04 (0.91) | - (-) | - (-) | 1.13 | 108 | 56 |
| arrows | on | 156 | 0.93 (0.82) | 0.89 (0.79) | - (-) | - (-) | 1.00 | 0 | 62 |
| overscroll | off | 142 | 0.00 (0.00) | 0.02 (0.00) | - (-) | - (-) | 0.00 | 23 | 56 |
| overscroll | on | 70 | 0.18 (0.12) | 0.17 (0.12) | - (-) | - (-) | 0.12 | 56 | 37 |

still camera (I phases): pop-ins / min off 39, on 6; frames off 61, on 62; faults 0

**R2d**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 78 | 0.20 (0.13) | 0.68 (0.47) | 0.14 (0.12) | 0.39 (0.36) | 0.20 | 92 | 119 |
| gentle drag | on | 137 | 1.00 (0.86) | 1.18 (1.05) | 0.90 (0.89) | 1.00 (0.87) | 1.21 | 79 | 117 |
| extreme drag | off | 100 | 0.01 (0.00) | 0.10 (0.03) | 0.01 (0.00) | 0.12 (0.04) | 0.01 | 34 | 113 |
| extreme drag | on | 124 | 0.71 (0.47) | 0.61 (0.07) | 0.65 (0.59) | 0.40 (0.11) | 0.49 | 76 | 100 |
| arrows | off | 126 | 0.90 (0.87) | 0.87 (0.80) | 0.77 (0.72) | 0.65 (0.58) | 1.06 | 50 | 103 |
| arrows | on | 157 | 0.96 (0.95) | 0.96 (0.89) | 0.95 (0.93) | 0.94 (0.86) | 1.08 | 7 | 70 |
| overscroll | off | 104 | 0.00 (0.00) | 0.00 (0.00) | 0.00 (0.00) | 0.00 (0.00) | 0.00 | 34 | 109 |
| overscroll | on | 107 | 0.03 (0.00) | 0.00 (0.00) | 0.03 (0.00) | 0.00 (0.00) | 0.03 | 51 | 108 |

still camera (I phases): pop-ins / min off 41, on 21; frames off 117, on 113; faults 0

**R2e**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 78 | 0.26 (0.22) | 0.65 (0.52) | 0.22 (0.21) | 0.49 (0.47) | 0.32 | 58 | 120 |
| gentle drag | on | 126 | 1.09 (1.07) | 1.17 (1.15) | 0.94 (0.93) | 0.88 (0.87) | 1.33 | 211 | 119 |
| extreme drag | off | 93 | 0.01 (0.00) | 0.63 (0.28) | 0.00 (0.00) | 0.45 (0.34) | 0.01 | 58 | 120 |
| extreme drag | on | 112 | 0.37 (0.28) | 0.27 (0.22) | 0.39 (0.37) | 0.33 (0.25) | 0.48 | 491 | 119 |
| arrows | off | 142 | 0.74 (0.74) | 0.87 (0.75) | 0.66 (0.62) | 0.68 (0.67) | 1.05 | 51 | 118 |
| arrows | on | 162 | 0.95 (0.93) | 1.07 (0.95) | 0.94 (0.93) | 1.05 (1.02) | 1.12 | 118 | 115 |
| overscroll | off | 108 | 0.00 (0.00) | 0.00 (0.00) | 0.00 (0.00) | 0.00 (0.00) | 0.00 | 51 | 120 |
| overscroll | on | 95 | 0.00 (0.00) | 0.01 (0.00) | 0.00 (0.00) | 0.02 (0.00) | 0.02 | 43 | 120 |

still camera (I phases): pop-ins / min off 40, on 17; frames off 120, on 120; faults 0

**R2f**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| gentle drag | off | 113 | 0.36 (0.24) | 0.43 (0.25) | 0.36 (0.27) | 0.44 (0.31) | 0.33 | 48 | 114 |
| gentle drag | on | 110 | 1.12 (0.98) | 0.52 (0.51) | 1.01 (0.85) | 0.42 (0.39) | 1.47 | 35 | 112 |
| extreme drag | off | 84 | 0.01 (0.01) | 0.14 (0.14) | 0.01 (0.01) | 0.16 (0.16) | 0.01 | 92 | 107 |
| extreme drag | on | 162 | 0.33 (0.33) | 0.25 (0.16) | 0.40 (0.40) | 0.39 (0.24) | 0.38 | 79 | 112 |
| arrows | off | 140 | 0.85 (0.77) | 0.96 (0.95) | 0.80 (0.64) | 0.85 (0.69) | 1.04 | 51 | 110 |
| arrows | on | 168 | 0.91 (0.86) | 0.90 (0.87) | 0.93 (0.88) | 0.95 (0.94) | 1.06 | 16 | 107 |

still camera (I phases): pop-ins / min off 38, on 12; frames off 119, on 119; faults 0

**R3b**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| overscroll | off | 30 | 0.09 (0.04) | 0.14 (0.06) | 0.11 (0.04) | 0.24 (0.06) | 0.19 | 0 | 120 |
| overscroll | on | 51 | 0.19 (0.10) | 0.58 (0.40) | 0.18 (0.10) | 0.53 (0.42) | 0.36 | - | - |

still camera (I phases): pop-ins / min off 12, on 14; frames off 120, on 120; faults 0


Builds per arm: B0 sc3cartrips 33ef673e (before the fix; its switch is animation); R1 / R2 053963fa; R1b / R2c dba17e77;
R1c / R2d / R3b 3f9a2c82 (staged); R1d / R2e 268d6676; R1e / R2f d5e98b81; sc3simrun 74901709 (margin 8) up to R1b /
R2c, 0b903bb6 (margin 5) from R1c on. R1 / R2 / R1b did not re-centre (R1 / R1b at the map corner); R2 / R2c / R2d / R2e
overscroll rows are a 20 s cross-map flight (addendum 13); R3b's are a 3 s one-way arrow scroll (addendum 16, drop 0).
**R3c**

| move | fix | in box before | box move / before | box after / before | box move / end-ref | box after / end-ref | drawn move / before | on-screen pop-ins / min | frames / s |
|---|---|---|---|---|---|---|---|---|---|
| overscroll | off | 26 | 0.00 (0.00) | 0.20 (0.00) | 0.00 (0.00) | 0.19 (0.00) | 0.05 | 0 | 120 |
| overscroll | on | 48 | 0.01 (0.00) | 0.56 (0.33) | 0.02 (0.00) | 0.82 (0.69) | 0.07 | 0 | 120 |

still camera (I phases): pop-ins / min off 41, on 40; frames off 120, on 120; faults 0

R3c: staged build; the approach `MV:5` and the hold `OS:4` took the view box to x 241-255, z 0-6 (the map corner and past it); analysed with drop 0; its "after" window includes the 4 s return.

