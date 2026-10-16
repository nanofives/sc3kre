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
