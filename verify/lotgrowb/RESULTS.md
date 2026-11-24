# lotgrowb: non-square growables, full version (round 2026-11-24d)

Design: `re/analysis/LOT_SHAPES.md` section 11. What was built and measured: section 12 there. Brief:
`re/sessions/ROUND_2026-11-24d_lotgrow_build.md`.

## Verdict

**Done, mod side and importer side.** Imported growables on 1x2, 2x3 and 3x4 lots grow by themselves in the zones
(sc3simrun LOTGROW, mods page row "Non-square zoned buildings", default on), and draw whole with LOTRECT. Square
buildings take exactly the stock code path, proven call by call against the stock bodies. The importer (Python and
page, byte for byte) writes w x d growables, including the copy families classes 3500 and 3700 need.

## 1. Mod side: sc3simrun LOTGROW

| part | where |
|---|---|
| rule-vtable slot 0x1c rewrites (9) | SIMRCI `0x1004cccc`, `0x1004c8f8`, `0x1004c404`, `0x1004c444`, `0x1004c3c4`, `0x1004c128`, `0x1004cd0c`, `0x1004c1a8`, `0x1004c168` |
| C copies of | block fill `0x10026b01` (no transport test), `0x10020762`, `0x10014794`, `0x100152a2`, `0x10013c66`, `0x1000c3eb` (transport test `vt+0x6c(&cell, rule+0x30)`); corners + strip + fill `0x10027699`, `0x1000dd1a`; com block `0x1000cf87` |
| byte check before patching | SIMRCI TimeDateStamp `0x38fd559f` + SizeOfImage `0x60000`, each slot's pointer, FNV-1a of each body with relocations zeroed, each tunable among the body's relocated operands; all or nothing |
| switch | `simrun.ini [lotgrow] enabled=1`; env `SC3SIMRUN_LOTGROW=0` = slots untouched; mods page row (sc3resize MODTOGGLE `-SC3SIMRUN_LOTGROW`) |
| verify mode | `SC3SIMRUN_LOTGROW_VERIFY=1`: lockstep replay through the stock body (section 2) |
| log | `SC3SIMRUN_LOTGROW_LOG=1`: every non-square placement; a summary per minute (calls per rule, time in Apply, placements, verify counts) |

Non-square rules in the copies: Z from attrib `vt+0x44` on the z axis, all X x Z grid cells free, refused while LOTRECT is
not installed (SIMSPR `0x10019341` not a jmp into sc3perf), when X > Z, or when Z - X != 1. Found while copying:
`0x10027699` skips its corner step on an empty corner list (`jbe` at `0x1002790c`), `0x1000dd1a` does not.

## 2. Identity test (the gate) - PASSED before anything non-square was installed

Every rule RNG is seeded from `timeGetTime` (`cRZRandom::Seed` SIMRCI `0x10039a7f`): two runs of the same save never grow
alike, so occupant layers of a switch-off run and a switch-on run cannot be compared. The test is in lockstep instead:
each Apply runs the C copy for real, recording every ZoneLayer call and answer, then the stock body on the same input
with the seed put back and a replay layer that checks every call (slot and arguments) and returns the recorded answer;
final seed and result compared.

| run (no non-square member installed) | Apply calls | identical | different | layer calls checked | log |
|---|---|---|---|---|---|
| Sacramento, ~7 sim minutes | 1,487 | 1,487 | 0 | 7,019 | `work/logs/sac_verify1_sc3simrun.log` |
| Europolis 1024, ~3 sim minutes | 99,891 | 99,891 | 0 | 231,849 | `work/logs/e1024_verify1_sc3simrun.log` |

8 of 9 bodies ran there. The ninth, dense commercial `0x1000c3eb`, ran 532 times in Berlin later (all identical where no
non-square member was drawn). With members installed, verify splits differences into "a non-square member was drawn in
this call" (expected: the paths part there) and "unexplained": **0 unexplained** in Sacramento, Berlin and Madison.

## 3. In game (dev\lotgrowb\tree, windowed, posted input and Frida game calls, test slot)

Test pack: `work/pack` (Kenney CC0 models from the sample pack), installed first through `work/mkgrow.py` (bldimport as a
library) and later with the finished importer: Shop Row 1x2 (5700, family 8), Office Block 2x3 (6100, 23), Long Factory
1x2 (8900, 19), Chimney Factory 1x2 (8300, 6), Gable House 1x2 (3900, 12), Villa 1x2 (3500, 31 + copy 38100), Wide
Apartments 1x2 (3700, copy 38116), weight 20 each.

| check | result | picture |
|---|---|---|
| grow by themselves | Sacramento 30 min: 425 placed (ind_block_v3 375, res_corner 34, res_block_v3 9, com_corner 7). Berlin 25 min: 241 (162 / 51 / 28 com_corner). Madison 25 min: 27 | `01` |
| every rotation draws whole | industry 1x2 at zoom 3, Shop Row 1x2 and Office Block 2x3 at zoom 4, 4 rotations; sorted against their neighbours | `01`, `02`, `03` |
| under construction / abandoned | one sprite over the whole lot, flag 0x400 on both cells (`lab.py cells`), the building's own frames | `04`, `05` |
| save / reload | autosave of the Sacramento run: 217 non-square occupants saved with their real size (1x2, one 2x3, `work/occsave.txt`); loaded again: same rects, SizeInCellsX/Z 1 x 2, one sprite with 0x400 | |
| bulldoze (game's Demolish tool, posted click) | the 1x2 at (222,65) gone, both cells ordinary single-cell sprites, no 0x400 | `06` |
| package removed, mods on | each 1x2 came back as a 1x1 stock building of its class on its origin cell, the second cell empty zoned land (e.g. 38002 at (218,66) -> 8900 id 0x13bc 1x1). No overlap | |
| copy families live | class 3700 members drawn by the residential corner rule in Madison (verify lines) | |
| sim cost | time in the copies: Berlin 1,396 ms over 10,410 Apply calls = 0.134 ms per call with verify on (copy + stock replay + PlaceBuilding); without verify, Sacramento 523 ms over 1,737 calls in 11 minutes. sc3perf DAYS> on the same save, speed 3, 12 minutes each: LOTGROW on, medians 661-665 ms per day; off, 662-668 ms; both at the nominal 666 ms (`work/perf_ab.out`) | |

Not done in game: the save opened in the stock game (`-Stock` loads only sc3winonly.dll and the `-City` load needs the
mods, so the stock instance stayed on the menu; the missing-key path it would take is the package-removed row above);
redevelopment over a non-square building was not singled out (sc3simrun CHURN sets the anarchy roll to 0 by default;
the zone layer's merge path, FindBuildableRect over abandoned / same-class cells and PlaceBuilding removing what a new
footprint covers, is X x Z already, LOT_SHAPES 11.1). Needs owner check: none of the above needs a real cursor.

## 4. Importer side (bldimport.py, bldweb.js, classifier.html; after objprops merged, fast-forwarded to main 1fbdd1a9)

- `lot_of(m, rect, grow)`: growables accept 1x2, 2x3, 3x4 (`GROW_RECT`); 3x2 / 4x3 / 2x1 get "list the short side
  first ... turn the model with rotate_deg"; others "non-square growables are 1x2, 2x3 or 3x4".
- Stats of the class's d x d base (`class %d has no %dx%d base for a %s lot` otherwise); prop 0x66 = (w, h, d); frames and
  anchors as for a w x d landmark (LOTRECT anchors).
- Families: `grow_families`: no fixed-layout family (`FIXED_FAMILIES` 1, 10, 16, 25, 28, 29, 30); 3500 -> 31 + copy
  38100 of family 10, 3700 -> copy 38116 of family 16 (`COPY_FAMILIES`), with the four [ZoneDeveloperRules] rows
  rewritten in the overlay SYS.PAK (`copy_family_rules`); farm 9300 refused.
- Page (bldweb.js) ported line for line, including a SYS.PAK builder (`syspakBuild` = `syspak_parse.build`).
- classifier.html: Lot choices 1x2 / 2x3 / 3x4 when all selected cards are growables; the suggestion gives a long model a
  w x d lot (d = its long side) when the class has a d x d base, turning it 90 degrees when its long side is along x;
  warnings for 3x2-style lots, missing bases and farms.
- Tests: golden case `lotgrow` (`make_testmodels.py --lotgrow`: shop 1x2, villa 1x2 (copy 38100), flats 1x2 (copy 38116),
  tower 3x4, office 2x3, a square 3500 beside them, five refused), in golden_setup / golden.mjs / pagetest.mjs; lotshape's
  refused growable is now a 3x2. Python vs page on case lotgrow: 14 of 14 files equal, 120 frames equal.

## 5. Suite, docs

- Full suite, normal mode, six arguments + SC4INSTALL, `PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off`, test slot: **42 of 42 steps passed** (`dev/lotgrowb/work/runall1.log`), golden.mjs with case lotgrow (every file + frame), pagetest.mjs lotgrow (the page installs it in headless Chrome). `sync_css.py --publish` done.
- Guide: `docs/buildings/index.html` section "Growables on lots that are not square" (from MAIN
  `verify/bldpack/work/guide_template.html`, backup `.pre_lotgrowb`, `make_docs.py` with the published sample-pack link).
- README: mods section row "Zoned buildings on lots that are not square".

## Files

Worktree `dev/lotgrowb/wt` (branch child/lotgrowb), listed in `re/sessions/STATUS_lotgrowb.md`.
