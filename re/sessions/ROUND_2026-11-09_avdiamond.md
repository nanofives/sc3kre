# Round 2026-11-09: avenue ends at highway crossings (group D)
Orchestrator: "Avenue cars driving wrong direction". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace made from main 790a52c.

| stream | owner report | expected |
|---|---|---|
| avdiamond | 2026-11-09: cars drive against the lanes on avenues; owner chose "two-way look now (done, 790a52c), then convert more avenues" | avenues that pass under an elevated highway next to its ramps convert to one-way halves instead of staying two-way |

## Background (read first)
- `verify/avdir/RESULTS.md` (cause, step 1, census), `re/analysis/AVENUE_LANES.md` (direction rule, avlj joins,
  avlt / avxm letters, avl_band_ok), `re/harness/src/sc3netmod_avl.c` (band walk, end checks, refusal log),
  `sc3netmod_avx.c` (junction boxes), memories `project-avenue-lanes`, `project-avpaint-cornert`, `project-highway-program`.
- AVL converts a band whole or not at all. A band stays two-way when an end row is not a U-turn pair, corner or avlj
  join. Since 790a52c a two-way band draws the stock yellow centre line (AVP off, avenue_markings uninstalled in your tree).

## Your cases (owner's Big One 1024 save, `tree\Cities\BigOne_owner.sc3`, `-City BigOne_owner.sc3`)
Group D = an avenue passing UNDER an elevated highway (15098 crossing rows, 15051 deck) where diamond ramps
(15117..15146, hwt 21225..21239) feed a stock T 39 / X 43 right beside the crossing. Refused ends from the owner's log
(`avl: load: band ... stays two-way`), cell (x,z):
- (584,108)/(584,109), (584,112), (584,116): z-avenue x 584/585 crossing the highway at z 113/114, X 43 rows at 112 and
  115, T 39 at 111 / 116, a 69 rail crossing at 110.
- (598,112): z-avenue x 598/599 under the highway at 113/114, T 39 at (598,112) and (598,115).
- (600,117), (604,119): x-avenue z 117/118 under highway 11258 with ramp pieces 15136..15141 and T/X beside it.
- (605,131), (608,132), (608,134): the owner's screenshot spot: avenue jogging under the highway at 133/134 (15098), hwt
  ramp 21225..21239 at x 606..608, z-avenue x 608/609 from 135 (two-way nose 20810/20811 at 139, box at 140).
Run `py -3.12 re/tools/network_layer.py` style dumps (see verify/avdir/RESULTS.md) for the grids.

## Deliverable
1. Cause per case: which check in AVL / AVX refuses, with the log line. Then a design: which cells become which pieces
   (one-way crossing under the highway, junction box for the T/X beside it, ramp joins), how the half directions meet the
   ramps and the stock T/X lanes (AVENUE_LANES.md 2: nodes at 80 / 175, same direction, or cars vanish).
   Message the orchestrator with the design BEFORE building art.
2. Build: lanes + art + table lines, off switch `SC3NETMOD_<NAME>=0`, selfblock 0, netpack validate 0 errors,
   English and English-UK lane checks (`avlanes.check`).
3. One in-game check on the owner's save: the D bands convert (log), cars in the half's direction (hwcars_tracks +
   avl_tracks_an, box around the case), save + reload keeps it, no-mod load is stock. Pictures in
   `verify/avdiamond/owner_shots/` (do NOT git add them, they reach the public repo).

Grants: piece ids 20850..20899, shapes 25500..25999 (check both against the installed tables before use).
Do not change behaviour outside group D. Groups B/C/A/E come later.
