# placehints3 RESULTS (2026-11-02)

Owner decision: "Make Shift + release place the zone". Build `dev\placehints3\inst\sc3resize.dll` (main e509d99 + this
stream). Berlin, 800x600 windowed, posted input only (down, moves, then `WM_LBUTTONUP` with wParam MK_SHIFT, plus a
posted VK_SHIFT key message so the hint text shows as in the owner's flow). Pictures: `verify\placehints3\owner_shots\`.

## What changed

While the active tool is the one whose preview made the current hint (airport / seaport zone drag, plop with a land
value row), the Shift flag is dropped from the left-button release, so it places exactly like a plain release.
- Hooked: zone tool left-up slot (SIMRCI vtable `0x1004c06c` +0x28 = `0x1003f7ca`) and the four building tool vtables
  (SIMGEOM +0x28 = `0x1002165e`). The wrapper clears bit 0 of the flags argument, then calls the original.
- Narrow: only when `tool == the hint tool` and a hint is set. Other zone types, plops with no land value row, other
  tools and every other use of Shift keep stock behaviour.
- Off switch `SC3RESIZE_PLACEHINTS_SHIFTPLACE=0` (stock cancel). Not launched with it.

## One in-game check each

| case | result | picture |
|---|---|---|
| 30-cell airport drag, release with MK_SHIFT | zone placed, money $117,006 -> $102,006 = the game's own $15,000 | `A1_airport_drag.png`, `A2_airport_placed_by_shift_release.png` |
| Big Park plop, release with MK_SHIFT | park placed, money $117,006 -> $115,961 = the $1,045 on the label | `B1_park_placed_by_shift_release.png` |
| road drag, release with MK_SHIFT (control) | nothing built, money unchanged at $115,961 (stock cancel kept) | `C1_road_shift_release_stock_cancel.png` |

Before the fix the same airport release with Shift placed nothing (placehints2 RESULTS, B3).

## Notes

- First build patched the building slots with the wrong RVA (`0x165e`, should be `0x2165e`), so parks were still
  cancelled. Found by logging the release, fixed. The slot check is silent when it does not match, a mismatch leaves
  the plop at stock behaviour.
- Needs owner check: the physical Shift key and release (posted messages only here), and the other mods loaded
  together. No other mod source patches these two up slots.
