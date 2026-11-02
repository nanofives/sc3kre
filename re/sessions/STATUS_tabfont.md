# STATUS tabfont (2026-11-02)
goal: smaller caption font on the 7 Cuadros tabs only (Graficas tabs keep font 0xf).
verdict: done. Cuadros strip uses factory font id 0x11 (vt+0x14), Electricidad-width table says 54 px vs 68 in 0xf (Ciudad 33 vs 39), cell h 17 vs 14, regular weight instead of the bold look of 0xf. Layout widths now come from the font's own glyph table (font obj +0x14, cell char*0x14, advance at +0x10 [CONFIRMED @ GZServiceD 0x10006e54, HUD_SCALE.md]) via vt_font_w, so padding/centering match; 0xf keeps the old per-character estimate (the table reproduced the measured 39 px for "Ciudad").
Font probe (SC3RESIZE_VDTABS_LOG=1 logs "font probe id ..."): 0x00/0x0b = 54, same face as 0x11 (cell h 14); 0x01/0x02/0x0e = 68 (h 16, same width as 0xf); 0x03/0x0c = 73; 0x0d = 92; 0x10 = 126. No same-bold-face smaller one exists, 0x11 is the nearest.
switches: SC3RESIZE_VDTABSSMALL=0 old font; SC3RESIZE_VDTABSFONT=<id> other font.
proven game-side: Berlin 2560x1351, Cuadros and Graficas, SMALL=0 vs 1. Pictures verify/tabfont/owner_shots. Tab clicks not re-tested (button rect code untouched).
files owned: re/harness/src/sc3resize_vdtabs.c, re/harness/src/sc3resize_vdbars.c, re/sessions/STATUS_tabfont.md, verify/tabfont/
blocked on: nothing.
