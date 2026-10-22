# STATUS_hwlight (child of "SC3: owner hand-test bugs 10-21 (highways + avenues)")

## goal
Owner img11 (main a89ecef LAN build): ramp / interchange embankment walls on the shade side are drawn in the
light wall colour. Every ramp / interchange wall must use stock shading for its facing, all 4 rotations.

## state (2026-10-21)
- cause found, sent to the orchestrator.
- FIXED: twins for all five packages (184), engine mapping, manifests, art; installed in my tree.
- in game: hwave turn 0 + turn 3 (4 views, save + reload), hwt T at turn 1 (4 views, saved).
- in game 2026-10-21 (noinject loader): hwx, hwdx (case A + B r1), hwdd, hwave diagonals, 4 views each, loaded from the
  streams' pre-fix saves (load pass healed 68 / 162 / 60 / 12 cells to twins), hwx saved + reloaded (208 restored,
  0 written 0 reverted). CHECKED, no fix needed. Detail: worktree verify/hwlight/RESULTS.md, frames MAIN
  verify/hwlight/owner_shots/hwlight_ingame_hw*.png. Defender 0 new detections.

## cause
Stock wall shading follows the wall's WORLD axis: outer walls toward +-x (73) read ~135 grey in every view, toward
+-z (15051) ~78 (`hwpaint.py lit`). A piece's frame is shared by (state + view), so art painted at state 0 is only
lit right at states 0 / 2. The blocks write one painted set at all four states:
- hwave (highway_avenue 21600..21609, 21850/21851): state = turn k 0..3  <- img11
- hwt (all 57 pieces): state = the T's turn r
- hwx ramps 21120..21136: state = quadrant
- hwdx ramp-only classes (68 ids): one id for both parities
- hwdd land ramps (30 ids): states 0..3
No single art set can be right at both parities (same frame, opposite shades), so the fix needs new ids.

## design (the fix)
LIT TWIN per piece written at odd states: same base / lanes / turn matrix / hwrc class, art painted from the scene
turned one state (hwpaint.turn_scene + paint_twin, frames relabelled r -> r + 1). Engine: `hwyl <piece> <twin>` lines;
rb_read / hwy_read report the twin as its piece (blocks unchanged), hwy_put / hwy_end re-place / hwave_write / AVL's
writer put the twin at odd states (hwlt_want), HWLT_LIT on a read value makes a writer re-put a wrongly lit cell (old
saves heal on load). Saves use the piece's own hwyp / hwys entry (hwy_piece maps twin -> piece).
Ids 26000..26399 (free in every worktree; 24000..24999 are bvlanes curve shapes):
hwave 26000..26011, hwt 26020..26076, hwx 26080..26096, hwdx 26100..26167, hwdd 26180..26209.

## proven in game vs offline only
- offline: `hwpaint.py lit` (twin of 73.0 / 73.2 / 15051.0 / 15051.2 vs the stock piece the engine shows there: near
  0.975, against 0.325 for the state-0 art at state 1); hwlight.py check (twin geometry = piece geometry, worst 2.4%,
  a cut-face sliver); hwave repaint = shipped art (240/240 frames identical).
- in game hwt: T at turn 1, 4 views, saved (hwlight_ingame_after_hwt_turn1.png).
- in game (instance inst_hwlight, lab_hwl2.sc3): hwave turn 0 (along z) and turn 3 (along x, twins 26000/26001/26010/
  26011 written), 4 views each, saved (40 variant tiles) and reloaded (40 restored, hwy load pass 0 written 0 reverted).
  Frames: MAIN verify\hwlight\owner_shots\hwlight_ingame_after_x.png / _z.png.
- Seen twice: the known latent deadlock (memory project-avenue-lanes: SIMSPR waits SIMCITY+0xd31d, render thread waits
  SIMSPR+0x54f3d) when rotating the view through Frida with the sim running. Workaround used: pause, rotate with the
  minimap button, grab with sc3io. Not caused by this change (same stacks as the avenue-program reports).

## orchestrator asks (2026-10-21, after the build) and answers
- ids: 26000..26399 granted by the orchestrator.
- no-mod load: both saves read with tiler.City.load hold 0 tiles with an id >= 20000. The hwave turn-3 cells save as
  15054.2 / 15053.2 + 11203.3 / 11203.2 (= hwave RESULTS' stock ends), turn 0 as 11235.0 / 11237.0 + 11203; the hwt T at
  turn 1 as 15099.1 land + stock 73 / 15051 (= hwt's own turn-1 saves). Twins save exactly as their pieces.
- capacity: twins add no hwyp / hwys / block-table lines (HWY_MAXP 4096, HWT_MAXC, HWX_MAXC, HWDX/HWDD tables
  untouched); g_hwlt_t / g_hwlt_p, g_base, g_rampcls are 65536-wide; the tree loaded 864 variants, no ### line.
- read-back: blocks only see cells through rb_read / hwy_read (both map twin -> piece), claims are by cell, reverts
  remove the real occupant, the load pass reads through hwy_read. sc3undo replays the logged occupant objects
  (Insert <-> Remove), not ids: it restores exactly what the cell held; a wrongly lit cell is re-put by the next pass.
- Defender / noinject: my in-game runs above were done before the "do not launch" message. No launch since.
  In-game check of hwx / hwdx / hwdd / hwave diagonals: DONE 2026-10-21 with the noinject loader (see state).

## blocked on
- nothing.

## files owned (worktree Simcity_wt_hwlight, uncommitted)
- re/tools/netmod/hwpaint.py (lit twins section, `lit` CLI)
- re/tools/netmod/hwlight.py (new)
- re/tools/netmod/hwave_paint.py (diag_render base=), re/tools/netmod/hwave_build.py (twart)
- re/harness/src/sc3netmod_rbt.c (hwlt table + rb_read), sc3netmod_hwy.c (hwyl line, hwy_piece, hwy_read, hwy_put,
  re-place), sc3netmod_hwave.c (hwave_write), sc3netmod_avl.c (writer)
- re/tools/netmod/examples/<5 packages>/lit_twins.json (new), manifest.json, README.md
  (highway_avenue, hwt_trumpet, hwx_cloverleaf, highway_diagonal_cloverleaf, highway_dd_cloverleaf)
- verify/hwlight/RESULTS.md (new)
- .gitignore (allow examples/*/lit_twins.json)

## instance
folder Simcity_stock_hwlight\re\harness\inst_hwlight, last PIDs 70092, 36892, 37000, 33120, 32488, 19548 (all mine, all stopped; mods_launch.exe rebuilt from main d7d114b). Saves lt_hwx / lt_hwdx / lt_hwdd / lt_hwave.sc3 (copies of the streams' labs; lt_hwx re-saved after the heal), lab_hwl2.sc3 (hwave both axes), lab_hwl3.sc3 (hwt T at turn 1). Tree has a netpack ledger + packs
copied from Simcity_stock_avint (the release source) so packages can be reinstalled.

## needs owner
Pictures: verify\hwlight\owner_shots\ (cause sheet, offline before/after, in-game after).

## asks of other streams
none
