# avpaint RESULTS (2026-10-28)

Owner report (LAN build sc3mods-2026-10-27f): an avenue on a slope (img1) and an avenue corner (img2) draw the plain
road with a yellow centre line. Save: `dev\avpaint\inst\owner\Big One.autosave1.sc3` (1024 map).

## 1. Cause (task 3, the refusal log)

AVL now logs one line per refused band with the first check that failed. Owner save, load pass:

```
avl: load: band along z from (567,15) rows 0..15 stays two-way: band along z at (567,15): forward end (567,31) 11204.1
     + (568,31) 39.2 is not a U-turn pair, corner or avlj join (neither cell an avlj piece; corner check: no 11203
     inner bend in the end row)
avl: load: band along x from (570,31) rows 0..9 stays two-way: ... back end (569,31) 39.3 + (569,32) 43.0 ...
avl: load: band along z from (580,33) rows 0..9 stays two-way: band along x at (579,31): back end (569,31) 39.3 ...
```

A plain road (x 569, z 33..36) meets the x band's first row right beside the corner at (567..568, 31..32). The stock
tiler puts T 39 / X 43 on that row and links the corner's inner bend and x half through their shared edge (11203/2
becomes 39/2, 11204/0 becomes 39/1). `avl_corner_at` needed an 11203 inner bend, and AVX sees no box there (a T beside
a corner has no straight pair on one side). Corners are all or nothing, so the whole chain (z band 567, x band 570..579,
z band 580 with its U-turn at z 43) stayed stock: straights white-dashed by avenue_markings, every bend and the slope
row yellow. The orchestrator's hypothesis was right.

## 2. Fix: corner + T (task 2, SC3NETMOD_AVLCT=0 off)

AVL accepts the corner block when the row beside it is a T row (39 / 43 with the road on one or both outsides) and
every linked cell and T row cell has an `avlt` piece for its outline / modes (the AVX box-cell letters: one paved
2 x 2 box). The other band starts one row further out; seen from it the T row is its end. Pieces (avenue_lanes 0.3.0):

| id | base | outline / modes (NESW, state 0) | what |
|---|---|---|---|
| 21736 | 39 | ICAI / CCIO | linked inner bend: both lanes turn (avjunc_build.box_spec, corner=True) |
| 21737 | 39 | ICAI / ICOC | linked half |
| 21738..21741 | 39 / 43 / 43 / 39 | as 20817 / 20815 / 20814 / 20816 | T row cells: avenue_junctions box cells under own ids |

21740 / 21741 cover the road on the other outside (not in the owner's save, not seen in game).

Owner save with the fix:

```
avl: load: band along z from (567,15) rows 0..15 -> one-way (ends: join or edge / corner + T)
avl: load: band along x from (570,31) rows 0..9 -> one-way (ends: T row of a corner + T / corner)
avl: load: band along z from (580,33) rows 0..9 -> one-way (ends: corner / U-turn)
avl: load pass over (-2,-2)-(1025,1025): 88 cell(s) written, 0 reverted
```

Live grid (rb_lab cells): (567,31) 21700.1, (568,31) 21736.2, (569,31) 21738.3 / (567,32) 21701.2, (568,32) 21737.1,
(569,32) 21739.1; slope row 25 21718.2 / 21719.2; corner (580..581, 31..32) 21700 / 21701 / 21726; U-turn z 43 21701.

Save + reload: the autosave of that game holds the stock pieces at the block (39/2 39/3 / 11203/2 39/1 43/1, the X
saved at state 1 because the box piece fits it at that state, as AVX box cells do). Reloaded: the same three bands
one-way, 0 cells written (the variant section restored them).

## 3. Fallback look on two-way bands (task 1, AVP block, SC3NETMOD_AVP=0 off)

A band AVL leaves two-way gets look-only twins on its bends, U-turn ends and slope rows: same art as AVL's piece, stock
base, stock two-way lanes, saved as the base. Only cells of a band with at least one straight 11204 row and no
converted cell. Reads see the base (rb_read / hwy_read), so no block decides differently.

Check: the same save with SC3NETMOD_AVLCT=0 (chain refused again): `avp: load pass ...: 6 cell(s) painted` = slope pair
21728.2 / 21729.2, corner 21727.0 x2, U-turn 21727.2 / 21727.1. The corner + T block itself is not painted (by design),
and AVL put its 217xx pieces back to stock. Plain road curves already in the save, (577,17) 11203.2 and (586,10)
11203.1, stay stock.

Lab, same run: a plain road drawn at x 565 (two cells west of the avenue) over the same hill, with a curve at each end.
Its slope (565,28) stays 31.2 and its curves (565,20), (565,30), (566,31) stay 11203 with the yellow line, while the
avenue's slope row stays painted after the edit pass (`avp: edit pass ...: 2 cell(s) painted`).
Frame: `owner_shots\frames\lab_plainroad_z3_r1.png`.

## Pictures

`owner_shots\avpaint_sheet_z4.png`: before (both blocks off = the LAN build) / after (default, one-way) / fallback
(AVLCT=0: two-way with the avenue look), zoom 4, slope at the img1 angle (rot 1), corner at the img2 angle (rot 3),
the corner + T from both sides, the U-turn (the "after" U-turn frame is rot 0). Frames in `owner_shots\frames\`.

## Not done / open

- The corner + T outer bend (567,32) keeps the plain look when the block is refused (AVLCT=0 only). With the default it
  converts.
- Only the owner's T shape (road on the outer side) was seen in game. The road-on-inner-side shape uses 21740 / 21741
  and the stock tiler's linking there was not measured; if it links differently the block is refused with a logged
  reason (stage "no avlt piece fits a cell").
- Traffic over the new box was not observed (light testing). Lanes: 21736 = 2 lanes N -> E turning, 21737 = 2 lanes
  straight, both from avjunc's generator; the copies are the shipped box cells.
