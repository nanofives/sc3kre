# nativetext: sharp text in the enlarged HUD and dialogs, 2026-10-26

Child `nativetext`. Worktree `Simcity_wt_nativetext` (branch `child/nativetext` from main `742fe1f`). Test tree
`Simcity_stock_nativetext`: all 7 mods + `version.dll` built from the worktree, Europolis, HUD scale Auto, Suavizado
on. Driven with posted messages only (no cursor, no foreground, no topmost). Pictures from `SC3RESIZE_FRAMEDUMP`.
Code and mechanism: `re/analysis/HUD_SCALE.md`, section "Text drawn at the factor".

## What it does

Today HUDSCALE / DLGSCALE resample the native HUD and dialogs, text included. NATIVETEXT hooks the game's one glyph draw
(GZServiceD `0x10006e54`), tracks every glyph through the Blts to its place in the frame, and after the resample erases
the magnified glyph and draws it again at the factor. Two looks:

- **A**: TrueType. Comic Sans MS for the game's two anti-aliased UI fonts (dialogs, titles; the game face is a Comic Sans
  style, measured from the dumped sheets), Arial Bold for the 1-bit bar/ticker font. Size: 'H' matched to the game font's
  cap height x factor. Each glyph stays at the game's own position and baseline, so the spacing is the game's.
- **B**: the game's own glyphs rebuilt. Each glyph's coverage (15 levels, or 1-bit) is resampled bicubically at the dest
  resolution and its edges sharpened to about one dest pixel. Generated in memory, nothing shipped.

Colours are the glyph's own (palette entry 1 at draw time), so the yellow ticker, blue fields, white titles and the red
funds when negative keep their colours. Shadows drawn as a second glyph (the compass "N") are two records and stay.

## Pictures (`owner_shots/`, each sheet stacks: now / A / B)

| file | what |
|---|---|
| `00_bottom_2560_1to1.png` | bottom of the frame at 2560x1351 (2.252x), 1:1 |
| `01_ticker_2560_x2.png` | news ticker, zoomed 2x |
| `02_bar_fields_2560_x2.png` | city name, Pob, funds, date, zoomed 2x |
| `03_bar_rci_minimap_2560.png` | RCI letters, minimap compass, 1:1 |
| `04_dialog_reunirse_2560_1to1.png` | Reunirse, 1:1 |
| `05_dialog_text_2560_x3.png`, `06_dialog_label_2560_x3.png` | dialog title and labels, zoomed 3x |
| `07_max_ticker_bar_1to1.png` | maximized 3840x1984 (3.307x): ticker and bar fields, 1:1 |
| `08_max_dialog_text_x2.png`, `09_max_dialog_label_x2.png` | maximized: Reunirse title and labels, zoomed 2x |
| `10_max_bottom_right_1to1.png` | maximized: bar end, RCI, minimap, 1:1 |

What the sheets show: "now" is soft with blocky steps at both sizes. A and B are sharp. A is smoother and rounder, but its
letters are narrower than the game's at the game's positions, so some words open small gaps ("Asesor es" in 05, 08). B
keeps the game's letter shapes and widths exactly, with a slight pixel-font character on the 1-bit bar font.

## Cost per frame

Final build, maximized 3840x1984 (3.307x), Europolis, HUD only, 10-s windows, about 22 fps (`QueryThreadCycleTime`
and wall time):

| look | glyphs drawn per frame | NATIVETEXT per frame | whole HUD pass per frame |
|---|---:|---:|---:|
| off (`0`) | - | - | 37.2 to 41.7 M cycles, 10.8 to 12.4 ms |
| B (`2`) | 101 | 6.3 to 6.5 M cycles, 1.78 to 1.84 ms | 40.8 to 44.7 M, 12.2 to 13.2 ms |
| A (`1`) | 101 | 6.9 to 7.0 M cycles, 1.94 to 1.98 ms | 44.3 to 46.1 M, 13.0 to 13.5 ms |

The ticker scrolls every step, so its word groups (about 6 per frame) are recomputed; every other line is pasted from the
cache (`areas pasted from the cache 2832, recomputed 1288` over 223 frames). Masks are built once per glyph and factor
(34 for the HUD). Earlier numbers on a loaded PC (3 games, 4 to 10 fps), before the ticker fix below: 2560x1351 HUD 1.2 to
1.8 M cycles for 47 glyphs; Reunirse open 1.9 to 2.9 M for 89 glyphs. The first build without the cache took 4.5 to 6.3 ms.

## Checks

- Default off path: `SC3RESIZE_NATIVETEXT=0` (or `_CTL` digit 0) leaves the resampled text: the "now" row of every sheet.
- Ticker scroll: the ticker moves its strip by a Blt onto itself. Treated as a cover, it dropped the strip's records, so
  only the newest ticker glyph was sharp and the rest stayed resampled (seen in look A, where the TrueType glyph stands
  out). Fixed: a self-Blt moves the records with the pixels (121 to 306 moves per 10 s). After it all 101 HUD glyphs are
  drawn, 0 rejected per frame.
- Ticker end: the glyph the ticker scrolls in at its right end showed 1 to 3 columns, and a stale record matched them, so
  a whole glyph was drawn over the ticker frame. Fixed: a cut glyph needs 60% of its ink visible, and a partly covered
  glyph is clipped to the ink that still matches. Frames in a row at 3840x1984 after the fix: the end glyph is cut at the
  box edge as in the native frame.
- Records follow text changes: bar fields are redrawn on messages, and the old glyphs are dropped by the opaque Blt of the
  field background and by the new-batch rule. Records held stay at 135 to 200.
- Census (`_LOG=1`): every glyph seen came through the text loops `0x100072e2` (bar fields via SIMUI `0x10026B28`, RCI
  letters `0x10064E9B..`, compass `0x1005054C`), `0x1000A586` (ticker, SC3U `0x00444647`) and `0x10007B9B` (box text),
  plus "Cargando..." (SIMUI `0x1002BFFD`).

## Round 2: owner picked look B, letter spacing fixed, RCI bars (2026-10-26)

Look B is the default (`SC3RESIZE_NATIVETEXT` unset = 2).

**Spacing cause.** Glyph positions come from the game's own layout: x per glyph, with the font's advances already in it.
The map dest = a + b x is exact. But the first build put each glyph mask at the rounded dest pixel, so each letter
could sit up to 0.5 px off its true place, and a gap between two letters up to 1 px wider or narrower than the native
gap x factor. **Fix:** look B builds each glyph at its own sub-pixel phase (the fraction of a + b x, 1/8 px steps, both
axes) and places it at floor(a + b x). No position is rounded and nothing accumulates along the string, so the spacing
is the native spacing x factor. `SC3RESIZE_NATIVETEXT_PHASE=0` gives the old placement (used as the control below).

**Measured in-process** on every redrawn letter pair. The metric is the alpha centroid of each drawn glyph minus the
native glyph's coverage centroid mapped by a + b x, taken as the difference between neighbouring letters. Same game,
switched live, 10-s windows:

| case | letter pairs | spacing error mean | max | pairs > 0.5 px |
|---|---:|---:|---:|---:|
| 2560x1351 (2.252x), HUD + scrolling ticker, old rounded placement | 5,659 / 6,083 | 0.308 / 0.341 px | 1.005 px | 1,148 / 1,383 (20 to 23%) |
| 2560x1351, sub-pixel phase | 4,980 / 5,353 | 0.034 / 0.035 px | 0.171 px | 0 / 0 |
| 3840x1984 (3.307x), HUD + ticker + Reunirse, sub-pixel phase | 10,645 / 6,351 / 5,671 | 0.054 to 0.056 px | 0.348 px | 0 |

I also measured the ink-free gap between neighbouring letters, from the first/last column with alpha >= 128 against
the native gap x factor. At 2.252x it is 0.29 px mean and 0.75 px max with the phase (0.48 / 1.25 rounded). At 3.307x
with the dialog it is 0.35 px mean and 2.7 px max in BOTH placements. That residue is glyph shape: in the
anti-aliased dialog font the sharpened edge crosses alpha 128 up to 0.8 native px away from where the native coverage
crosses 0.5. It does not depend on placement.

**RCI bars.** The RCI Draw (SIMUI `FUN_10065214`) makes 3 solid colour fills, which are DirectDraw COLORFILL Blts. While
it runs they are now recorded and redrawn at their exact mapped rect, with partial coverage on the edge pixels, after
erasing the resampled bar. They show only with the sim running (paused Europolis has empty bars; unpaused with the
mod's P key). Measured: fills drawn whenever the RCI area is recomputed, pasted from the cache otherwise.
`SC3RESIZE_NATIVETEXT_RCI=0` turns this off.

Sheets (`owner_shots/`, rows: resampled native text as the spacing reference / look B rounded / look B fixed):

| file | what |
|---|---|
| `11_spacing_ticker_2560_x2.png` | ticker at 2.252x, zoomed 2x |
| `12_spacing_bar_fields_2560_x2.png` | bar fields |
| `13_rci_bars_2560_x3.png` | RCI letters and bars, zoomed 3x |
| `14_spacing_dialog_2560_x3.png`, `15_spacing_dialog_label_2560_x3.png` | Reunirse title and labels; row 2 shows the uneven gaps the owner saw ("sol icitantes"), row 3 does not |
| `16_spacing_max_ticker_bar_1to1.png` | maximized 3.307x, 1:1 |
| `17_rci_bars_max_x2.png` | RCI maximized |
| `18_spacing_max_dialog_x2.png`, `19_spacing_max_dialog_label_x2.png` | Reunirse maximized |
| `20_ticker_scrolling_2560_x2.png`, `21_ticker_scrolling_max_1to1.png` | 5 consecutive frames of long news lines scrolling (sim running), look B fixed |

Seen, not changed (owner call): at 3.3x the thin strokes of the Comic-style title font ("Reunirse" n, i) come out a little
uneven in look B. That is the edge sharpening (gain 0.9 x factor, capped 4) on 1-px anti-aliased strokes, the same in
both placements. A lower gain for the anti-aliased fonts would soften it.

Cost: 2560x1351 HUD with the ticker, 3.5 to 4.4 M thread cycles per frame with the phase against 4.3 to 4.9 M rounded
(no regression; 8 to 62 extra masks built once). Maximized with Reunirse open and the sim running, 179 to 182 glyphs
per frame: 18.6 to 25 M cycles. The PC was shared with other games; the ticker word groups and the dialog text are
recomputed every frame (about 12 groups).

## Not covered

- Main menu and its dialogs (MENUSCALE resamples the 800x600 frame; the glyph records exist, the compose is not hooked
  there).
- Non-text art: buttons, frames, icons (bitmaps). The RCI bars are done (round 2).
- Hover-only tooltips and budget/graph dialogs with a real cursor: needs owner check (posted input only here).
