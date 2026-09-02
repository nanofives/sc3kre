# TOOLTIP.md — the hover label is placed at the cursor and CLAMPED TO 800x600 (2026-09-01, measured)

Owner-reported defect: after a resize, the in-game hover label still appears "on the 800x600 part of
the screen". Now measured rather than described.

## Instrument

`re/tools/frida_tooltip.py` — attaches to the live game, walks the window tree from the event sink's
root every 200 ms, diffs successive snapshots and stamps each change with the live cursor position in
screen **and** client coordinates. No hooks, no writes; all reads bounded and individually guarded.
Idle control: 60 s with the game untouched produced **zero events** — no false positives.

Raw: `tooltip2.json` (51 label samples over an owner-driven hover session, cluster mode, client
2048x1081).

## The label

One window, `0x0063b418`, **vftable `SC3U.exe+0xd3bcc`** (virtual address `0x004d3bcc`). Height 16 px,
width varies with the text. It is a **SC3U.exe class, not SIMUI** — which is why nothing in the HUD
work ever touched it.

## The measurement

| cursor (client) | label rect |
|---|---|
| (1969, 775) | `[755 582 798 598]` |
| (1979, 663) | `[762 582 798 598]` |
| (2010, 602) | `[696 564 798 580]` |
| (1968, 528) | `[739 512 798 528]` |
| (2018, 500) | `[757 492 798 508]` |
| (2031, 493) | `[757 492 798 508]` |

Two invariants hold across all 51 samples:

- **The right edge is `798` in every single sample** = `800 - 2`. Cursor x ranged 1810..2037 and the
  label never moved right of 798.
- **The top clamps at `582`** = `600 - 2 - 16` (label height 16). Below that bound the top tracks the
  cursor **1:1, not scaled** — cursor y 500 → top 492, y 528 → top 512, y 550 → top 528, y 602 → top
  564, y 628+ → pinned at 582.

**So the placement is: position at the cursor, then clamp to fit inside a screen extent still believed
to be 800x600.** No scaling is involved, which rules out a coordinate-space mismatch and leaves a
single stale bound.

`[UNCERTAIN]` — every sample had cursor x in 1810..2037, so x-tracking below 800 was not exercised.
The y axis proves the tracking-plus-clamp shape; the x axis only proves the clamp.

## What decides the fix

Whether the `800`/`600` (or `798`/`598`) bound is a **hard-coded immediate** in the positioning
routine, or is read from a **global / field holding the display size**. Immediate → code patch, like
the four grid-B clamps. Global or field → a runtime write, which is what the mod already does
elsewhere and is much cheaper. Static read in flight against `0x004d3bcc`.

## Also seen

`SIMUI.DLL+0xa9a80` moved 5 times during the session — a different class, unexamined.
