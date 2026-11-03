# placehints2 RESULTS (2026-11-02)

Build: `dev\placehints2\inst\sc3resize.dll` from child/placehints2 (main 89c015f + this stream), loader from the same
tree. Driving: posted input only (sc3io messages, `roadover_drive.py`, a scratch hover / key / button-up driver), no
real mouse or keyboard. Berlin, 800x600 windowed, `SC3RESIZE_PLACEHINTS_LOG=1`. Pictures:
`MAIN\verify\placehints2\owner_shots\` (frame dumps). Detail and RVAs: `re/analysis/PLACEHINTS.md` D.

Owner: "the extra information when placing a zone should be visible when pressing shift, the zone impact should be in
a shade of green, light blue is the same as the zone it's being placed".

## 1. Hint text only while Shift is held

| case | result | picture |
|---|---|---|
| Big Park hover, no Shift | plain stock label `$1,000`, halo drawn | `C1_park_green_halo_no_shift.png` |
| posted `WM_KEYDOWN` VK_SHIFT, mouse not moved | label re-posted at once: `$1,000 \| Valor del suelo R +36% C +21% I +6% \| en verde R +9% o mas hasta 10 celdas`. Log `Shift down: label re-posted` | `C2_park_shift_text.png` |
| posted `WM_KEYUP` VK_SHIFT, mouse not moved | back to `$1,000` | `C3_park_shift_released.png` |
| airport drag held, no Shift | `$15,000` only, zone preview drawn | `B1_airport_drag_no_shift.png` |
| same drag, posted Shift down | `$15,000 \| Aeropuerto 30 celdas, 0 sin transporte (rojo) \| cap. C +15000, uso 60% a 59% \| techo C 800 a 820 \| necesita energia y agua` | `B2_airport_drag_shift_text.png` |

Stock meaning of Shift (checked before building, `PLACEHINTS.md` D): it does matter, at button release only. The zone
and building tools commit on left-button-up only when the Shift flag is clear (SIMRCI `0x1003f7ca`, SIMGEOM
`0x1002165e`, flag mapped from MK_SHIFT by GZGraphicD `0x10017b90`). Releasing the mouse with Shift held cancels the
zone or the plop. Measured: posted button-up with MK_SHIFT after the 30-cell airport drag, no zone placed, money
unchanged at $123,479 (`B3_release_with_shift_cancels.png`). Pressing and moving ignore Shift. The block leaves this
stock rule alone. **Owner call:** keep it (look with Shift, let Shift go, then release to place, or release with
Shift held to cancel), or have the mod drop the Shift flag from the button-up while a hint tool is active so Shift
plus release still places.

## 2. Impact area in green

| case | result | picture |
|---|---|---|
| Big Park on an open lot | footprint in the stock light blue, land value halo green on terrain and on the buildings inside it | `C4_park_blue_footprint_green_halo.png` |
| Big Park over buildings (stock refuses) | footprint stock red, halo green | `C1_park_green_halo_no_shift.png` |
| Esc after the preview | halo gone, view as stock | `C5_after_esc.png` |

Log: `green row 0x35 added to palette style 0 (53 rows, 32 shades): mid shade light blue 0 101 131 -> green 32 129 32`.
Falls (negative land value) stay red. The airport zone hint draws only red cells, so nothing changed there. The label
word for the rising part is now "en verde" / "green" (new key `placehints.in_green`, fr/de/it/nl/sv machine
translations added with `sc3lang.py merge`, `check` clean: 278 keys, 0 missing in every table).

## Not covered / needs owner check

- **The real Shift key** (a modifier cannot be posted, memory `reference-posted-modifier-keys`). The lab drove the
  game window's own `WM_KEYDOWN` / `WM_KEYUP` VK_SHIFT, which is what the block reads, so only the physical key is
  untested. Owner: hover a park, press and release Shift without moving, then drag an airport and do the same.
- `SC3RESIZE_PLACEHINTS_SHIFT=force|never` and `SC3RESIZE_PLACEHINTS_GREEN=0` built, not launched.
- Only sc3resize was rebuilt and tested in this inst. The other mods were not loaded. New hooks: SIMSPR highlighter
  getter slot (vtable `0x10067a5c` +0x30), SIMSPR E8 at `0x10019903`. A grep of `re/harness/src` finds no other mod
  patching them. sc3undo clears the tint through inst vt+0x28(0), which still works.
- Seaport and plop buildings other than Big Park not re-shot (same code path).
