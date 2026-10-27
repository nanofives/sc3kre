# STATUS avslope (child of the orchestrator, 2026-10-26)

## goal
Owner (LAN build sc3mods-2026-10-26b): "avenue section on slope doesn't have the lanes, then check for 3 road avenues
for the same" (`MAIN\verify\avslope\owner_shots\img1_avenue_slope_no_lanes.png`). On sloped cells an avenue (and a
boulevard) shows plain two-way sloped roads: yellow centre line, no median trees, a jog in the curb.

State: DONE (milestone 2 "fixed", 2026-10-26). Evidence: worktree `verify/avslope/RESULTS.md`.

## design
Measured in game (lab.sc3, PID 24740, all mods but sc3overscroll, LAN-build sources = main 0284ba7):
- Avenue up / down a slope (both axes, both directions, mag 1 and steep): stock puts the plain slope piece in both
  halves (11202 / 11201 / 32 / 31, state = downhill side). AVL ALREADY converts those rows to its one-way slope
  variants 21718..21725 (lanes right, saved as the slope piece), but those ids have no art of their own: they draw the
  plain sloped road (yellow line, no median, narrower asphalt = the jog). Owner's picture = this.
- Boulevard on a slope: BV counts any ROAD cell as a column, so it writes FLAT 20700 / 20701 onto the sloped cells
  (terrain hole + step in game) and the save holds 11204 / 29 on a sloped cell (a no-mod load shows flat on slope too).
- Halves at different heights: not buildable. A Road drag along a cell sloped ACROSS it builds only its first cell
  (lab PE, rows 83 / 94); two adjacent flat cells share vertices, so no terrace. Shipped cities: 0 such pairs.
- Junction next to a slope (tee 2 cells from it): AVX box + band through the slope convert (lab PA).
Fix:
- Avenue: art for AVL's 8 slope ids (avslope_paint.py: the release's white-dash 11204 + its trees laid on the slope
  piece's own plane; trees moved by the plane height at their foot; first-pass bit cleared). No code, no new ids.
- Boulevard: 12 new ids 27100..27111 (sloped OUTER per slope piece x direction = 8, sloped MIDDLE per slope piece = 4),
  base = the slope piece (saves stock-safe), art = the boulevard's own outer / middle art laid on the plane, lanes =
  AVL's slope one-way lanes (outer, same 80 / 175 positions as 20700) and the slope piece's two-way lanes (middle).
  BV: when a cell it writes holds a slope piece, write the sloped variant at the cell's own state (outer / middle /
  nose -> sloped outer / middle; other roles leave the slope piece).

## ids
**27100..27199 reserved for avslope; 27100..27111 used** (boulevard_slopes: 27100..27107 sloped outer, 27108..27111
sloped middle). Checked 2026-10-26: no variant id 27100..27199 in any
Simcity* worktree manifest (1,074 ids scanned); the 271xx numbers in STATUS_avx32 / hwseam / menumask are PIDs.

## built (files, uncommitted, worktree Simcity_wt_avslope, branch child/avslope)
- `re/harness/src/sc3netmod_bvs.c` NEW (needs `git add -f`): BVS, boulevard cells on a legal slope (terrain corner
  pattern FUN_1001a1f3) get the sloped outer / middle at the slope's state. Off: `SC3NETMOD_BVS=0`.
- `re/harness/src/sc3netmod_bv.c` (+3, `/* task avslope */`: `bvs` lines, bv_is_piece, bvs_map in the write loop)
- `re/harness/src/sc3netmod_rbt.c` (+4: decls, bvs_install after BV's env check, bvs_stats)
- `re/harness/src/sc3netmod.c` (+2: table_read skips `bvs`, #include before sc3netmod_bv.c)
- `re/tools/netmod/netpack.py` (+16: key `boulevard_slope_lines`, validation, table output, placed set),
  `re/tools/netmod/netpack.schema.json` (+5)
- `re/tools/netmod/avslope.py` (survey, lab), `avslope_lab.py` (lab drags, frame dumps), `avslope_paint.py` (art for
  both packages: build / bvmanifest / bvbuild / preview), `avslope_trips.py` (direction probe), `avslope_sheet.py`
- `re/tools/netmod/examples/avenue_lanes/manifest.json` (0.1.0 -> 0.2.0: art for 21718..21725, first_pass false)
- `re/tools/netmod/examples/boulevard_slopes/` NEW: manifest.json + bvs_27100..27107.lanes.json (written by
  `avslope_paint.py bvmanifest`)
- `verify/avslope/RESULTS.md`

## files to commit (by path, worktree -> main)
re/harness/src/sc3netmod_bvs.c (add -f), re/harness/src/sc3netmod_bv.c, re/harness/src/sc3netmod_rbt.c,
re/harness/src/sc3netmod.c, re/tools/netmod/netpack.py, re/tools/netmod/netpack.schema.json,
re/tools/netmod/avslope.py, re/tools/netmod/avslope_lab.py, re/tools/netmod/avslope_paint.py,
re/tools/netmod/avslope_trips.py, re/tools/netmod/avslope_sheet.py,
re/tools/netmod/examples/avenue_lanes/manifest.json, re/tools/netmod/examples/boulevard_slopes/manifest.json,
re/tools/netmod/examples/boulevard_slopes/bvs_271*.lanes.json (8 files), verify/avslope/RESULTS.md.
MAIN: re/sessions/STATUS_avslope.md, verify/avslope/owner_shots/* (pictures: check the publish policy first).

## release (what must be installed)
1. sc3netmod.dll built from this branch (BVS).
2. `avenue_lanes` 0.2.0 reinstalled (uninstall + install) with art: art/11204 and art/11203 as today (avenue_markings.py
   frames, copies in Simcity_wt_avint) PLUS art/21718..21725 from
   `py -3.12 re/tools/netmod/avslope_paint.py --game <tree> build re/tools/netmod/examples/avenue_lanes`.
3. `boulevard_slopes` 1.0.0 installed, art from
   `py -3.12 re/tools/netmod/avslope_paint.py --game <tree> bvbuild re/tools/netmod/examples/boulevard_slopes --boulevard <boulevard package dir with art/20700, art/20701>`
   (the boulevard package's art lives in Simcity_wt_avint, gitignored). Nothing is hand-drawn: all art is rebuilt
   from the game's frames by those scripts.

## proven in game vs offline only
In game (lab, all mods except sc3overscroll): before (PID 24740) the table in RESULTS 1; after (PID 31476) the load of
the old save converted the 24 flat boulevard cells on slopes to 27100..27111, the avenues' slope cells draw the avenue
half, an edit-path avenue + boulevard over a plateau next to two crossing roads converted (AVX boxes beside the slope,
BV's slope column), save 477 variants as base with 0 non-slope tile words on slopes, reload (PID 24328) 477 restored and
0 load-pass writes, mod off (PID 20084) stock slope pieces and no hole. Traffic (Frankfurt, PID 16432, 300 s): 8,062
trip steps over 89 sloped halves, all in the halves' lane direction (flat halves the same, 105,755). Offline: previews of
both packages, netpack validate OK.

## blocked on
nothing

## instance
`Simcity_stock_avslope\re\harness\inst_avslope` (lab.sc3, lab_built.sc3 = run 1 save, lab2_saved.sc3 = run 2 save,
frankfurt_saved.sc3, frankfurt_sites.json, frankfurt_trips.json, run*_logs). Tree prep: `mods\netmod\ledger.json` +
`packs\` copied from Simcity_stock_slopeend, then the two packages installed. All my PIDs stopped (24740, 31476,
24328, 20084, 16432). No game of mine running.

## needs owner
- Look check: `MAIN\verify\avslope\owner_shots\avslope_sheet_z4.png` (before / after at zoom 4, both axes, mag 1 and
  steep, junctions beside a slope, two Frankfurt avenues) and `avslope_sheet_z3.png` (all four views).
- Hand test not done with a real cursor (posted input only).

## asks of other streams
none
