# vdscroll: frame rate while scrolling with Ver datos open (child/vdscroll, 2026-10-26)

Owner report (MARIANO-PC, maximized 2560x1351, HUD scale Auto 2.25x, main c2276dd): "when trying to scroll the camera
while the map details menu is open fps drop substantially". The menu is Ver datos (views flyout -> Ver datos), enlarged
by DLGSCALE, with the map drawn natively by VERDATOS.

## How it was measured

- Test tree `Simcity_stock_vdscroll`, all 7 mods + version.dll built from the worktree, client 2560x1351 windowed, HUD 2.252x.
- Input posted only: sc3io PostMessage, SetWindowPos with NOZORDER|NOACTIVATE. Pictures from `SC3RESIZE_FRAMEDUMP`.
- Scrolling: the arrow handler reads `GetAsyncKeyState`, and Frida crashed the game twice on this PC (inside
  frida-agent, during a re-attach). So a test-only switch was added, `SC3RESIZE_DIAG_ARROWS=1`: GZWIND's
  `GetAsyncKeyState` import reports the arrow named by a posted `WM_APP+0x5D0` as held, and posted arrow keys drive the
  handler. The bench holds an arrow continuously and flips direction every 3 s.
- Numbers: sc3perf CSV fps (median per window), the HUDSCALE pre-present pass in ms per frame, and the 10 s lines
  `VERDATOS>`, `VDSCROLL>` and `DLGSCALE>`. The `DLGSCALE>` timing line is new.
- Bench: `re/tools/vdscroll_bench.py`.
- **This PC was shared with 2 to 9 other SC3 games from other children during every run.** A plain 1.9 MB memcpy took
  1.3 ms here (about 1 GB/s), and windows with no dialog read anywhere from 8.7 to 104 fps. Only A/B inside one game
  (ABBA windows, the block switched in game by a posted `WM_APP+0x5D1`) is a fair comparison. Single-game arms place
  the cost but their absolute fps are not comparable.

## Cause (milestone 1)

| arm, Europolis 256, sim speed 3, one game each | still | scroll | still + Ver datos | scroll + Ver datos | twin draws / 10 s scrolling |
|---|---|---|---|---|---|
| all defaults | 57.8 | 61.5 | 53.1 | 51.1 | 16 to 20 (30 ms each), 11 full dialog resamples |
| `SC3RESIZE_VERDATOS_NATIVE=0` | 72.1 | 74.6 | 61.7 | 60.2 | none (no twin) |
| `SC3RESIZE_DLGOCC=0` | 68.8 | 66.6 | 53.8 | 43.0 | as default |
| `SC3RESIZE_DLGCLASS=0` | 86.6 | 76.7 | 67.5 | 53.9 | as default |
| `SC3RESIZE_DLGSCALE=0` (dialog native) | 76.3 | 66.2 | 63.8 | 58.7 | none |
| `SC3RESIZE_HUDSCALE=0` (nothing enlarged) | 104.4 | 90.5 | 88.5 | 89.4 | none |

Stock (`SC3MODS_OFF=1`) was not measured: it has no sc3perf counter and no posted scrolling.

1. **VERDATOS redrew its twin about every 100 ms while the camera moved.**
   - The game sets the data map view's dirty byte (view+0xdc) in bursts while scrolling, and 0 to 2 times per 10 s
     with the camera still.
   - A diag of each redraw showed most with 0 native pixels changed, the rest with 9 to 185 pixels (one with 4,186), from the sim's data.
   - One twin draw costs 30 ms on a 256-cell city (texture 512) and 230 to 420 ms on Europolis 1024 (texture 1024).
   - Every new twin rebuilt the paste runs, which dropped DLGSCALE's cache, so the whole 954x990 dialog was resampled
     on the next frame.
   - With VERDATOS off, scrolling with the dialog cost the same as standing still with it (60.2 vs 61.7).
2. **DLGSCALE has a fixed cost with any enlarged 424x440 dialog**, still or moving: prep (dest snapshot for the
   restore, native copy) 1.1 to 2.7 ms plus draw (diff, full cache copy to the frame) 0.9 to 3.1 ms per frame in the
   placement arms. That is
   two to three 1.9 MB copies, at this PC's memory speed.
3. **The game's own dialog cost**: with nothing enlarged, 104 -> 88 fps still. Scrolling was 90 -> 89.
4. DLGOCC and DLGCLASS take no part: with one dialog open neither does anything.

## Fix (milestone 2): VDSCROLL block in sc3resize.c, `SC3RESIZE_VDSCROLL=0` = as before

Final rule (orchestrator 2026-10-26: gate on the native pixels, the timer only as a cap during a scroll):
- Once the twin shows the view at the current size, it is redrawn only when the native view's pixels differ from the
  ones it was drawn over. The dirty byte alone does nothing, except once the twin is older than 20 s
  (`SC3RESIZE_VDSCROLL_MAXAGE=<ms>`; covers a data change finer than one native pixel on a 1024-cell city).
- With the camera still, that redraw happens at once. This covers the monthly data refresh (logged
  `twin redraw (at once): native pixels changed`).
- While the iso view origin moved within the last 1 s (`SC3RESIZE_VDSCROLL_SETTLE=<ms>`), it waits until the camera
  stops. Meanwhile the compose's equality mask shows the resampled native pixel wherever the data changed. The map stays
  correct, and those few cells are softer until 1 s after the camera stops.
- Open, view switch, rotation and factor changes still redraw at once.
- A run rebuild caused by native pixels alone is pasted inside the box rz_hd_draw just resampled. A new twin whose runs
  cover the old ones keeps the cache. Both no longer trigger a full dialog resample.

The F runs below used the first build (redraw after 1 s with no dirty byte, no new pixels and no camera move, skipped
when the picture was unchanged). The G runs use the final rule. With the sim paused, both builds redraw nothing while
scrolling, so the 1024 numbers carry over.

### F6: Europolis 1024, sim paused, one game, ABBA 20 s windows (first build)

| window | fps | pass ms/frame | twin draws / 10 s | full dialog resamples / 10 s |
|---|---|---|---|---|
| no dialog (start) | 41.6 | 8.4 to 13.5 | | |
| VDSCROLL off (3 windows) | 26.9, 26.2, 25.9 | 18.8 to 28.4 | 2 to 3, 228 to 419 ms each | 2 to 3 |
| VDSCROLL on (3 windows) | 40.8, 40.1, 39.8 | 16.1 to 21.4 | 0 (3 to 4 settles with the picture unchanged, skipped) | 0 |
| on, camera still | 28.7 | 15.0 to 22.8 | 1 (data age past 20 s) | 0 |
| no dialog (end, after close) | 27.5 | 14.7 to 24.1 | | |

On: +50% fps over off in the same game, and the same as the first no-dialog window. The last no-dialog window read
lower (27.5), which is the shared PC: the dialog was closed by then.

### F7: Europolis 256, sim speed 3, one game, ABBA 20 s windows (first build)

| window | fps | twin draws / 10 s | full dialog resamples / 10 s | DLGSCALE prep + draw ms/frame |
|---|---|---|---|---|
| no dialog (start, end) | 69.6, 67.8 | | | |
| VDSCROLL off (3 windows) | 56.9, 49.1, 54.8 | 5 to 10, 27 to 30 ms each | 4 to 6 | 4.2 to 4.8 |
| VDSCROLL on (3 windows) | 52.5, 50.9, 54.1 | 4 to 5, all at a stop with the data changed | 0 | 3.8 to 4.6 |
| on, camera still | 60.9 | 1 | 0 | 3.3 |

- On a 256-cell city the fps medians are the same either way: a 27 ms redraw 5 to 10 times per 10 s is under 3% of
  the time.
- The remaining gap to no dialog (68 to 70 -> 51 to 55 here) is the fixed DLGSCALE copy cost (item 2) plus the game's
  own dialog cost (item 3). On this PC that copy runs at about 1 GB/s. How large it is on an idle PC is on the owner
  list below.
- With the sim running, the twin still redraws once at each stop when the data changed meanwhile. That is a 27 ms
  frame on 256 and 230 to 420 ms on 1024. With the sim paused, nothing redraws.

### G2 and G1: final build, same protocol

The load was heavier and rising during both runs. No-dialog fps went from 14.7 at the start to 62.0 at the end of G2,
and was 27.4 and 28.1 in G1. So read the A/B pairs next to each other and the counters, not the absolute fps.

| run | window | fps | twin draws / 10 s | full resamples / 10 s | VDSCROLL line |
|---|---|---|---|---|---|
| G2 1024 paused | off (A1, A2, A3) | 12.1, 15.7, 17.1 | 1 to 4, 189 to 340 ms each | 1 to 2 | |
| G2 1024 paused | on (B1, B2, B3) | 16.4, 16.1, 24.8 | 0 | 0 | 4 to 7 dirty-only draws per 10 s, no redraw |
| G2 1024 paused | on, still | 29.3 | 1 (age past 20 s, run once the camera stopped) | 0 | |
| G1 256 speed 3 | off | 23.5, 12.0, 11.4 | 2 to 4, 61 to 121 ms each | 2 to 4 | |
| G1 256 speed 3 | on | 16.9, 12.0, 13.9 | 1 to 3, each after the camera stopped with native pixels changed | 0 | |
| G1 256 speed 3 | on, still | 9.4 | 1, at once on the data change | 0 | `twin redraw (at once): native pixels changed, camera moved 16906 ms ago` |

### Pictures (`owner_shots/`)

| file | what |
|---|---|
| `01_e256_midscroll_map_off_on_zoom2x.png` | mid-scroll, map centre 2x: off (left) and on (right), both the crisp twin |
| `02_e1024_midscroll_dialog_off_on.png` | Europolis 1024 mid-scroll, whole dialog, off and on |
| `03_view_switch_scroll_close_after.png` | on: crime view while scrolling, fire coverage view while scrolling, then closed (no leftover) |

Checked with VDSCROLL on: open, view switch (crime, fire coverage: new twin each time), scroll, still, close (twin freed by
the view's Shutdown). The only VEH line in every run is the startup `0xC0000096 at SC3U.exe+0x84122`. Logs: `logs/`
(`M1_*` placement arms, `F6_*` 1024 ABBA, `F7_*` 256 ABBA, `B_*` first scroll run, `C_diag` redraw diag).

## Needs owner check

- Scroll with Ver datos open on MARIANO-PC, Europolis and Europolis 1024, with the real arrow keys, the edge scroll and
  a right-drag. Only posted arrows were used here.
- Whether the fixed per-frame cost with any enlarged dialog (item 2: two to three 1.9 MB copies) is visible on an idle
  PC. If it is, the next lever is the dest snapshot DLGSCALE takes for the restore, which every measured frame cancelled
  (`paid late 0`). Not changed here.

## Seen, not changed

- Selecting Ver datos leaves the views flyout open. The bench closes it with a second click before measuring.
- `dismiss_tips.py` (Frida) timed out attaching twice on this PC, and a later Frida attach crashed the game inside
  frida-agent.
