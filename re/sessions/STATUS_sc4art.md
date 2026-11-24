# STATUS sc4art (round 2026-11-24, SC4 conversion artifacts) - DONE

## goal
Owner: artifacts on converted SC4 buildings (verify/forumshots/owner_sc4_artifacts.jpg). Trace pixels to faces, fix
converter faults (Python = page), count, re-make sheets, suite.

## verdict (full detail: verify/sc4art/RESULTS.md)
1. Mayor's House lamp slabs: lamp 1DFC view = 7 vertices but crossed billboards; hidden_faces' back walls hit the stair
   art next to it on SC4's shared prop atlas. FIXED (views.is_box).
2. Police lamp columns: lamp 1DFB = real 1x1x9 m box, pole drawn on front + back walls. FIXED (views.thin_billboard).
3. Hagia shards: view-N proxy faces (65-96% clear) whose opaque texels are all behind the minaret, 10-21 m nearer SC4's
   camera. FIXED (views.proxy_hidden: faces >= 50% clear lose hidden texels; a strict rule opened roof holes).
4. Alamo fragment: hull face at 67.5 deg paints ground rubble (view W shows a 6 m gap). Camera/hull family, unchanged.
5. White police cars: baked tone lifts their black panels. Owner call (style), unchanged.

## built (dev\sc4art\wt, no commit)
Python = page 188 files 0 differ. Full suite 41/41 (1,492 s). Non-SC4 goldens 1,414 same, 0 differ.
Full install: 302 of 423 models change (proxy 2,972 faces in 280 models; box test 8 prop models / 37 rows + 2 houses;
billboards 5 prop models / 109 rows). 17 forum pictures re-made (old copies *_pre_sc4art.jpg), new in-city frames for 12.

## proven game-side
Madison: 9 civic/landmark/reward looks + police placed and shot in 4 rotations (lamp posts thin, Hagia shards gone);
Dao / Tsvirkunov from forumshots' industry save. Only the start-up 0xC0000096 line. Harness released, no BMPs.

## blocked on
nothing

## files owned (to commit by path, worktree dev\sc4art\wt)
re/tools/sc4conv/views.py, re/tools/sc4conv/props.py, re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/compare_sheet.py,
re/tools/bldimport/sc4web.js, docs/buildings/importer/sc4web.js, re/analysis/SC4_FORMATS.md.
MAIN: re/sessions/STATUS_sc4art.md, verify/sc4art/RESULTS.md.
Local only: verify/sc4art/{owner_shots,fd,runs,logs}, verify/sc4cmp/forum (re-made), dev\sc4art\work.

## owner calls
- police cars: keep baked tone, or exempt props from it (owner_shots/02).
- Alamo fragment: leave (camera limit), or a hand-table entry like firedist's door wall.

## game-harness need
none left
