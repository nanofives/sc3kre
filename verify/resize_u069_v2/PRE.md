# PRE-REGISTRATION — U-069 clean downward resize (before the lease)

**Now unblocked:** the OOB AV is fixed engine-wide (all 4 clamps), so the auto-maximize no longer
crashes and preempts the test. Method: let the view settle large (auto-maximize ~2048x1081, handled),
then drive a genuine DOWNWARD resize to **1024x768** (below the desktop workarea so Windows won't clamp
it up). Census + SEH on, load zoom.

| # | reading | verdict |
|---|---|---|
| 1 | down resize runs all 9 steps, no fault, census bbox ~1024x768 (fills the smaller window), content beyond 800x600 present but NONE beyond 1024/768 | ⭐ **PASS — downward resize works and the frame shrinks correctly** |
| 2 | steps run but census bbox still ~2048 (stale large content) | **FAIL** — surfaces/extent not shrunk; report bbox |
| 3 | `FAULT CAUGHT` | **FAIL** — a shrink-specific fault; SEH names step+addr (all 4 clamps are in, so a fault here is new) |
| 4 | down resize never triggers (client didn't change) | inconclusive — report client sizes |

**Pre-registered reads:** the settled (pre-down) client size, the `extent AFTER` for the down step
(should be 1024x768, cells plausible), and the census bbox + beyond-800x600 count.
