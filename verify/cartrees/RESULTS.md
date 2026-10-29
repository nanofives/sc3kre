# cartrees: cars drawn over the avenue median trees (2026-10-28 / 29)

Owner report: "some cars are rendering over the trees" (owner_report.png). Workspace dev/cartrees, branch child/cartrees
(fast-forwarded to main 783a8ba by the orchestrator). Owner call 2026-10-29: option A, stock 11204 included.

## Cause (stock behaviour, the mod reproduced it unchanged)

Stock 11204 draws each half's two median trees itself. In the slots where they stand at the half's back edge (0, 3)
they are only in layer 0 (stock `l1_z4_r0` / `r3` are 4x4 empty). Both halves are first-pass cells (draw flags
0x10008181), and SIMSPR `0x1000dc17` paints first-pass records before every sorted record. So the near half's trees
were under every car, and a car on the far half standing behind them was drawn over them. The far half's trees are also
in layer 1, a sorted record with layer byte 2. When footprints overlap, the comparator `0x1000c7a6` draws it after that
half's cars, which is correct. Measured live in a stock game and in the modded game (display-list dump, same records);
detail in re/sessions/STATUS_cartrees.md and re/analysis/NET_ART.md 8.2.

## Fix (data + one small AVP change)

- `avenue_markings.py build PACK --trees` (avenue_lanes only): 11204's layer 1 in the two far-half slots (1, 2) also
  carries the partner half's trees. They are cut from 11204's layer 0 in slot (r + 2) % 4 (the pixels outside the ground
  diamond) and placed one cell over (slot 1 down-left, slot 2 down-right). Layer 0 is unchanged. Offline check: with no
  car, the two-cell picture in game draw order is pixel-identical to stock at all 5 zooms and both slots (diff None x 10).
  Built from the user's own game frames at install, like the markings art; nothing from the game is in git.
- avenue_lanes 0.4.0: 21700 uses that art (its png_dir art/11204). New **21742** = look-only twin of 21700 (`avlp 21742
  21700`, base 11204, stock two-way lanes, saved as 11204).
- sc3netmod AVP block (`sc3netmod_avp.c`): straight rows of a band AVL leaves two-way now get the straight's twin when one
  is declared. Off: `SC3NETMOD_AVPSTRAIGHT=0` (straights stay stock 11204, as before). This is how "stock 11204
  included" is done: the art assumes the mirrored half across the median, which holds for every band row but not for
  every 11204. In the shipped cities 90.85% of 11204 halves face the mirrored half; 6.88% face a road T (39), 1.63% an
  11203 end, 0.55% a plain road (29). A blanket 11204 reskin would have put phantom trees on those.

## In game (dev/cartrees/tree, Seoul, zoom 4, light check)

| check | result |
|---|---|
| far half, inner lane (v 175), 8 cars caught by a display-list trigger | all behind the median trees (owner_shots/cartrees_after.png top row) |
| far half, curb lane (v 80), 6 cars | behind the trees |
| near half, inner lane (v 80), 6 cars | still drawn in front of the trees |
| dirty-rect edges: full frame after traffic ran, view rotations 0 / 1 / 2 | no stale fragments, no missing or doubled trees (after_seoul_avenue_full_frame.png, after_view_rot1_rot2.png) |
| two-way band (122, 236), log `avp: straight rows painted (twin 21742)` | its band rows are 21742 (live grid); (122, 238) facing a road T 39 stays 11204 (after_twoway_band_21742_122_236.png) |
| load pass | `avl: 1526 cell(s) written`, `avp: 580 cell(s) painted, 0 given back` |
| boulevard middle row: lab boulevard x 143..154 rows 205..207 (bulldoze + two road drags) | far middle lane (z 14) behind its trees, near middle lane (z 241) in front, far outer row clear of them: no opposite problem, **no change** (cartrees_after.png bottom row, boulevard_lab_seoul_143_206.png) |

Before pictures: owner_shots/cartrees_stock_vs_mod_before.png (stock game and main 1f17791, same case).

## Scope: pieces

Fixed: 21700 (converted bands), 21742 (straight rows of two-way bands, i.e. stock 11204 inside an avenue band).

Left exactly as now:
- stock 11204 cells outside any band row (for example a half facing a road T 39)
- the avenue_markings reskin of 11204
- U-turn ends / corners 21701, 21726 and their twin 21727 (single layer, trees in layer 0)
- crossings and slopes 21710..21725 and their twins 21728..21735
- AVX junction pieces 20800..20804, 20810, 20811, 21771..21778 and the BVX noses 20910 / 20911
- diagonal avenue 20500, 21800, 21801 and the diagonal boulevard pieces (209xx, 210xx, 21901, 21917)
- boulevard 20701..20703 (checked in game, fine) and the boulevard narrowings 20751..20767
- stock 67 / 71 / 11258 / 15098 (layer 1 in all four slots, a different pattern)

## Installed

`stage\src`: avenue_lanes 0.3.0 uninstalled, 0.4.0 installed from `dev/cartrees/wt/re/tools/netmod/examples/avenue_lanes`
(its art/ = stage's art plus the 10 new `l1_*` frames and an anchors.json for them). The stage overlay, ledger and table
are byte-identical to the tree tested above. Backup of the 0.3.0 pack and ledger: this session's scratchpad. The
release needs the new sc3netmod.dll (AVP change). With an older DLL, 21700 still gets the fix and two-way straights stay
stock.
