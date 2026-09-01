# BUTTON_PRE.md — clean automated button test (2026-09-01)

**Committed before the run.** Tool: `re/tools/frida_route4.py`.

## Why a new run

`PARENTFIX_RESULTS.md` proved the router now reaches the bar (P-PASS) but the button test was
**inconclusive**: the posted click took the CAPTURE branch (`sink+0x28` non-null), so it was routed
straight to a captured window and never hit-tested. That capture was left by my own earlier posted
clicks in the same process — instrument contamination.

## What is fixed in the instrument

- **Capture gate.** `sink+0x28` is asserted `0x0` immediately before each post; if held, a
  `WM_LBUTTONUP` is posted to release it, and the point is scored **VOID** rather than measured if
  it will not clear. Same for `sink+0x30`.
- **Fresh process**, and the **button point is posted first**, before any viewport click, so no
  earlier click can leave state behind.

## Points (client 2048x1081, cluster mode; rects observed in `route_armA.json`)

| name | point | target rect (a bar child) |
|---|---|---|
| `btn_a` | (1815,1055) | `[1795 1036 1835 1075]` |
| `btn_b` | (1747,1045) | `[1736 1034 1758 1056]` |
| `bar_bg` | (1547,1053) | bar background — **negative control**, should reach the bar and no button |

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **B-PASS** | `btn_a`/`btn_b`: the target button passes `vt+0xe4` (ret=1) **and** its `vt+0x130` handler is entered | **The click reaches the button widget.** Routing is fixed all the way to the leaf. |
| **B-CONSUMED** | additionally the button's `vt+0x130` returns **1** | The widget **handled** the event — the strongest automated evidence short of a hand-test. |
| **B-STOPSHORT** | the bar is reached but no button passes `vt+0xe4` although the point is inside a button rect | Routing reaches the container and stops — a further defect below the bar. |
| **B-VOID** | capture or focus not clear before posting, or branch != ROUTER | Do not interpret. |

## Stated in advance

- **Even B-CONSUMED is not "the HUD is clickable".** It shows the event reaches and is accepted by
  the widget; whether the widget performs its user-visible action (tool changes, panel opens) is not
  observable here. Only an owner hand-test settles that, and I will not claim it from this run.
- `bar_bg` is the negative control: it must reach the bar and **not** any button. If it "hits" a
  button, the instrument or the rects are wrong and the whole run is void.
