# BUTTON_RESULTS.md — **B-CONSUMED.** A relocated HUD button receives and consumes the click.

Scored against `BUTTON_PRE.md` (committed `0aed59f`, before the run). Fresh process, capture gate
armed. Raw: `button_clean.json`, log `button_clean.log`.

## `btn_b` (1747,1045) — the decisive trace

Four-level descent, every gate passing, on the ROUTER branch (`cap28=0x0`):

```
DISPATCH type=7 (1747,1045) branch=ROUTER vt+0x130 cap28=0x0
  TRAVERSAL root      [0 0 2048 1081]      kids=15   vt+0xe4 -> 1
  TRAVERSAL container [0 0 2048 1081]      kids=5    vt+0xe4 -> 1
  TRAVERSAL bar       [1248 1025 1847 1081] kids=5   vt+0xe4 -> 1
  TRAVERSAL button    [1736 1034 1758 1056] kids=0            <- leaf reached
      HANDLER vt+0x130 button    ret=1     <<< THE EVENT IS CONSUMED
      HANDLER vt+0x130 bar       ret=1
      HANDLER vt+0x130 container ret=1
      HANDLER vt+0x130 root      ret=1
DISPATCH LEAVE ret=1
```

The button's own handler **returns 1** and that 1 propagates back up through bar, container and
root to the dispatcher. On the matching button-UP the handler returns 0, which is the expected
release. **And the button took the mouse capture** (`cap28` became `0xe15cc88` — the button object
itself) — grabbing the mouse on press is what a working button does.

## Negative control passes

`bar_bg` (1547,1053) descends root → container → bar, **hits no button**, and the bar's handler
returns **0** — not consumed. Exactly as pre-registered. Had the background "hit" a button, the run
would have been void.

## `btn_a` is INCONCLUSIVE — reported, not hidden

`btn_a` (1815,1055) took the **CAPTURE** branch. `sink+0x28` read `0x0` at the gate but a capture
existed by the time the click was dispatched, so it was routed to the captured window without
hit-testing. The gate narrowed the window for this race but did not close it. **One of three points
is uninterpretable; the verdict rests on `btn_b` plus the negative control.**

## Verdict

**B-PASS and B-CONSUMED.** The routing chain is repaired from the dispatcher to the leaf widget, and
the widget accepts the event.

## ⛔ Still not a clickability claim

Pre-registered, and it holds: **this shows the event reaches and is accepted by the widget. It does
not show the widget performs its user-visible action** — the tool changing, a panel opening, art
highlighting. That is not observable from this trace. **Only an owner hand-test settles it, and I am
not claiming the HUD is clickable.**

Also still unmeasured: any side effect of widening the container rect on painting, layout or
clipping.

## For the hand-test

`SC3RESIZE_CLUSTER=1`, click the buttons in the bottom-right cluster. Also worth checking whether
the standing board note *"navigation works only in the top-left 800x600"* is gone — that is very
likely the same stale rect.
