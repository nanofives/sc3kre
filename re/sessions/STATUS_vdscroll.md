# STATUS vdscroll (child/vdscroll from main 742fe1f, 2026-10-26)

State: **fixed** (milestone 2). Detail: `verify/vdscroll/RESULTS.md`.

Cause:
- While the camera moves the game sets the Ver datos map view's dirty byte about every 100 ms.
- VERDATOS redrew its twin each time: 30 ms on 256, 230 to 420 ms on Europolis 1024. Most redraws had 0 native pixels
  changed.
- Each redraw also made DLGSCALE resample the whole 954x990 dialog.

Fix: VDSCROLL block in sc3resize.c (`SC3RESIZE_VDSCROLL=0` off), final rule after the orchestrator's note:
- The twin is redrawn only when the native map's pixels changed. A dirty byte alone does nothing, except past the
  20 s twin age.
- With the camera still, the redraw is immediate (data refresh). While the camera moves it waits until 1 s after it
  stops.
- The dialog cache is kept over native-only rebuilds and over a twin whose runs cover the old ones.

Results:
- Europolis 1024 ABBA, same game (first build): 26 fps off, 40 fps on, 41.6 with no dialog.
- Final build, heavier load: 12.1 / 15.7 / 17.1 off against 16.4 / 16.1 / 24.8 on. 0 twin draws and 0 full resamples
  with it on.
- Europolis 256: fps equal off/on. The full resamples went from 4 to 6 per 10 s to 0.
- The remaining 256 gap is the fixed DLGSCALE copy cost plus the game's own. Owner check needed on an idle PC.

## Files to commit

Worktree `Simcity_wt_vdscroll` (branch child/vdscroll):
- `re/harness/src/sc3resize.c`. Contains:
  - VDSCROLL block;
  - `DLGSCALE>` 10 s timing line;
  - test-only DIAGARROWS (`SC3RESIZE_DIAG_ARROWS=1`, off by default; also `WM_APP+0x5D1` sets VDSCROLL in game).
- `re/analysis/HUD_SCALE.md` (new last section "Scrolling with Ver datos open")
- `re/tools/vdscroll_bench.py`, `re/tools/vdscroll_io.py` (new bench, posted input only, no Frida)

MAIN:
- `verify/vdscroll/RESULTS.md`
- `verify/vdscroll/owner_shots/*.png` (3 files)
- `verify/vdscroll/logs/*` (sc3resize / sc3perf logs and bench output of the runs cited)
- `re/sessions/STATUS_vdscroll.md` (this file)

## Notes for the orchestrator

- Test tree `Simcity_stock_vdscroll\re\harness\inst_vdscroll` holds the final build (sc3resize.dll 382,976 bytes, final rule, plus
  the other 6 mods built from 742fe1f). `Apps\version.dll` is the loader from the worktree. No game of mine is running.
- Frida crashed the game twice on this PC (inside frida-agent, during a re-attach), and `dismiss_tips.py` timed out
  attaching. That is why the bench scrolls through DIAGARROWS.
- Needs owner check: real arrow keys, edge scroll and right-drag with Ver datos open, on Europolis and Europolis 1024.
