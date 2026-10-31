# cyantri: cyan triangles on diagonal avenue / boulevard edges (2026-10-31)

Owner request 2026-10-31: "Fix the cyan triangles on diagonal edges." Evidence was the avdiagbreak pictures
(`verify/avdiagbreak/owner_shots/`): triangles at zoom 3 on the outer cells of diagonal avenues (20505) and on the
west edge of diagonal boulevards (20950). Branch child/cyantri (from main b6ad384), tree `dev\cyantri\tree`, city
Roadless Paradise.

## Verdict

The triangles are not in the package art, the piece choice or the terrain-under bit. They come from the lab's build
call, `nb_drive.py build()` (used by `avdb_lab.py avenue / dboulevard / stair`). Pieces drawn with the game's own
Road tool never show them, and a saved city shows none after a reload. So the owner has only seen them in lab
pictures. Fixed in `nb_drive.py`. No mod code, no art, nothing for `stage\src`.

## Evidence (in game, PIDs 5996, 13184, 9524, 18916, 23508, 19296)

| case | zoom 3 highlight-colour pixels (0,120,152 / 0,104,136) in the land area |
|---|---|
| avenue + boulevard built by avdb_lab, same session | west-edge triangles (owner's pattern) |
| plain STOCK diagonal road (35) built by avdb_lab stair | 13,669 at zoom 3, 43,381 at zoom 4, 90 at zoom 2, 0 at zoom 1, both sides |
| the same city saved (autosave) and reloaded, all 10 mods | 0 |
| reloaded with mod subsets (sc3resize only, + sc3netmod, two halves of the rest) | 0 each |
| avenue (2 drags, DAV 20 cells) + boulevard (3 drags, DBV 27 cells) drawn with the Road tool (posted drags) | 0 at zooms 1, 2, 3, rotations 0-3 |

- The colour is the Road tool's cell highlight: the same diamond shows under the Road cursor ("$10" label).
  Over water the same highlight is red.
- `nb_drive.build()` writes low nibble 1 into SIMSPR's drag-highlight byte grid for the path cells (the object at
  SIMNTWRK `FUN_10021b37()->vt+0x8c`, grid at +0x6c), because `FUN_10014a23` keeps only cells that read highlighted
  `[CONFIRMED @ SIMSPR 0x1004adcd]`. It builds, then writes the saved bytes back.
- A grid byte holds the live highlight in its low nibble and the state last pushed to the view in its high nibble.
  `vt+0x58` = `FUN_1004b779(int box[6])` walks the box and, for each cell where the two differ, copies low into high
  and sends the cell to the view (message 0xC3331D0D) `[CONFIRMED @ SIMSPR 0x1004b779]`. The game's own set
  (`FUN_1004b534`, vt+0x2c) and clear (`FUN_1004b653` + vt+0x58, vt+0x40 = `FUN_1004ae23`) go through it.
- The lab's restore leaves both nibbles equal, so no cell is pushed. The pieces were placed while the cells read
  highlighted, so the terrain drawn under each ground-under piece's transparent part (35, 20505, 20950: frame-table
  flag 0x40) keeps the highlight colour until the city is reloaded. Full-tile pieces (20500, 43) have no transparent
  part, so nothing shows there.
- Only the LAST drag's cells keep it: a band's earlier drag is re-written by DAV / DBV during the next build, when its
  cells no longer read highlighted. In an avenue the last drag is `stair(x+1, z)`: middle + high-x outer cell
  (20505 state 0, the screen-left edge at rotation 0). That is the owner's "west edge" pattern.

## Fix: `re/tools/netmod/nb_drive.py`

After the build, the restore writes each byte with high nibble 1 ("the view shows it highlighted", which is true)
and calls `vt+0x58` over the cells' box (game-thread call, `exceptions: 'propagate'`). The game then pushes the cells
and redraws their terrain without the highlight, as after a Road tool drag. Old behaviour for before pictures:
`NB_DRIVE_HLPUSH=0`.

| case (same session, PID 19296) | highlight pixels |
|---|---|
| avdb_lab avenue 7 rows, fixed | 0 |
| avdb_lab dboulevard 7 rows, fixed (DBV 28 cells) | 0 |
| control, `NB_DRIVE_HLPUSH=0` (two short builds that stayed stock ladders) | 547 / 804, on those cells only |
| fixed bands, zoom 3 rotations 0-3, zooms 1-2 | 0 on the fixed bands (frames also hold the two controls) |

Not done (light testing): a lab band left over 5+ minutes, a save of a fixed lab band.

## Pictures (MAIN `verify\cyantri\owner_shots\`)

- `cyantri_before_after.png`: before (lab avenue zoom 3, lab stock diagonal zoom 4), after (lab bands with the fix),
  normal play (Road tool avenue + boulevard).
- `cyantri_after_rotations.png`: lab bands with the fix, zoom 3, rotations 0-3.
- `cyantri_after_zooms.png`: Road tool and lab-with-fix at zooms 1-3.
- single frames: `av_z3_r0`, `st_z3_r0`, `st_z4_r0` (before), `fix_bv_z3`, `after_lab_z3_r*`, `after_tool_z3_r*`,
  `tool3_z3`, `tool_bvav_z3`.
