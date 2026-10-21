# avrbtfix: "adding a road turns the avenue into roundabouts" (owner img4 / img5, 2026-10-21)

Pictures: `MAIN\verify\avrbtfix\owner_shots\` (frame dumps, zoom 3).

## Cause
- The owner's avenues are diagonal in world terms (vertical on screen). DAV converted them (img4).
- The added road made rows of 4 cells, which is a diagonal boulevard band. DBV refused the band, so its cells kept the
  stock tiler's ladder 11203 / 43 / 43 / 11203. Vanilla SC3 (no sc3netmod) draws the same column of circles
  (`vanilla_same_ladder.png`, yellow lines). Ours has white dashes only because avenue_markings re-skins stock 11203
  (`repro_mod_ladder.png`, `repro_stub_ladder.png`). No block wrote roundabout pieces: that pass logged no rbt, dav,
  dbv or avl write.
- DBV refused for two reasons, both in `dbv_end_kind` (sc3netmod_dbv.c):
  1. If one drag sticks out one row past the others (any hand-drawn stagger), the end matches no known kind. In game
     the log says "top end: the roads past the band are not an end this package knows".
  2. A plain cap required six empty rows past the end. Any unrelated road within six rows refused the band (measured:
     a road 3 rows below the end, not touching it). img4 has a curved road just below the right avenue.
- With a third road whose ends line up with the avenue, DBV already converted (`aligned_third_road_dbv_ok.png`,
  third road on either side).

## Fix (sc3netmod_dbv.c, offline twin diagbv.py `classify_end` / `_one_band`)
1. A cap needs only the rows its stamp writes plus one empty row (orchestrator's call; first build had two). A road that touches the band or its stamp still
   refuses ("touches road").
2. Any other end shape is RAGGED. The band converts, and that end's rows stay with the stock tiler (the end row is
   treated as an end row, road cells 1..2 rows past it are path). New log suffix: ", one end left to the stock tiler
   (shape not known)". These still refuse the whole band as before: a narrowing whose avenue will not convert (bvlanes
   lane rule), a road beside the end row, fewer than 3 clean rows, and junction or stamp conflicts.
No new piece ids, no table or package change.

Behaviour change the owner did not report: two diagonals drawn two cells apart (rows of 4 cells with a gap at the ends)
used to stay a stock ladder unless their ends were square. Now they convert with ragged ends (offline case
"two drags two apart").

## Checks
- Offline: `py -3 diagbv.py check`: 0 case(s) off (every footprint case of the twin, both axes, first step along x and along z).
- In game (lab, all 8 mods built from the worktree, test tree = Simcity_release copy):
  - owner-like case: two diagonal avenues (DAV), then a third road one row off at both ends on the left avenue, and
    one row short at one end on the right avenue. Both became diagonal boulevards, each with one ragged end
    (`fix_2_third_road_staggered.png`, `fix_2_ends_zoom.png`). Before the fix, the same stagger gave the ladder.
  - unrelated road 3 rows below a cap-part end: band kept, nothing reverted (`fix_3_unrelated_road_below.png`).
  - other diagonal axis, staggered third road: converts (`fix_4a_axis1_avenue.png`, `fix_4b_axis1_staggered.png`).
  - save + reload: 132 variant tiles restored, the three bands seen intact, 0 rewritten. View rotation 1
    (`fix_5_reload_rot1.png`).
- Other drag order (rebuilt DLL with the one-empty-row cap rule): the third road first, then the two avenue roads, on
  both bands. Same result as the forward order: 47 and 48 cells, one ragged end each (`check_1_third_road_first.png`).
  On the way, the first two drags of the left band (two cells apart) already converted with both ends ragged (44 cells),
  then grew to 47 with the next drag.
- No-mod load of that save (instance with sc3resize only): the city loads, every cell holds a stock id (35, 43, 11203,
  11225, 39; no variant id), the boulevards show as their saved base pieces (`check_2_nomod_load_fixed_save.png`). A
  save made with the pre-fix DLL (aligned boulevards) looks the same without the mod (`check_2_nomod_load_prefix_save.png`):
  the broken-looking cap edges are DBV's existing save-as-base design, not this change. Ragged ends load as plain stock road.

## img4 "one end did not convert" (report only)
In my reproduction both diagonal avenues converted whole (DAV "38 written", no refusal). Where the two drags' last cells
stagger, DAV's end rows use the stock lone-staircase pieces by design, which reads as a stock end. Not changed.

## Look the owner should judge
A ragged end shows a small stock road end (a rounded half-loop, or a short stock road with a yellow line) next to the
boulevard's curb (`fix_2_ends_zoom.png`). Painted caps for these shapes would need new pieces; none were built.
