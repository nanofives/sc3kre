# avrbtchain: "This is not turning into an avenue" (2026-10-31 / 11-01)

## Cause
Not RBT and not a 2-wide straight strip. The owner's strip is a DIAGONAL band, 3 cells per row, (576,99)..(585,106) on
"Big One". It joins the straight avenue x 576/577 (z 83..98) to the straight avenue x 584/585 (z 107..). The DAV block
refused it every edit, and that refusal left no line in the log. The refusal is the avdiag program rule (STRAIGHT_OK,
sc3netmod_dav.c): a diagonal that bends into a straight avenue converts only when AVL converts that straight. AVL kept
the upper straight two-way because of its far end (z=82: a plain road crossing where the boulevard 575..577 narrows
into the avenue, slope 32 at (578,82)). So the band stayed the stock 43/11203 ladder, which draws as a chain of
circles. Evidence: owner log `stats: dav ... left two-way for a straight avenue=9 -> 141`, `rbt ... blocks
converted=0`. The owner autosave in this tree logged:
`dav: load: band axis 0 from (576,99), 8 row(s), left to the stock tiler (the 43/11203 ladder): the straight avenue it
bends into at (577,98) stays two-way (post-AVL)`.

## Fix (owner call A, 2026-11-01): DAVTWO, the two-way diagonal avenue look
- Package diagonal_avenue 0.7.0: variants **21830..21835** = two-way twins of the middle pieces 20500..20505. Same base
  and art dirs (no new art). Lanes: two_21830..21834.lanes.json are the pre-avdiag two-way specs (8e44a0e^), the union
  of the two stock roads' lanes, with stock path keys (match stock 35 in both languages). 21835 (twin of the outer piece
  20505) has no spec, so stock 35's lanes (copy_base). `davw <twin> <piece>` lines in avenue_lines.
  `selfblock.py`: 0 of 5 specs self-block. `netpack.py validate`: exit 0. The twins get the same first-pass warnings
  as 20500..20505.
- sc3netmod_dav.c (own block, `task avrbtchain`, off `SC3NETMOD_DAVTWO=0`): when the ONLY refusal is "the straight
  avenue it bends into stays two-way", a band with no junction, arm, stub, merge, crossing or touching road is written
  with the lone stock pieces plus the twins, without the one-way roles. Bands with side roads stay as today (ladder,
  now logged). Readers see the twin id (not an avlj join), so a straight avenue ending on it stays two-way too: the
  whole group is two-way (program rule, all-or-nothing per connected group). Post-AVL: twins written or a twin band
  beside a one-way straight -> AVL re-decides that straight (it goes two-way). Twins save as their pieces (43 middle,
  35 outer). Orphaned twins revert like other DAV pieces.
- sc3netmod_rbt.c: `davw` dispatch. sc3netmod.c: the variant-table reader skips `davw`. netpack.py + schema: `davw` is
  an accepted avenue_lines kind.
- Kept from the cause round: the log line for the silent refusal.

## Checks (dev/avrbtchain tree, posted input only)
| case | result |
|---|---|
| owner save "Big One (auto 5 min)" load | band written with twins (24 cells), `DAVTWO` log; both straights two-way (AVP look) |
| owner save, autosave + reload | save: middle 43 / outer 35 + section entries 21830 / 21835; reload: 720 restored, DAV 0 written |
| owner save, `SC3NETMOD_DAVTWO=0` | ladder as before, refusal logged |
| fresh, real Road tool (Roadless Paradise 42..52, 12..37): avenue + 2 joined diagonal drags + avenue | both straights one-way, diagonal one-way DAV pieces (unchanged path) |
| same + one road running on past avenue B's end | B refused -> diagonal twins (DAVTWO) -> post asks AVL -> A goes two-way too; 1 re-run, no "still asking" |

Pictures (verify/avrbtchain/owner_shots/):
- before_owner_save_ladder.png: the owner's chain of circles, reproduced.
- after_owner_save_davtwo.png: same view, diagonal avenue look.
- lab_control_oneway.png: fresh build, one-way group (control).
- lab_davtwo_twoway.png: fresh build with the blocker, two-way look group.

## Behaviour change to note
In the owner's save the LOWER straight avenue (x 584/585) used to convert one-way next to the ladder. Now it stays
two-way because its end is a two-way diagonal (the group rule). It draws the same (AVP look), but its cars are two-way.

## Not done
- Cars not traced on the twins (light testing). The lanes are the pre-avdiag specs, which drove in game before avdiag.
- English-UK: the twins use stock path keys, so they follow stock 35 (left-hand in UK), like every two-way stock road.
