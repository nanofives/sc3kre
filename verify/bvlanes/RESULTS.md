# bvlanes milestone 2: boulevards with 3 lanes each way (2026-10-19 / 20)

Plan: `verify/bvlanes/PLAN.md`. Base: avcore's one-way halves (`re/analysis/AVENUE_LANES.md`, child/avcore 4c7e510).
Owner rules: right-hand everywhere, English-UK included; an avenue the mod cannot convert stays stock, and a piece
whose attached avenue would not convert stays in its pre-rework stock state (AVENUE_LANES.md program rule).

## What was built

| part | what |
|---|---|
| lane specs | 220 pieces: BV 57 (20700..20768 + new 20707 / 20708), BVX 29 (box cells 20900..20905 + new 20912..20932, noses 20910 / 20911), DBV 134 (20950..21063 + new 21900..21919); `bvl_<id>.lanes.json` in each package, `"mirror_uk": false`, no path keys, turn matrices = every lane's turn (low) and its transpose (high) |
| curves | 818 new VPathAtt shapes 24000..24817 (grant 24000..24999: 24200..24999 added 2026-10-20) (each cut no stock curve has; an English-UK twin where UK has no forward copy, as avcore's 23601 / 23603); `bvlanes.py build` |
| lanekit | a spec's own curves are preferred among curves with the same end points (adopted by avcore) |
| BV rule | a T column takes 20707 (entry row) / 20708 (middle row, state 2 for a T from +w); a narrowing into an avenue asks `avl_band_ok` first and leaves the run stock if the avenue would stay two-way (`sc3netmod_bv.c`, twin `boulevard.runs(band_ok=)`) |
| BVX rule | box cells chosen by (box width, height, sides, cell) through 105 `bvxc` lines (5 box kinds x 4 turns) instead of the edge pattern; an avenue arm asks `avl_band_ok` (`sc3netmod_bvx.c`, twin `bvx.box_want` with `bvlanes_boxes.json`) |
| DBV | no rule change: split pieces are new stamp entries (`dbvlanes.py rebuild`), art copied from the piece they split from |
| joins | `avlj` lines: narrowing end cells 20756 / 20757 / 20767 / 20768, noses 20910 / 20911, so avcore's bands end on them |
| netpack | `junction_t` (auto_boulevards -> `bvj`), `cells` (auto_boulevard_junctions -> `bvxc`) |

Lane rules (PLAN.md 2-3): each side = the outer cell's 2 lanes + the middle cell's lane beside it, one way; caps a
3-lane U-turn plus 2 routing branches; junctions straight on every lane, right from the outer lane(s), left from the
inner lane(s) through the median opening, 2 each from a 3-lane side, 1 from an avenue side or a road, fanning out where
a side has no straight feeder; tapers / narrowings merge on the side going in and split on the side coming out.

## Offline

| check | result |
|---|---|
| one lane set per piece on the rule's own placements (BV / BVX scenes, every diagbv drag case + every end shape on both ends and axes) | yes after the splits (BV 2, BVX 21, DBV 20 new ids) |
| `netpack.py validate` (boulevard, boulevard_junctions, diagonal_boulevard) | exit 0, 0 lane warnings |
| compiled records (netpack's own lanes compiler), every lane edge's curve vs the planned geometry, ENGLISH and English-UK | 1,676 edges, 0 off |
| neighbour pairs through `avlanes.check` | BV / BVX 2,346: 7 problems, all English-UK against stock road 29; DBV 1,242 distinct: 0 in ENGLISH, 36 in English-UK, all against stock 29 |
| edges with avcore's one-way half 21700 (narrowing ends, noses, all states, both languages) | 48 checks, 0 problems |
| diagonal handovers: taper ends to the stock diagonal road, narrowings to the diagonal avenue | every edge on the stock 35 slots (18 + 12) |
| python twins vs the placements the lanes were built for | 376 cells, 0 differ; all 20 box configurations resolve; `diagbv.py check` 0 off; `bvx.py check` 0 failures |

English-UK: stock road 29 keeps its mirrored (left-hand) lanes in the UK files, so wherever a right-hand rework piece
meets a plain stock road, English-UK cars cannot cross that edge. Program-level (reported); ENGLISH is clean.

Also in the BV block (`sc3netmod_bv.c`): the post-AVL slot `AVL_POST_BV`. After each `avl_run` it hands AVL the box
of every cell BV wrote or reverted (so the attached avenue is re-decided with the boulevard as it stands), and re-decides
a run whose attached avenue AVL left two-way when `avl_band_ok` says it cannot convert (a side road drawn far down the
avenue, outside BV's own pass box). Each call handles only the attachments it started with (a first version that did
not looped in game: it re-decided a run that held, which re-added the same attachment; fixed before the runs below).

## Tight left turns (orchestrator rule 2026-10-20: no left bend of radius <= 80, either language)

`avlanes.py tightleft` on the three packages: 54 hits on the first build (27 per language), **0 after these changes**:
- BV cap routing branches: half ellipses instead of polylines (the U-turns themselves were already 112..127);
- every junction merge (two turning lanes onto one lane) runs a tangent arc onto the real lane instead of aiming at a
  virtual lane and bending onto the real one (BV boxes and DBV junctions);
- DBV junctions: the 135 degree left turns from the band onto the crossing road are dropped (inside one road row no
  bend wider than ~56 fits); band traffic turns right there; a lane left with no move turns right too;
- DBV caps: two concentric half ellipses square to the band (outer to outer, middle to middle, tightest bend 110..117
  units); the inner lanes are only 0.63 cells apart across the diagonal, so no U between them can be wider than 80:
  the inner C lane merges into the middle one just before the U and the inner A lane splits from it after (an S of two
  tangent arcs, radius 105), as avcore's one-lane U-turn; the U sits as far into the cap as the curb allows (searched
  back from the curb, so the same for every band length);
- DBV tapers: the lanes are smoothed after the curb clamp.
New curves get sort id 0 (hwlanes.extra_for, avcore 3559939): netpack writes it at install, no spec change.

## In game

Tree `Simcity_stock_bvlanes`, instance `inst_bvlanes`, packages avenue_lanes (avcore), boulevard, boulevard_junctions,
diagonal_boulevard, sc3netmod.dll from this worktree. Shots: `MAIN/verify/bvlanes/owner_shots/bvlanes_sheet.png` (+ `bvlanes_dbv_lanes.png`, the diagonal lanes top-down).

| run | what | result (sc3netmod.log) |
|---|---|---|
| lab (pid 48456) | boulevard x 44..70 z 20..22, road crossing x 50, road T x 56, avenue x 64..65 | BV: caps 20704..20706 both ends, crossing 20710 / 20711 / 20710, T 20707 / 20708 / 20712, box cells from the `bvxc` table, noses 20910 / 20911; the twin on the same roads = the live grid (85 cells, 0 differ); avcore converted both avenue arms one-way, each band ending at a nose (`ends: U-turn / join or edge`) |
| | save, reload (pid 58556) | `save: 105 variant tile(s) written as base`; the saved file holds stock ids only (max 11225); reload `all 105 variant tiles restored`, load passes write 0, live grid identical |
| Seoul (pid 3756, 74608) | road row 206 x 143..159 (mean monthly density 88.6 along it), 21 houses on rows 205 / 207 demolished, two drags x 145..157 -> boulevard tapering into the road at both ends (39 cells) | car tracks 180 s (`hwcars_tracks.py`, 249 cars): row 205 only eastbound (153 car passes summed over its cells), row 207 only westbound (168), middle row both (460 E / 524 W); on the boulevard pieces no STOP / JUMP / UTURN; 17 removed and 11 spawned mid-road at scattered cells (the stock density despawn / spawn; none clustered at cell borders) |
| | router (`lanedensity` lines) | 36,340 honoured steps in the game, wrong-way fails 0; e.g. (150,205) entered only by x- and left by x+ (300 steps), (150,207) the reverse (394), (150,206) both |
| | save | `save: 39 variant tile(s) written as base`; the whole saved city has no id above 18083 (stock) |
| lab (pid 32644, 35760) | diagonal boulevard (drags x 102..112, z 92..100) + row road z 96 | DBV: square cap on top, cap-part at the bottom, the crossing 20953..20956 with noses 20952 / 20957, as diagbv recorded |
| | avenue x 125 / 126 z 6..38, third road x 127 z 10..30 | BV narrows into the avenue at both ends (20750.., 20760..); avcore converts both avenue pieces one-way, each ending at a narrowing (`join`) and a U-turn; the post-AVL hook re-runs AVL over BV's cells |
| | side road z 35 into the lower avenue | `run ... left to the stock tiler: the avenue it narrows into would stay two-way`; then both avenue pieces stock too (program rule) |
| | side road removed | BV converts again (63 cells), AVL converts the lower avenue, the post-AVL re-run converts the upper one; every piece consistent |
| | save, reload (pid 51764) | `save: 122 variant tile(s) written as base`, saved ids stock only; reload restores 122, every load pass writes 0, grid identical (37 x 98 cells) |

Not seen in game: the diagonal boulevard narrowing into the diagonal avenue (the diagonal avenue is still two-way until
avdiag's pieces; offline the narrowing's edges sit on the stock 35 slots), the post-AVL re-decision of a run whose
avenue is cut off beyond BV's own pass box (the lab window is too small for a side road more than 24 cells away),
caps / T / boxes with traffic (Seoul had a tapered stretch only), English-UK. The DBV cap U-turns were reshaped after the
lab run (the outer lanes start nearer the curb than the first margin allowed, which flattened the U); offline checks
re-run after it (above); the installed test tree holds the build before that fix.

## Car hang: a test trap, not the game (2026-10-20)

The hangs I measured (main thread in the STRTSIM car step waiting in SIMCITY.DLL+0xd31d, render thread in
SIMSPR+0x54f3d) came from Frida attached while the game was paused: the saved city loads paused, and my camera helper
(rb_lab cam, Frida) ran before the unpause. avcore showed any such attach deadlocks within 30 s. Re-run with no Frida at
all (unpause + speed 3 by posted keys, the save's own view, 105 s): the full package set (802 new
curves in the overlay, sort id 0) ran 3 / 3 without a hang, router busy (12,000..14,600 evaluations per run). With the camera moved by
Frida only after the sim was running: 2 / 2 clean; the third such run hung after the helper's HUD clicks failed to
capture the camera (very likely pausing it first: the trap again). The bisect table I sent earlier is void.

The radius <= 80 rule was lifted with it. Kept from the tight-left round (they only make bends smoother): tangent merges,
half-ellipse cap branches, smoothed DBV tapers, concentric DBV cap U-turns. Restored: the DBV 135 degree left turns from
the band onto the crossing road, and the inner-to-inner DBV U-turn (the owner sheet's "outer to outer, middle to
middle, inner to inner"); tightleft now lists 26 hits, all those (allowed).

## Open

- DBV narrowing into the diagonal avenue: edge convention confirmed by avdiag; `dbv_narrow_ok` calls `dav_band_ok` once child/avdiag (with `DAV_HAS_BAND_OK`) is merged; not seen in game yet.
- English-UK: stock roads stay left-hand there (program call pending).
