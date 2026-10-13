# netramp: results (2026-10-13)

PRE: `verify/netramp/PRE.md` (commit before any run with the pack). Analysis: `re/analysis/NET_RAMPS.md`.
Tree `Simcity_stock_netramp` (hard links of Simcity_stock, stock DLLs, Spanish; `link_tree.py --verify` after the
uninstall: 3,488 linked, 0 de-linked). Instances: `re\harness\inst_netramp` (mods_launch -multi, sc3resize for the
in-process frame DUMP, sc3netmod from this branch), `re\harness\inst_nrstock` (mods_launch + sc3resize only, no
sc3netmod). Fixture package `example_ramp_variant` installed in overlay mode for the pack arms, uninstalled for the
stock arms. All building through the game's own tools (menu commands from MenuItem.INI, posted input, cells found by
hovering the On-ramp tool, `nramp_view.py`); camera through the game's camera calls (`nramp_cam.py`). Cell reads are
live Frida reads (`np_drive.py cells`). Saves, frames and cell dumps stay in the instance folder (not committed).

Arms A0..X ran on the netramp-only build (round/1012 + this task). After the rebase onto child/netbridge the C arms
re-ran the key checks with both DLL blocks (netbridge INHERIT/XCROSS + NETRAMP) and netbridge's variant inheritance in
place of this task's first `mirror_base` (byte-identical TilingRules files, 9 of 9).

| arm | setup | result | prediction |
|---|---|---|---|
| S0 | stock data, sc3netmod without NETRAMP | strip 15139.0/15135.0/15131.0 at x 102..104 z 143, road (101,143) 15046.2, lane 15120.0/15116.0/15147.2; FUN_1000abde returned 1 with 3 points | baseline |
| A0 | NETRAMP DLL, no pack | log `ramp: 0 slot(s) changed`; cells = S0; other side (103,146): 15138.0/15134.0/15130.0, road 15045.2, lane 15119.0/15115.0/15148.2 | met |
| A1 | pack, NETRAMP DLL | log 6 `ramp: onramp slot` lines + `3 variant id(s) classified as their base`; strip **25139.0/25135.0/25131.0**; 25139 class SIMNTWRK+0x2a020 (kind 14, as 15139), 25135/25131 SIMNTWRK+0x29e74 (kind 15); every other cell of x 96..108, z 139..150 = A0 | met |
| A2 | A1 game, other side | 15138.0/15134.0/15130.0 (slots 15-17 not in the pack); whole grid = A0 except the 3 variant cells | met |
| R | A1 game | green at zoom 0..4 (r0) and at 4 rotations (z3, z4), one continuous ramp, the stock ramp grey, no missing tile (`shots\R_*.png`, `R_sheet.png`) | met |
| S | A1 game, Save | file: the 3 cells hold 15139/15135/15131, section 0x4E56 with the 3 entries (`netvariant.py scan`); log `save: 3 variant tile(s) written as base` | met |
| S-stock | inst_nrstock (no sc3netmod in the process), pack uninstalled, load S's file | strip loads as 15139/15135/15131, grey, base classes | met |
| S-mod | pack + DLL, load S's file | `load: all 3 variant tiles restored`; green; base classes | met |
| B | A1 game, Demolish (0x1000400A) on (103,143) | both strips go, the highway cells x 104..105 of both lanes go (ends 15054/15053 at x 103 and 106), the road cells (101,143) and (101,146) go back to 29.1 | met |
| B0 | stock instance, same Demolish on the stock strip | **identical grid to B** (diff empty) | control |
| X | `SC3NETMOD_RAMPS=0`, pack installed | strip 15139/15135/15131 (stock): the table lines are the only way in | met |
| C1 | combined build (rebased), pack, both strips | grid = A2 exactly, same classes | met |
| C-save / C-load | combined | file: bases + 3-entry section; reload: `all 3 variant tiles restored` | met |
| C-B | combined, Demolish (103,143) | grid = B0 | met |
| T | Frankfurt, pack + combined DLL: variant strip x 122..124 z 96 (25139/25135/25131) and stock strip x 118..120 z 96 at the same crossing; road (121,96) became 15047.0; 150 s of sim at speed 4 | **not measurable**: `surf_live` and `surf_snap` read 0 on every on-ramp and highway lane cell before and after, the old stock on-ramps of the same interchange (z 99) included; the road cell (121,96) went 0 -> 136 | exploratory; same limit netbridge hit (its H5) |

Offline (same session):
- `netramp.py check-saves`: 601 / 601 straight on-ramp strips of the 16 shipped cities predicted exactly (plus the 2
  of A0's save).
- `netramp.py build-onramp` from A0's pre-build state: 0 of 80 cells differ from A0's in-game save; with the pack's
  merged rules and table it gives the A1/A2 grid; with only the Set membership (no Protected / Convert) the HWAY
  retile turns the variant strip into highway pieces (simulated, not run in game).
- `netrules validate` (ROAD, HWAY, 16 cities): 99.83% / 99.71% before and after; HWAY interior 21 + near-slope 8 ->
  onramp-area 29, ROAD classes unchanged (NET_RAMPS.md 4).
- `netpack.py selftest` on the rebased branch: 0 failures (U1..U10). `netramp.py selftest`: 24 PASS.

Stock quirk met during setup (not an arm): after a few hundred On-ramp tool hovers the tool selects nothing (cost
$0, click returns 0 points) until a road drag tool is hovered: the global point cap `DAT_100322a4 < 0x200` in
`FUN_10004754`, reset only in `FUN_1000488d`.

Not covered: corner on-ramps (`onramp_corner`), tunnels and slope pieces in game (exposed and patched the same way,
no in-game build), traffic over the variant strip (oracle reads 0 on highway cells), 1024 cities, the release layout.
