# ROUTE_RESULTS.md — partial. One real finding, one of my results is VOID, one confound found.

Scored against `ROUTE_PRE.md` (committed `6b5c035`, before the run).
Raw: `eventroute.json`, `eventroute2.json`, `dispatch_cmp.json`.

## Instrument control: PASSES

Setup found **164 windows** in the live tree and hooked **4** `vt+0x130`, **4** `vt+0x100` and
**8** `vt+0xe4` distinct targets — which vindicates hooking live vtables rather than one hard-coded
copy. A viewport click produced **22 traced gate events**, twice, so the router was genuinely
observed.

## ⛔ The `bar_bg` result is VOID — an instrument gating artifact, not a finding

`bar_bg` (1547,1053) traced **0 events**, twice, and I was one step from reporting that as
`NOT-VISITED`. It is not. **My trace window only opens inside a hooked `vt+0x130` entered with a
button event type**, and on the branch the bar click actually takes, no `vt+0x130` is entered at the
top at all — so the gate stays shut and nothing is logged regardless of what happens.

Ruled out first, properly: reordering. `eventroute2.json` posted viewport → bar → viewport → bar and
got 22 / 0 / 22 / 0, so it is reproducible and **not** a first-click window-activation artifact. The
difference is real; my instrument just cannot see the branch it lives on.

**`NOT-VISITED` must not be claimed from this run.** Nothing here says the HUD windows are absent
from the routed subtree.

## ⭐ The real finding: routing depends on `sink+0x30`, and a dialog was open

`dispatch_cmp.json`, same process, both points:

```
viewport  type=7 ev=(400,300)    cap28=0x0  foc30=0xf4c5000
bar       type=7 ev=(1547,1053)  cap28=0x0  foc30=0xf4c5000
```

**Both clicks reach `FUN_10020818` identically, with correct unclamped coordinates.** The
difference is entirely in what `FUN_10020818` does next `[CONFIRMED @ GZWIND 0x10020818]`:

- `sink+0x30` **non-null** (a focus/modal window at `[246 163 553 437]`, native-positioned):
  - point **inside** it → routed to that window's `vt+0x130` → the 22 traced events. This is the
    viewport case, because (400,300) falls inside the dialog.
  - point **outside** it → falls through to `LAB_100208bd`, which runs the `vt+0x8c` walk and then:
    ```c
    uVar8 = (*(this+0x38)->vt[0x8c])(x, y);   /* find the window */
    uVar7 = (*this->vt[0x8c])(uVar8);         /* hand it to the SINK, not the window */
    uVar7 = uVar7 & 0xffffff00;               /* low byte cleared -> returns FALSE */
    ```
    **The found window is never given the event on this branch.** That is ordinary modal
    behaviour, and it exactly reproduces "the HUD is found but nothing happens".
- `sink+0x30` **null** → `return (*(sink+0x38)->vt[0x130])(ev)` — the real router, which delivers.

## ⛔⛔ THE CONFOUND — a dialog was open in most of my runs

A modal/focus window at `[246 163 553 437]` was present in `gate.json`, `dispatch_cmp.json` and
almost certainly in the `eventroute` runs. `button.json` is the one run that measured
`sink+0x30 == 0`.

**With a modal open, HUD clicks outside it are supposed to be ignored.** So a large part of today's
click evidence may be measuring correct modal behaviour rather than the mod's defect. This was not
controlled for and it should have been: the auto-harness path-loads a city and nothing ever verified
the game was in a plain, dialog-free in-city state before posting clicks.

**What the dialog is has not been identified.** It sits at native coordinates and did not relocate,
which is separately worth noting.

## Standing, after this run

| claim | status |
|---|---|
| clicks reach the dispatcher with correct coordinates | **confirmed**, both points, `dispatch_cmp.json` |
| the `vt+0x8c` walk returns the relocated bar when it runs | **confirmed**, `gate.json` |
| routing branches on `sink+0x28` / `sink+0x30` | **confirmed** `[CONFIRMED @ GZWIND 0x10020818]` |
| the modal branch never delivers to the found window | **confirmed in decomp**, `& 0xffffff00` |
| HUD windows absent from the routed subtree | **NOT established** — the run that would have shown it is void |
| `vt+0x100` / `vt+0xe4` verdict for HUD windows | **not measured** |

## The next run, and it is now precisely specified

1. **Gate on state, not hope:** read `sink+0x30` *before* posting and only measure when it is
   **NULL**. If a dialog is up, dismiss it or abort the run. Every click result today is suspect
   without this.
2. **Open the trace at `FUN_10020818` entry** on a button event, not inside `vt+0x130`. That covers
   both branches and removes the gating artifact that voided `bar_bg`.
3. Then read `vt+0x100` and `vt+0xe4` per child on the router path and settle G1-REJECT vs
   G2-REJECT vs ROUTED-OK.

## Method note

Two instrument gaps in two consecutive runs — hard-coded slot addresses in `HITTEST_RESULTS.md`,
and a trace window that could not open on the branch under test here. Both produced a **confident
looking zero**. The pattern worth carrying: *a zero from an instrument is only evidence once the
instrument has been shown able to produce a non-zero on that exact path.* The viewport control
proved the hooks fire, but not that they fire **on the branch the bar click takes**, and that is the
gap that mattered.
