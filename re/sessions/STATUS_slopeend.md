# STATUS slopeend (child of the orchestrator, 2026-10-26)

## goal
Owner: "is it possible to add an end of road on a slope?" (`MAIN\verify\slopeend\owner_shots\img1_road_end_on_slope.png`).
A plain road ending on a sloped cell keeps the sloped straight piece and stops with a square cut; on flat ground the
stock game draws the rounded cap 11225. Make the sloped end draw a rounded cap.

State: DONE (milestone 2 "fixed"). Details and evidence: worktree `verify/slopeend/RESULTS.md`.

## design
- Stock: the retile pass moves every non-flat legal-slope cell to the slope list; FUN_1001a2c0 gives it the ROAD slope
  table entry (SIMNTWRK 0x1003195C) by corner pattern only: 11202/0 (+x downhill), 11201/0 (+z), 11202/2 (-x),
  11201/2 (-z), steep 32 / 31 the same. Neighbours never read, no stock sloped cap art.
- 24 ids 27000..27023, ROAD variants of the slope pieces, used ONLY at their own state:
  11202: state 0 up/down/both 27000-27002, state 2 27003-27005; 11201: 27006-27008 / 27009-27011;
  32: 27012-27014 / 27015-27017; 31: 27018-27020 / 27021-27023.
- Rule, sc3netmod block SLE (`sc3netmod_sle.c`), after every ROAD retile (box + 1) and the load pass: road beside ->
  stock; road both sides along the slope -> stock; downhill only -> uphill cap; uphill only -> downhill cap; none ->
  both ends. Piece writer FUN_10008919, same state, height from terrain. Off: `SC3NETMOD_SLE=0`.
- Art: `slopeend_paint.py build`: the slope piece's own profile bent round a half circle (radius 0.5 at the cell
  centre), transparent outside, frame table taken from 11225 (`art.from: 11225`): sprite class 0x0672 + ground bit.
  The slope pieces' class 0x059D draws NO terrain under a ground-bit piece (holes, found in game, RESULTS 4). Class
  0x0672 anchors at the occupant height (the (x,z) corner), hence one art set per state with T shifted.
- Saves: tile word = stock slope piece, variant in section 0x4E56. Without the mod: today's square cut.

## ids
**27000..27099 reserved for slopeend; 27000..27023 used.** (Checked 2026-10-26: no variant id in any worktree's
manifest between 26210 and 28049; the 27xxx numbers in other STATUS files are PIDs; stock exemplars end at 18091.)

## built (files, uncommitted, worktree Simcity_wt_slopeend, branch child/slopeend)
- `re/harness/src/sc3netmod_sle.c` NEW (needs `git add -f`: re/harness/src files are force-added)
- `re/harness/src/sc3netmod_rbt.c` (+15, `/* task slopeend */`: decls, rb_file `sle`, rb_pass + rb_load_pass calls
  before AVL, sle_install, rbt_install gate `!g_sle_n` + both error resets, on-log, stats)
- `re/harness/src/sc3netmod.c` (+2: table_read skips `sle`, #include before AVL)
- `re/tools/netmod/netpack.py` (+12: `road_end_lines` key, validation, table output, placed set),
  `re/tools/netmod/netpack.schema.json` (+5)
- `re/tools/netmod/slopeend.py` (survey / classify / lab), `slopeend_paint.py` (build / preview / fit),
  `slopeend_lab.py` (lab drags), `slopeend_shots.py` (frame dumps), `slopeend_sheet.py` (owner sheet)
- `re/tools/netmod/examples/road_slope_ends/manifest.json` (package 1.1.0). Art is gitignored and rebuilt from the
  stock frames: `py -3.12 re/tools/netmod/slopeend_paint.py --game <tree> build re/tools/netmod/examples/road_slope_ends`
  (art sources = that script + the manifest; nothing hand-drawn).
- `verify/slopeend/RESULTS.md`

## files to commit (by path, worktree -> main)
re/harness/src/sc3netmod_sle.c (add -f), re/harness/src/sc3netmod_rbt.c, re/harness/src/sc3netmod.c,
re/tools/netmod/netpack.py, re/tools/netmod/netpack.schema.json, re/tools/netmod/slopeend.py,
re/tools/netmod/slopeend_paint.py, re/tools/netmod/slopeend_lab.py, re/tools/netmod/slopeend_shots.py,
re/tools/netmod/slopeend_sheet.py, re/tools/netmod/examples/road_slope_ends/manifest.json,
verify/slopeend/RESULTS.md. MAIN: re/sessions/STATUS_slopeend.md, verify/slopeend/owner_shots/* (pictures: check the
repo's publish policy before committing them).
Release note: a LAN / release build must install `road_slope_ends` (netpack install) and ship the new sc3netmod.dll.

## proven in game vs offline only
In game, final build (PID 14916 then 31616 / reload, lab11.sc3, all mods except sc3overscroll): every case wrote
the expected per-state id (W/E 11202 s2/s0, N/S 11201 s2/s0, up and down, stub, steep 32 s2/s0 and 31 s0/s2);
extension past a cap -> straight 11202; bulldoze below -> downhill cap; raised-corner cell -> stock flat 11225 (not
SLE); save -> 13 variant tiles as base + section; reload -> 13 restored, SLE load pass 0 writes; no terrain holes,
caps aligned in all 4 views; mod off (no sc3netmod) -> stock square cuts, no lost tiles. Offline: `slopeend.py
classify` on the save, 0 cells differ from the rule.

## blocked on
nothing

## instance
`<workspace>\Simcity_stock_slopeend\re\harness\inst_slopeend`; tree prep: `mods\netmod\ledger.json`
+ `packs\` copied from `Simcity_stock_avint` (overlay identical to the LAN build, 94 files compared), then netpack
install road_slope_ends. All my PIDs stopped (25628, 33420, 27480, 31672, 31848, 33672, 32824, 30168, 3848, 28560,
24052, 14916, 31616, last mod-off run below).

## needs owner
- Look check: `MAIN\verify\slopeend\owner_shots\slopeend_sheet.png` (before / after, zoom 4 and 3, 4 views).
- Design calls CONFIRMED by the owner 2026-10-26 (via the orchestrator): a slope end with a road beside it stays
  stock; an isolated 1-cell slope road gets both ends rounded (a pill). Both are what the build does.

## asks of other streams
none
