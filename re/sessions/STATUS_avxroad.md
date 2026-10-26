# STATUS avxroad (owner report on LAN build sc3mods-2026-10-25d = main 9825dc4)

Owner: "this intersection on avenues are not merging properly" (MAIN verify/avxroad/owner_shots/
img1_avenue_x_road_not_merged.png), and "on berlin this road looks wrong" (img2_berlin_avenue_48_183.png).

## state
2026-10-26: DONE (img1 + img2 Berlin, traffic checked). Cause found (sent), fixed in game, save + reload identical, no-mod load stock. All my games stopped.
Results: worktree Simcity_wt_avxroad verify/avxroad/RESULTS.md. Sheet: MAIN verify/avxroad/owner_shots/avxroad_sheet.png.

## goal
Avenue x road junctions form, with lanes per the avlanes rules, in both drag orders and both axes, and survive save + reload.

## cause
img1 = two roads meeting the avenue from opposite sides ONE position apart (yellow lines 130 px apart, road 129 px
wide). The STOCK tiler drops both T's (measured with no netmod), so each road ends with an arm into a straight half.
AVX saw no feature, and AVL converted the stretch as plain band 21700. img2 Berlin (48,183) = one road dangling into a
half, same family.

## design / built
sc3netmod_avx.c `avx_drops` (task avxroad, SC3NETMOD_AVXDROP=0): a straight half whose outside neighbour is a plain road
(29 / 39 / 43 / 11203) with an arm toward it is re-read with that arm (avx32's virt). The box forms from existing
pieces (20815 / 20817, mirrored 20814 / 20816, noses 20801 / 20802). Twin avjunc_rule.dropped_tees, and avl_bands made
to ignore the re-reads like the C AVL block.

## ids taken
None. No new piece ids, no lane curve shapes, no table lines.

## proven in game vs offline only
- In game: offset pair both orders, both offsets, both axes, avenue-first and road-first. Save (106 tiles as base) and
  reload identical, load passes write 0. Save loaded without netmod = stock ids, roads joined. Final DLL edit check.
  Berlin load boxes (48,183), 54 re-reads (= twin).
- Offline, 16 shipped cities: 106 new boxes, 24 replaced by bigger ones, 0 lost, 0 band cells lost, +152 converted.
  Edge check 125 -> 101 mismatches (the 23 `nose C|T 29` gone).
- Traffic (orchestrator ask): Berlin, 300 s at speed 4, 51 sites: fix on 4,603 trips cross, 45 sites; AVXDROP=0
  1,126 trips, 7 sites (only where the half stayed stock 11204, which the stock router crosses without matrices).
  The 6 sites not crossed are a dead-end stub plus 5 with another way out; those 5 are real boxes.
- Berlin img2 (48,183): before the fix no block writes those cells on load, and stock and the LAN build look the same,
  so the stub is the stock tiler's layout. The fix boxes row 183 (W road joins, trips use it). Row 181 (diagonal road 35
  T beside the 11203 curve) stays stock: diagonal-road work, separate task.
- Clean loads with the fix: Berlin, London, Seoul load and run 60 s, no new fault; re-reads 54 / 36 / 10 = twin.

## blocked on
(none)

## files owned (worktree Simcity_wt_avxroad, uncommitted)
- re/harness/src/sc3netmod_avx.c
- re/tools/netmod/avjunc_rule.py
- re/tools/netmod/avxroad_trips.py (new, read-only trip probe)
- verify/avxroad/RESULTS.md
- MAIN: re/sessions/STATUS_avxroad.md; verify/avxroad/owner_shots/*.png (pictures, not committed: avxroad_sheet.png,
  before_*, after_*, nomod_load_offset1.png; img1 / img2 / img2_queryid.txt are the owner's)

## instance
Simcity_stock_avxroad\re\harness\inst_avxroad (lab2_saved.sc3 = the saved lab, berlin1.sc3), inst_avxroad_off (stock
and AVX/AVL-off comparison games). version.dll built into the tree's Apps. PIDs 21496, 23280, 6976, 15464, 19840, 19336,
28048, 11576, 18412, 14524, 13592, 28060, 30380, 22652, 29704, 27256, 17108, 13048, 21732, 14988: all mine, all
stopped. Extra instance inst_avxroad_b (AVXDROP=0 copy). Trap: shared Apps\DUMP answers any game; use
SC3RESIZE_FRAMEDUMP per instance.

## needs owner
- Look of the 2-position box for offset roads (sheet), and of Berlin (48,183).
- Behaviour change: any city with this stock pattern now gets the junction on load (shipped cities: about 80 pairs +
  30 single roads), so those roads connect to the avenue where stock left them unconnected.

## asks of other streams
(none)
