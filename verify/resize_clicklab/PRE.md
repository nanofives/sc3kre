# PRE.md — does a relocated HUD button DO anything? (2026-09-01, automated)

**Committed before the run.** Follows `verify/resize_flaggate/BUTTON_RESULTS.md`, which established
**B-CONSUMED** (the click reaches the leaf widget and its `vt+0x130` returns 1) and explicitly refused
to call that "clickable". This run attacks the one thing that trace could not see: **a user-visible
change on screen**.

## Instrument

`verify/resize_clicklab/drive.ps1` — path-loads Europolis under `SC3RESIZE_CLUSTER=1`, maximizes
(client 2048x1081), settles, then for each point posts `WM_MOUSEMOVE` + `WM_LBUTTONDOWN` +
`WM_LBUTTONUP` (the same delivery proven to reach the widget in `button_clean.json`) and captures a
full-window PNG before and after. `diff.py` counts changed pixels per region.

**Screenshots are of the real window on the real desktop** (`CopyFromScreen`), so this measures what
reaches the monitor, not an internal surface. That distinction is the standing `D-004` /
nondiagnostic-proxy lesson.

## Points (client coords, cluster mode; rects from `route_armA.json`)

| name | point | meaning |
|---|---|---|
| `noise` | — | two shots 1.4 s apart with NO input — **the idle-animation baseline** |
| `btn_b` | (1747,1045) | the button proven consumed in `BUTTON_RESULTS.md` |
| `btn_a` | (1815,1055) | second bar button |
| `bar_bg` | (1547,1053) | bar background — **negative control**, should do nothing |

## Regions scored

- `HUD` = bar `[1248 1025 1847 1081]`
- `SIDE` = side panel `[1952 481 2048 923]`
- `MINI` = minimap `[1888 917 2048 1081]`
- `VIEW` = everything else (the city view — expected noisy, the sim is running)

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **V-PASS** | after `btn_b`, changed pixels in `HUD` **or** `SIDE` exceed the `noise` baseline for that same region by >=10x, and `bar_bg` does not | **The button performs a visible action.** Clickability demonstrated without a hand-test. |
| **V-NULL** | `btn_b` diff stays within the `noise` band in every HUD region | The event is accepted (already proven) but **produces no visible action** — a real remaining defect, and the next thing to chase. |
| **V-AMBIG** | `bar_bg` also exceeds the baseline | The signal is not attributable to the button. Do not interpret. |
| **V-VOID** | client size != 2048x1081, `FAULT CAUGHT` in the log, or the `noise` baseline already saturates a HUD region | Do not interpret. |

## Stated in advance

- The sim runs, so `VIEW` will be noisy by construction. **Only the HUD regions are scored.**
- A posted click is not a hand click. If it reaches the widget (proven) but the widget's action needs
  real cursor state the engine polls elsewhere, a V-NULL could be an instrument limit rather than a
  mod defect. That caveat is recorded now, not after seeing the number.
- Install is **already MODIFIED on disk** (`GZGraphicD.dll`, `SIMSPR.DLL`) from earlier staged work.
  The mod patches nothing on disk; this is recorded, not corrected.
