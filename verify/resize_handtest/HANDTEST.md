# D-004 HAND-TEST — resizable window on a real display (owner-run)

**Why this exists.** Everything about the resize mod is verified headless EXCEPT the final DirectDraw
**flip to a physical monitor** (`D-004`). The harness reconstructs frames from the raster composite
(proven full and correct at 2048x1152, both resize directions) but cannot see the real present to a
screen. This is the one step only a human at a real display can confirm. Full context:
`re/analysis/RESIZABLE_WINDOW.md`.

**What's being tested:** does the resized in-city view actually appear correct ON SCREEN — fills the
window, no black band, no garbage, no crash — when you resize/maximize the window by hand.

---

## Setup (already in place, just confirm)

- Mod binaries (built, all 4 grid-B clamps + load gate): `re/harness/bin/sc3resize.dll`,
  `re/harness/bin/resize_launch.exe`.
- Your standing install provides the draggable frame + X-quit: `Apps/GZGraphicD.dll` = `acefadf0`
  (`resizable_frame` + `close_button_quit`), `Apps/SIMSPR.DLL` = `f5b9f1d9`. The DLL patches the rest
  in memory and needs no on-disk change.

Confirm the install (optional):
```powershell
py -3.12 -c "import hashlib; [print(f, hashlib.sha256(open(f,'rb').read()).hexdigest()[:8]) for f in ('Apps/GZGraphicD.dll','Apps/SIMSPR.DLL')]"
# expect: GZGraphicD acefadf0 , SIMSPR f5b9f1d9
```

## Run it

```powershell
$env:SC3RESIZE_LOG = "$PWD\re\harness\sc3resize_handtest.log"
& .\re\harness\bin\resize_launch.exe -- (Resolve-Path 'Cities\Europolis.sc3').Path
```
(No `-kill`, so it runs until you close it. Use your own city if you prefer — a dense one shows the fill
best. The launcher injects `sc3resize.dll` from beside itself.)

Wait for the city to load (a few seconds; the load-readiness gate holds resizes for the first ~3 s).

## Do this, in order

1. **Grow it:** drag a window edge/corner larger, OR click maximize. Watch the isometric city view.
2. **Shrink it:** drag it back down smaller (this is the `U-069` downward path).
3. **Maximize / restore** a couple of times.
4. Close with the **X** (should quit cleanly — `close_button_quit`).

## What to look for — record PASS/FAIL per row

| # | observation | PASS | FAIL |
|---|---|---|---|
| 1 | after growing, the **city fills the whole window** | terrain/buildings extend to all edges | black band or the old view stuck in the top-left corner |
| 2 | the enlarged view is a **real image, not garbage** | coherent city | torn / noise / wrong colours |
| 3 | **shrinking** works too | view redraws correctly smaller | black, garbage, or frozen |
| 4 | **no crash** across several resizes incl. maximize | game stays up | crash / exit |
| 5 | HUD (toolbars) — *known gap, not a blocker* | — | HUD may not reflow (stays 1024x768 layout with margins) — expected, separate item |

**The decisive rows are 1-4.** Row 5 (HUD reflow) is a known, separate, unfixed item — note it but it
does not fail the D-004 test.

## After

Send back: which rows passed/failed, a screenshot if easy, and the log
(`re/harness/sc3resize_handtest.log`) — it will show `--- GRIDB_CLAMP ... all grid-B walkers clamped`,
the readiness gate, and one `RZ ---- done (all 9 steps) ----` per resize (with `RZ *** FAULT CAUGHT ***`
if anything faulted). If rows 1-4 pass, **D-004 is confirmed and the resize mod is complete end-to-end.**

⚠️ If it crashes, the log's last `RZ` lines + any `FAULT CAUGHT` (code + `MODULE+RVA` + step) localise
it — that is exactly what a headless run cannot capture, so the log is valuable either way.
