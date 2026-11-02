# STATUS hudpos (round 2026-11-02b)

## goal
Owner: move "Visitar Bolsa de SimCity" near the minimap, move "?" a little left, give the picker button a clean background.

## verdict
DONE, one in-game check (Berlin, tree dev/hudpos): 800x600, 1600x900, 1920x1040 (HUD Auto x1.733). Pictures: verify/hudpos/owner_shots/.
- **Bolsa**: the globe tab + plate in the RCI raster moved +18 px (to the RCI's right end, flush with the minimap edge), the
  stock 0x7d1 link button moved with it (log `HUDPOS> Bolsa button local [7 0 40 30] -> [25 0 58 30]`). Block in
  sc3resize_rcibars.c rcb_widen. `SC3RESIZE_HUDPOS_BOLSA=0` = stays on the left. Needs RCIBARS on (it lives in that code).
- **"?"**: 8 px left (kid [547 11 587 50] native, found by size/x range in rz_bar_children_right). `SC3RESIZE_HUDPOS_Q=0` off.
- **Picker button**: its art is the zoom-out strip, whose outer ring is a soft shadow baked against the LIGHT top of the panel.
  In the darker bottom-left corner it drew a light octagon. Ring now flood-filled from each frame border through blue pixels
  (b - r >= 64, b >= 0xb0) and made transparent (pkr_from_minus). `SC3RESIZE_HUDPOS_PKR=0` off.

## known leftover (not a regression of this block, exposed by moving "?")
A 2 px dark vertical line at console x 579..580 right of the "?" (flat 181c28, both sizes). Before, the "?" shadow hid it. It is in the
bar/console art, not in a button. Left alone; fix would be repainting those columns of the bar art or moving "?" less than 4 px.

## proven game-side vs static only
Game-side: all above. Not tested: click on the moved Bolsa button (opens a web link, not clicked), English install, second city load.

## blocked on
nothing

## files owned (worktree dev/hudpos/wt)
- re/harness/src/sc3resize.c (g_hudpos_* globals after g_rci_nat_ok; '?' shift + kid logging in rz_bar_children_right; ring flood in
  pkr_from_minus; 3 env lines after SC3RESIZE_RCIBARS_LOG)
- re/harness/src/sc3resize_rcibars.c (IGNORED by .gitignore: `git add -f`): Bolsa art + button move in rcb_widen
- re/sessions/STATUS_hudpos.md, verify/hudpos/owner_shots/*.png (do not stage pictures)

## game-harness need
none

## update (merge with main, vdcolors/vdcolors2)
- Conflict in sc3resize_rcibars.c resolved by taking main's file and re-adding only the two HUDPOS_BOLSA blocks (art move after the
  column-0 key loop, 0x7d1 button move before rcb_button). git diff main on that file = +16 lines. Not committed.
- Dark line right of "?": new `hudpos_art_patch()` in sc3resize.c (before rz_bar_children_right, called from it): console art [0x2a]
  columns 579..580, rows 8..55, set to RGB565 0xCE9F (c8d0f8) under a balanced lock, once per surface. Off with `SC3RESIZE_HUDPOS_Q=0`.
  Art column 581 is dark too (the RCI hides it), so copying it did not work; rows 0..7 are the lip and are kept.
- Checked at 800x600 and 1600x900 with the merged layout: owner_shots/4_merged_antes_despues_800x600.png, 5_merged_1600x900.png.
