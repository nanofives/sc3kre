# leak1024: rotation / zoom leak on a 1024 city, 2026-11-17c - RESULTS

Child `leak1024`, LIVING-PC, tree `dev\leak1024\tree` (linked from the 2026-11-17c stage, all mods, branch child/leak1024 = main b547c93).
City `Europolis 1024.sc3` (dense: the loaded view is full of buildings, checked on a screenshot, deleted after), client 800x600.
Tools = `verify/rotleak/` copies pointed at `dev\leak1024` (`rotmem.py` gained `--zout N`; `soak.py` waits 90 s for the unpause, the 1024 city
needs 14 P presses and 22 s). Memory read from outside (PrivateUsage, largest free block below 4 GB). Posted input only.
Arm A = shipped (SPR_IMGREF on). Arm B = `SC3PERF_SPR_IMGREF=0` (sc3perf.log: "SPR_IMGREF> off"). No stock arm (stock cannot load 1024).

## Verdict
**Superseded by the closest-zoom section: at the closest zoom B leaks 6.98 MB per rotation on 1024 (A 1.07). The statement below holds only for the far zoom the city loads at: no crash, no exhaustion in 100 paused rotations or in the 15 min soak. A is lower than B
in the soak (+64.6 MB vs +88.9 MB), and A and B are the same (0.14 vs 0.16 MB per rotation) paused.** Berlin's B arm gained 15.5 MB per rotation
and crashed at rotation 94. The decode tally below shows 1024 re-makes about 5x fewer and about 16x smaller images per rotation at 800x600.

## 100 paused rotations (`runs/*_z4.txt`, `*_wide.txt`)
CORRECTED 2026-11-17 (orchestrator, from the pictures): the 1024 city loads at a FAR zoom (tiny buildings, `shots/zoom_compare.jpg` top-left), not zoom 4. The rows
labelled "loaded" below are that far load zoom. The rows labelled "wide" (6 zoom-out clicks) were also far (not confirmed as a different step). Berlin's runs used its own load zoom,
a mid-close step (`zoom_compare.jpg` bottom-left; 8 zoom-in clicks give the closest step, bottom-right). The CLOSEST zoom on 1024 is in the section below.
| arm | zoom | private MB | MB per rotation | largest free MB |
|---|---|---|---|---|
| A shipped | far (load) | 276.3 -> 290.0 | 0.14 | 793 -> 777 |
| A shipped | far ('wide') | 276.8 -> 290.6 | 0.14 | 792 -> 776 |
| B IMGREF=0 | far (load) | 276.5 -> 292.9 | 0.16 | 800 -> 800 |
| B IMGREF=0 | far ('wide') | 276.7 -> 292.4 | 0.16 | 792 -> 792 |
All four: 0 crashes, 0 hangs, 0 VEH faults after the startup 0xC0000096 (B logs checked; A logs not copied, the runs passed). Growth is steady across the 100.

## 15 min soak, sim running (`runs/soak_A.txt`, `soak_B.txt`)
Each minute 6 rotations, 1 zoom round trip, 2 minimap jumps (rotleak's workload).
| arm | private MB min 0 -> 15 | largest free MB | VEH faults | crash |
|---|---|---|---|---|
| A shipped | 276.8 -> 341.4 (90 rotations) | 804 -> 768 | 0 | none |
| B IMGREF=0 | 276.4 -> 365.3 (90 rotations) | 808 -> 735 | 0 | none |
Both arms jump +32 MB in minute 1 (sim start). After that A grows 2-3 MB per minute, B 3-5 MB per minute.
Berlin soak for comparison (rotleak): fixed 189 -> 284, release behaviour 190 -> 1520 and crash in minute 12.

## Answers
- MB per rotation on 1024 (paused): A 0.14, B 0.16. Flat across the 100 in both.
- A's residual is not larger than Berlin's (0.62..0.72); it is smaller. No art search needed.
- Largest free block at the end: A 776 MB (paused 100), 768 MB (soak); B 792 MB / 735 MB.

## Orchestrator follow-up: positive control, proof the view turns, decode tally
All at 800x600, paused, posted input, same tools. `runs/Berlin_B20.txt`, `Berlin_A20.txt`, `Eur_B_shots.txt`, `trace_Eur_B.txt`, `trace_Ber_B.txt`.

1. **Control (`rotleak Berlin.sc3`, 20 paused rotations):** B (`IMGREF=0`) private 182.2 -> 503.4 MB, **16.06 MB per rotation**, largest free 892 -> 607 MB.
   A (shipped) 179.7 -> 198.3 MB, **0.93 MB per rotation**, largest free 910 -> 879 MB. This matches rotleak (15.4-15.5 / 0.62-0.72), so the harness does detect the leak.
2. **The view turns on 1024:** `shots/Eur_B_rot0-3_sheet.jpg` (and `Eur_B_shots_0..3.jpg`), arm B, after rotation 0, 1, 2, 3. The four frames are four different
   orientations of the same spot (the minimap compass changes each time). So the posted clicks rotate the view in the 1024 runs.
3. **Decode tally, 8 paused rotations, arm B, rot_trace.py (all mods):**
| | Europolis 1024 | Berlin |
|---|---|---|
| images re-made per rotation | about 226 (1,805 in 8) | about 1,245 (9,957 in 8) |
| decoded buffers allocated / freed | 1,805 (1.0 MB) / 0 | 9,957 (91.7 MB) / 0 |
| MB of decoded buffer per rotation | about 0.12 | about 11.5 |
| average buffer size | about 0.57 KB | about 9.4 KB |
| private MB, rotation 0 -> 8 | 279.4 -> 293.9 (one +12.6 MB step at rotation 3) | 196.4 -> 297.1 |
| PrepareImage calls per rotation | about 208,000 | about 55,000 |
| uses of a destroyed image | 0 | 0 |
Reading: in arm B nothing is freed on either city (0 freed). 1024 does not free more. It decodes about 5x fewer images per rotation and each is about 16x smaller,
so the same per-image leak adds up to about 0.12 MB per rotation of buffers against about 11.5. [UNCERTAIN] why the 1024 view re-makes so few and such small images
(more cache hits across the 4 orientations, or a far zoom) is not shown by this tally. The +12.6 MB private step at rotation 3 on 1024 is not explained either.
4. Not needed: the view did turn.
5. **Larger client (2560x1440 / 3440x1440): not run.** The rotate button position is only known for the 800x600 layout, and this harness has no calibrated layout for larger
   clients. So whether 1024 at the owner's resolution re-makes more art per rotation is open.

Revised verdict: the harness is valid (Berlin B 16.06 vs A 0.93). The leak exists on 1024 as well (0 buffers freed in B) but at 800x600 the 1024 view only re-makes about
226 small images per rotation, so it adds 0.14-0.16 MB per rotation, and no crash.

## Closest zoom on 1024 (orchestrator follow-up 2)
Zoom-in clicks (10 posted at the zoom-in button, 3 s apart) until the view is closest; `shots/zoom_compare.jpg` = Europolis load (top-left), Europolis closest (top-right),
Berlin load (bottom-left), Berlin closest (bottom-right, 8 clicks). `shots/Eur_B_zin40_start.jpg` = the 40-rotation run's frame after its 10 clicks. Whether a click past the
closest step changes the view was not tested separately (8 and 10 clicks look alike by eye). Berlin's runs above were at the mid-close load step.
`runs/Eur_B_zin40.txt`, `Eur_A_zin40.txt`, `trace_Eur_B_zin.txt`.

| arm (Europolis 1024, closest zoom, 40 paused rotations) | private MB | MB per rotation | largest free MB |
|---|---|---|---|
| B (`IMGREF=0`) | 293.9 -> 573.0 | **6.98** | 787 -> **549** |
| A (shipped) | 294.1 -> 336.9 | **1.07** | 786 -> 770 |
Both finished (no crash, within 40 rotations). A is flat per rotation by eye of the log; I did not split the 40 into phases.
At 6.98 MB per rotation B would reach the 0 MB largest-free point in roughly 110-120 rotations. [extrapolation, not measured]

Trace, arm B, closest zoom, 8 rotations: images re-made 2,713 (about 340 per rotation, 2,616 by rotation 8), decoded buffers allocated 2,525 = 48.5 MB (about 6.1 MB per rotation),
**freed 0**, calls on a destroyed image 0. At the end: 1,635 images held1 with live buffer (38.7 MB), 612 prepared (6.2 MB), 269 held>3 (3.3 MB).
| per rotation, arm B | 1024 far | 1024 closest | Berlin mid-close |
|---|---|---|---|
| images re-made | about 226 | about 340 | about 1,245 |
| decoded MB | about 0.12 | about 6.1 | about 11.5 |
| paused private MB (measured) | 0.16 | 6.98 | 16.06 |
Verdict: the leak is real on 1024 and is zoom dependent. At far zoom it is 0.16 MB per rotation, at the closest zoom 6.98 (B) against 1.07 with SPR_IMGREF on (A, -85%).
Berlin A at the same kind of 20-rotation run: 0.93.

## Open
- Why B does not leak here: not determined. Not measured: whether PrepareImage re-decodes on rotation in this city, or whether sc3bigcity changes the
  sprite path. A Frida count of decoded buffers per rotation (rot_trace.py) on this city would answer it. No code change proposed.
- The 2026-11-17 leak seen by the showcase may need the view to hold art that is not cached after a rotation; Europolis 1024 at 800x600 did not show it.
  A larger client (the owner plays at 3440x1440) was not tried.
- The wide-zoom arm was not confirmed visually.

## Files
verify/leak1024/{RESULTS.md, rotmem.py, soak.py, ab100.sh, soak2.sh, runs/*.txt, runs/*_sc3resize.log, runs/soak_A_sc3perf.log}. No game or mod code changed.
