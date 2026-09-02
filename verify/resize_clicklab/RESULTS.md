# RESULTS.md — the visual click test is **V-AMBIG**; the OWNER HAND-TEST then PASSED (2026-09-01)

## ⭐⭐⭐ THE RELOCATED HUD IS CLICKABLE — owner hand-test, cluster mode, 2048x1081

The question `BUTTON_RESULTS.md` refused to answer is answered, and by the only instrument that could
answer it. Owner, on the running game (`handtest/run.log`, pid 28528, `cluster=1 input=1`, no
synthetic input posted — every click in that log is a human one):

> "the buttons of the HUD works, tool changes / panels open ... i can move panels around the whole
> screen and it works"

So the chain is complete end to end: the router reaches the relocated widget (`P-PASS`), the widget
accepts the event (`B-CONSUMED`), and **the widget performs its user-visible action**. Panels are
also draggable anywhere in the 2048x1081 client area, which was never tested before.

The log corroborates the setup rather than the verdict: real clicks come in at `clamp bounds=2048x1081
(stored rect [0 0 2048 1081])` — the mouse clamp is correct at the new size — and clicks landing on
the side panel resolve to the relocated window (`[1952 481 2048 923]`, `shown=1`).

### Two residual defects, owner-reported, both NEW to the record

1. **Hover/tooltip labels still paint in the old 800x600 region**, not next to the cursor. This is
   visible in an old artefact nobody read: the `Zona` tooltip sitting mid-screen in
   `verify/resize_flaggate/before.png`. In this run's window census the same class shows the split —
   window `[3]` logs `rect+0x14=[3274 1470 3283 1485]` against `ext+0x80=[1386 553 1395 568]`, the
   `<<< PAINT/WINDOW DIVERGE` line that reproduces in every cluster run.
2. **The map itself cannot be clicked.** The HUD works, the city view does not take input. This is
   almost certainly the standing board note *"navigation works only in the top-left 800x600 — input
   picking reads a different size source than the blit"*, now sharpened: the mod records and fixes
   only HUD windows (`g_wins`), and **no city-view window appears in the census at all**, so nothing
   has ever widened its hit rect. `[UNCERTAIN]` — not yet instrumented.

**Next target: the city-view window's hit/pick rect**, the same class of fix that just worked for the
HUD, applied to the one window the mod never touched.

---

## The automated part of this session: V-AMBIG (2026-09-01)

Scored against `PRE.md` (committed `34a821a`, before the run). Four automated runs, all at client
**2048x1081**, path-loaded Europolis, zero `FAULT CAUGHT` in any log.

## The pre-registered verdict: V-AMBIG

| shot (vs `s0_noise_a`) | HUD | SIDE | MINI |
|---|---|---|---|
| `s0_noise_b` (idle baseline) | 0.09% | 0.59% | 0.12% |
| `s_btn_b` | 79.3% | 82.5% | 82.9% |
| `s_btn_a` | 72.7% | 81.9% | 72.5% |
| **`bar_bg` (negative control)** | **69.9%** | **79.7%** | **74.0%** |

The negative control moves as much as the buttons, which `PRE.md` names **V-AMBIG — do not
interpret**. Consecutive-frame diffs show why: the `VIEW` region moves 76–80% on every click too.
**The posted clicks scroll the camera** (the points sit near the bottom/right edge of the client
area, which is the edge-scroll band), so the whole frame translates and every region-diff is
dominated by that. The instrument cannot separate a widget action from a camera scroll.

**No claim is made about clickability from this run.** `BUTTON_RESULTS.md`'s B-CONSUMED still
stands on its own evidence; this run adds nothing to it.

## ⛔⛔ CORRECTION (owner, same day): the HUD IS ON SCREEN. The captures are the artifact.

**Everything in the section below is refuted by direct witness.** The owner looked at the running
game in cluster mode and the HUD is there in the bottom-right corner. The `[UNCERTAIN]` caveat that
was written into this file before the owner was asked is the one that fired: **a GDI
`CopyFromScreen` capture of this DirectDraw-presented window does not contain the HUD layer.**

Consequences, and they are the useful part:

- **Screenshot diffing is nondiagnostic for any HUD question in this game.** The HUD regions in the
  table above were measuring the *city view underneath* the HUD, not the HUD. That also explains why
  those regions moved 70–80% in lockstep with `VIEW`: it was all one scrolling frame.
- This is the **nondiagnostic-proxy class again** — the same failure as `verify/resize_census`
  (surface fill read as on-screen fill) and the `PrintWindow` "clipped 800x600" shot already retired
  as a capture artifact. **Pixel capture of SC3U from outside the process has now been wrong three
  times.** Do not settle a visual question with it; ask the owner or read inside the process.
- The four-arm table below is still evidence of *something* — `HUDNATIVE=1` and the default arm DID
  capture HUD pixels while cluster captured none — but whatever that difference is, it is a
  difference in what the capture path sees, **not** in what reaches the monitor. Unexplained, and
  not worth a run.

## (REFUTED — kept for the reasoning) What the screenshots showed

This was not what the run was looking for, and it is refuted above.

| arm | flags | HUD visible in the capture? |
|---|---|---|
| cluster | `CLUSTER=1` (FLAGS line verified) | **NO** — city fills the whole window, nothing in the bottom-right |
| cluster, no hit-rect writes | `CLUSTER=1 NOHIT=1` (verified) | **NO** |
| shipped default (dock+span) | all defaults, `hudfit=1` | **PARTIAL** — side panel + minimap painted near mid-screen, **bottom bar absent** |
| HUD untouched | `HUDNATIVE=1` | **YES** — bar, side panel, minimap and RCI all painted |

Two shots from the **previous session** (`verify/resize_flaggate/before.png` 17:29 and `ctrl.png`
17:33, cluster arm and `NOPARENTFIX` control arm) show the same thing and were never analysed. That
is **5 captures across 3 runs with no HUD in cluster mode**, versus a clean HUD the moment
`HUDNATIVE=1` is set.

**Excluded so far:** the `+0x80..0x8c` hit-rect writes (`NOHIT=1`, HUD still absent) and the
ancestor-rect widening (the previous session's `NOPARENTFIX` control shot, HUD still absent).

`[UNCERTAIN]` — one thing this method cannot exclude by itself: these are GDI `CopyFromScreen`
captures of a DirectDraw-presented window. A capture landing between the viewport blit and the HUD
composite would look exactly like this. **An owner glance settles it in one second**, and the board
records the cluster HUD as previously owner-confirmed, so this is a contradiction to resolve by eye
before any code is touched.

> **That is exactly what happened. The owner looked; the HUD is there. See the correction above.**
> Cost of not asking first: three control-arm runs. Cost avoided by writing the caveat before the
> answer: a false "the cluster HUD regressed" entry on the board.

## Also visible in the log, unexplained

`CLUSTER> [3] paint=[1386 553 1395 568] window=[3274 1470 3283 1485] <<< PAINT/WINDOW DIVERGE`
reproduces in every cluster run. That window's rect was translated by `(1888,917)` while the other
three were translated by `(1248,481)` — the minimap's translation applied to a window that already
carried the bar's. It lands off-screen at 3274,1470.

## Artefacts

`s0_noise_a/b`, `s_btn_a/b`, `s_bar_bg` (cluster), `armNohit/`, `armDefault/`, `armNative/`,
`live/` (the session left running), `diff.py`, `drive.ps1`, `run.log` per arm.

⚠️ One arm was void and is not in the table: the first `armNohit` invocation passed `-EnvVars` as a
quoted list under `pwsh -File` and the DLL read `cluster=0 nohit=0` — the exact failure
`HANDOFF.md` warns about. Caught by the `FLAGS>` echo, which is why that line exists. Re-run with
the flags verified before anything was read from it.
