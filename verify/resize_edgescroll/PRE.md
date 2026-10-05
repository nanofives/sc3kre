# PRE — edge-scroll band follows the resized window (`SC3RESIZE_EDGEFIX`)

Written 2026-10-05, committed BEFORE any run. Owner request 2026-08-30: match the edge-scroll band
to the new window bounds.

## Mechanism (static, all SIMSPR, vtables read from the PE)

- `FUN_10043989(outer)` is `__fastcall` and builds the edge rects `outer+0x178..+0x1c4` from the view
  bounds `outer+0xd8..+0xe4` as base +-64 (x) / +-48 (y) `[CONFIRMED @ SIMSPR 0x10043989]`.
  With bounds `[0 0 W H]`: inner `[64 48 W-64 H-48]`, L `[0 0 64 H]`, T `[0 0 W 48]`,
  R `[W-64 0 W H]`, B `[0 H-48 W H]`.
- The band test is `FUN_10043a38(outer, x, y)` = outer `vt+0x40`. It is reached on every mouse move:
  sub `vt+0x1cc` `FUN_1004947d` -> outer `vt+0x7c` `FUN_10049a6e` -> outer `vt+0x40`, when no tool
  delegate is installed at sub `+0x224`. A point outside the inner rect sets flag `+0x1e5`, plus one
  flag per band it is in: L `+0x1e4`, T `+0x1e1`, R `+0x1e3`, B `+0x1e2`. Gated by `+0x177 != 0`
  and `+0x1e6 == 0` `[CONFIRMED @ SIMSPR 0x10043a38, 0x10049a6e]`.
- Outer vtable `0x10067894`, sub vtable `0x100676ac`: both installed by the constructor at RVA
  `0x486d2`. Cross-check: outer `vt+0xa0` = `FUN_10048a2d`, the same slot the keyboard note found.
- The engine rebuilds the bands only on load (`FUN_10044323`, outer `vt+0xa8`) and on event
  `0x624a8241` (`FUN_10048d7a`). Evidence that neither fires on a resize: logged runs show the bounds
  staying at `[0 0 2048 1081]` after a restore to 800x600, which only the mod's widen-only write
  explains.
- The mod's `rz_input_geometry` widens the bounds (view sub `+0xd4..+0xe0` = outer `+0xd8..+0xe4`) to
  the client size and never rebuilds the bands. Native bounds are `[0 0 704 544]` = 800x600 minus the
  96-wide side panel and the 56-tall bar, measured on every logged run.

**Defect, as predicted from the above:** after a resize the bands stay at their native positions. At
1920 wide the "right edge" band sits at x 640..704, in the middle of the window, and the real right
and bottom edges never trigger.

## The change

`SC3RESIZE_EDGEFIX` (default 1). Bounds = cached native bounds + `(dx, dy)` on right/bottom, exact
in both directions, then `FUN_10043989(outer)` behind an expect-or-refuse check on the outer vtable.
The bands end at the side panel and the bar, which is the native relationship. `=0` keeps the old
widen-only write with no rebuild (control arm).

Side effect, stated up front: the same bounds disarm the right-drag pan for a point outside them.
With the fix a drag that moves over the HUD disarms, as it does at native. Before, the whole client
counted.

## Run

Build `sc3resize.dll` 192,512 B. Game on the Parsec virtual display at 100% scaling (input, engine
and grab coordinates coincide), `Cities\Europolis.sc3`, `SC3RESIZE_CLUSTER=1`. Two launches, one
flag: arm T `EDGEFIX` unset (default 1, read back from the `FLAGS>` line), arm C `SC3RESIZE_EDGEFIX=0`.
Each: `re/tools/edge_probe.py` at native, then maximized, then restored to 800x600. Moves are posted
with sc3io. Let W = 704 + dx, H = 544 + dy at the maximized client.

Points at maximized size: mid `(cw/4, ch/3)`, old right `(672, ch/3)`, old bottom `(cw/4, 520)`,
new right `(W-32, ch/3)`, new bottom `(cw/4, H-24)`, left `(32, ch/3)`, top `(cw/4, 24)`.

## Predictions

| # | observable | arm T (EDGEFIX=1) | arm C (EDGEFIX=0) |
|---|---|---|---|
| 1 | bands at maximized | match the formula with `[0 0 W H]` | native: inner `[64 48 640 496]` |
| 2 | new right / new bottom | `R=1` / `B=1` | all four flags 0 (`out=1`, in no band) |
| 3 | old right / old bottom | no flag, `out=0` | `R=1` / `B=1` |
| 4 | mid, left, top | none / `L=1` / `T=1` | same as T |
| 5 | bands after restore to 800x600 | native again, bounds `[0 0 704 544]` | bands native, bounds stay maximized |
| 6 | view translation while the mouse rests 0.4 s on new right vs old right (secondary) | moves / does not | does not / moves |

"Moves" = `|dx|` >= 8 px, or a correlation peak < 0.1 (moved too far to register). "Does not" =
`|dx|` <= 2 and `|dy|` <= 2 with peak >= 0.2.

**PASS:** rows 1-5 as predicted in BOTH arms. The control must reproduce the defect, or the arm T
result does not show the fix did anything.
**FAIL:** arm T row 2 or 3 differs from the prediction while the hook fires and `en=1`.

**VOID (no verdict, investigate):** zero hook calls at the probe points (a tool delegate is
intercepting moves), `en=0` (edge scroll disabled in this save), scaling not 100%, `edgefix` missing
from `FLAGS>`, or an `EDGE> REFUSED` line. Row 6 alone is VOID if neither arm moves at either point:
that would mean the flags do not drive a scroll under posted input. It does not void rows 1-5.

**Not claimed by this run:** that a real mouse at the physical edge scrolls. The owner hand-test
covers that. Edge scroll at the very client edge while the cursor is over the HUD is out of scope:
those moves go to the HUD window, not the city view, at native too.
