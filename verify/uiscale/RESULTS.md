# uiscale: HUD scale Auto by default + the city cost label at the HUD scale (owner img17, 2026-10-22)

Branch `child/uiscale` (worktree `Simcity_wt_uiscale`, from main 2564a08). Code: `re/harness/src/sc3resize.c`, all edits
marked `task uiscale`. Test: instance `Simcity_stock_avx32\re\harness\inst_uiscale`, all mods built from the worktree,
lab.sc3, road tool drags by posted input (held, grab, release), monitor dpi 240, window dpi 240.

## 1. Auto is the default

- `[hud] scale` missing (or no ini) = 1 = Auto. The factor is the existing fit rule `min(cw/800, ch/600)`, recomputed
  every present, so it applies at start and after every resize. Same rule as before; no better rule found.
- Preferencias "Escala de la interfaz": `Auto  Normal  125%  150%  200%`, Auto first and selected when scale is 1. The old
  "Ajustar"/"Fit" option is this Auto (same id 0x02F95B42, same value 1).
- An ini from an earlier build holding `scale=0` and no `ver` key is read as Auto once. 0 was the old default and OK wrote
  it back unchanged, so it does not tell a choice from a default. Every save now writes `ver=2`, so a Normal picked from
  now on persists.
- New log line on every size or mode change: `HUDSCALE> Auto: client WxH -> factor F`.

| check | result |
|---|---|
| fresh instance, no ini | `HUDOPT> on: scale 1`, `Auto: client 800x600 -> factor 1.000 (native size)` |
| resize to 1600x900 | `Auto: client 1600x900 -> factor 1.500` |
| maximized | `Auto: client 3840x1984 -> factor 3.307` |
| option list (`after_prefs_auto_first_selected.png`) | Auto first, selected |
| pick Normal, OK, relaunch | ini `scale=0 ver=2`, next start `HUDOPT> on: scale 0` (kept) |
| old ini `scale=0`, no ver | `ini scale=0 from a build before Auto (no ver=2): read as Auto`, `scale 1` |

## 2. City cost label at the HUD scale, clear of the pointer

Cause: since COSTLABEL the city cost label (tooltip window vt exe+0xd3bcc) is kept native when the cursor is in the city.
At 3.307x it is 26x16 px, and the game puts it 2 px below a 76 px box under the hotspot (TIPCURSOR), next to a pointer that
Windows draws 64 to 80 px at dpi 240.

Change: that native case now draws the label enlarged by the HUD factor (a DLGSCALE slot: cached resample, native copy
erased with the city layer, restored after the present, no mouse mapping). Placement from the cursor point the TIPCURSOR
stubs record: centred under the pointer box, top `clearance + gap` below the hotspot (clearance = max(pointer size,
CursorBaseSize x dpi / 96) in game px = 80 here, gap = 2 + 2s). If that hits the client bottom or an enlarged HUD window,
it moves left of that window, then above the hotspot. HUD tooltips keep the COSTLABEL enlarged path (unchanged).
`SC3RESIZE_COSTLABEL_SCALE=0` = native label as before. Log: `COSTLABEL> city label [native] -> [drawn] s, cursor (x,y), ...`.

The magenta cross in the shots is the posted cursor point, the box is the 80 px clearance (grabs never show the pointer).

| shot (`owner_shots/`) | case | result |
|---|---|---|
| `after_800x600_native_label.png` | 800x600, factor 1.0 | stock label, unchanged |
| `after_1600x900_1500_label_bottom_right_corner_center.png` | 1600x900, 1.5x | centre: below; near the bar: above the hotspot; at the side panel: below, left of the panel; near the minimap: above |
| `after_max_3307_label_center_bottom_right_corner.png` | 3840x1984, 3.307x | centre: below (86x53); near the bar: above; at the panel: below, left of it; near the minimap: below, left of its button |
| `after_max_3307_label_topleft.png` | top-left | below the pointer |
| `after_max_hud_tooltip_still_enlarged.png` | hover Emergencia | tooltip enlarged beside the enlarged button, as before |

Every logged label decision in the maximized run: `below the pointer` or `above the hotspot`, none `SHIFTED onto the
pointer rows`.

Not measured: the drawn pointer size at (CursorBaseSize 32, dpi 240). `SM_CYCURSOR` there reads 64. The clearance takes
32 x 240 / 96 = 80 so the label errs clear. Grabs cannot show the pointer, and the DXGI pointer-shape tool needs the real
mouse over the window. Save/reload not relevant (no game state touched). Only startup `VEH FAULT` = the known
`0xC0000096 at SC3U.exe+0x84122` (also in both owner logs of 2026-10-22).

## Also changed

`re/scripts/lan_release/stage_lan_release.py`: `sc3resize.ini` added to APPS_SKIP. It is per-PC player state, and
`Simcity_release\Apps` now holds one (written by a local run at 14:37). The current manifest does not list it, so the
owner's earlier `scale 0` starts were the old default, not an overwrite.
