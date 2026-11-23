# civlot results (round 2026-11-23b): SimCity 4 civic buildings and parks on their own SimCity 4 lot

Worktree `dev\civlot\wt` (branch child/civlot, fast-forwarded to main 991bea2 after bakedsharp, nothing committed). SC4
install read in place. Pictures with SC4 art stay local (`owner_shots\`, `verify\sc4cmp\forum\`).

**Verdict.**

- **It holds, with one rule.** A civic look is its own exemplar (bldimport's copy of the button's stock exemplar), so its
  lot is data (prop 0x66). The placing tool, site check, cell claim, bulldoze and Mover read X and Z separately, the
  coverage is stamped from the occupant's X x Z rect and removed from the same rect (SIMSERV `0x1000f006` ->
  `0x1000f557`), the price is by type, and LOTRECT saves X x Z. Static detail: `re/analysis/CIVIC_REWARD.md` section 8.
- **The rule: X <= Z.** A saved look whose key is gone (plugin removed) is loaded as a SQUARE exemplar of its type with
  side = the saved X (SIMGEOM `0x100038a8` -> SIMINIT `0x1000cb3d`). With X <= Z that is nothing (an empty lot) or a
  square inside the lot. With X > Z a 3x2 police look would come back as the stock 3x3 station over its neighbours. So a
  civic w x d with w > d is installed turned a quarter (d x w, model rotated 90 degrees, its SC4 views remapped).
- **In game: works.** SimCity 4's Small Police Station (3x2 in the model frame, installed 2x3) was picked from the
  Police list in Madison, placed on 2x3, drew whole in four rotations, drew its own coverage circle, saved as 2x3,
  reloaded the same, opened in the stock game, and came back as an empty lot with the plugin removed.
- **baked_sharp is the default style for every converted SimCity 4 building** (orchestrator, owner call 2026-11-23):
  `sc4conv.py --style` default and `sc4web.js` `opt.style`, guide updated. Full install: all 113 entries baked_sharp.
- Suite: see section 4.

## 1. What changed

| part | change |
|---|---|
| `bldimport.py` | `RECT_KINDS` + `civic`; `civic_table` maps every lot 1..5 to the button's exemplar, `"lot"` = the stock lot (default); the "keeps the stock lot" refusal is gone; prop 0x66 rewritten for every civic look; `civic_turn` / `turned_model`: a civic [w, d] with w > d becomes lot (d, w), `rotate_deg + 90`, marker `_quarter` (render key, sc3slot groups s -> s - 1 in `render_one`); report line "(turned a quarter: the short side first)" |
| `bldweb.js` | the same (`civicTable`, `RECT_KINDS`, `civicTurn` / `turnedModel`, plan, pack, `renderOne` job.quarter, `renderJob` slot remap). Render core (`renderFrame`, styles) untouched |
| `classifier.html` | Lot choices w x d and 5x5 for civic looks; warnings: lot vs the stock lot (same service, coverage radius, price), "installed turned a quarter" for w > d; hints |
| `sc4conv.py`, `sc4web.js` | `service_for`: civic buildings and parks on SC4's own lot (`real_lot`) when it fits 5x5, else the smallest square; notes name the SC4 lot and the turn. `--style` / `opt.style` default `baked_sharp` |
| `make_testmodels.py` | case civmod: the police 2x2 look is now accepted; case lotshape: a police hall 3x2 (turned) and a Small Park look 2x3 (were refused) |
| `compare_sheet.py` | `turn_of`: a turned civic look's SC3 frame slot is the SC4 view's slot - 1 (main sheet, four-sides sheet, subtitle lot) |
| guide | `docs/buildings/index.html` from MAIN `verify/bldpack/work/guide_template.html` (make_docs.py, the published sample-pack link kept, `stage\sample_pack\README.txt` unchanged, sha256 bdda1dee...): civic Lot row, non-square section, removing looks + why X <= Z, the in-game test, SC4 civic bullet, install count 83 of 113, baked_sharp default line (folds in bakedsharp's line); importer copy published (`sync_css.py --publish`) |
| analysis | `CIVIC_REWARD.md` section 8, `LOT_SHAPES.md` section 10 |

## 2. Converter, the Steam SimCity 4 Deluxe (full install, scratch folder)

113 models, 83 on (82 on main). Civic and parks: 23, 22 on (Large High School off, 6x6), 14 not square, 5 turned
(Small Police Station 3x2, Large Fire Station 3x2, Large Medical Center 4x3, Ranger Station 2x1, Soccer Field 5x3).
Examples: Small Fire Station 1x2, Elementary School 2x3, City Museum 2x3, City Jail 3x4, Deluxe Police Station 3x4,
City College 3x5, Tennis Court 1x2. Style: baked_sharp on all 113.

## 3. In game (dev\civlot\tree, Madison, windowed, posted input and Frida game calls)

Converted with `sc4conv.py --only` (Small Police Station, Small Fire Station), installed with `bldimport.py build`: ids
38000 fire (1x2), 38001 police (2x3, turned). Load: `LOTRECT> 29 SIMSPR sites patched`, `save footprint: 9 of 9`,
`CIVVAR> base 0xD2: 0xB1D10002:0x9471 "Small Police Station"`. Harness claimed for every run (shared with forumshots,
coordinated). Game PIDs started and stopped by this session: 2684, 21200, 21880, 11832 (-Stock), 19552, 17616, 21356.

| check | result | picture (`owner_shots\`) |
|---|---|---|
| Police button (hotkey 0x18 = the button's GetCommand path) | list "Elegir aspecto": 3 style rows + "Small Police Station", `CIVDLG> entry 3: key 0xB1D10002 0x00009471 type 13130 lot 2x3 price 500`; picked, "Aspecto 4 de 4", "Precio: $500" | 01 |
| tool | key `0xB1D10002:0x9471`, `+0x116` = 1, `+0x117` = 2: a 2x3 highlight; cost label "Aspecto 4 de 4: Small Police Station \| $521" | 02 |
| place (posted click) | `RELOCATE> building placement (kind 0) at (197, 210): placed, price 521` ($500 + clearing); occupant rect [197, 210, 198, 212], SizeInCellsX 2, Z 3, 6 cells, type 13130, rotation 0 | |
| draw | zoom 4 and 3, four rotations: whole, the lot's car park and lawn, the neighbouring pylon sorted in front where it stands in front | 03 |
| coverage | crime map ("Mapa de criminalidad", Cobertura de Policía) with the look, then the look bulldozed (Demolish 0x12): cyan pixels 2,913 -> 2,735, 178 gone, 0 new, one whole circle with its centre (map x 249..313, y 349..413) | 04, 05, 06 |
| save | sc3autosave (link-safe) -> `civlot_saved.sc3`: `207EDC0E B1D10002 38001 at (197,210) rot 0 size 2x3` | |
| reload | the same occupant and rect; sprite cells (197..198, 210..212), size byte 2, registration (198, 210), flag 0x400 on all 6 | 07 |
| stock game (`sc3dev run -Stock`, only sc3winonly, plugin present) | alive 75 s+, occupant 2x3 at the same rect; drawn as a 2x2 sprite plus bare plopped ground at the +z end (no LOTRECT, as non-square landmarks) | 08 |
| plugin removed (`bldimport.py restore`) | loads, no occupant in the 2x3 rect and no stand-in station: empty orange-brown 2x3 lot; one VEH line, the game's own start-up `0xC0000096 at SC3U.exe+0x84122` | 09 |
| baked_sharp, among houses | a second copy at (157..158, 203..205) next to houses and a road, four rotations at 1430x900 | 10 |
| faults | every run: only the start-up `0xC0000096 at SC3U.exe+0x84122` | |

Not run: the Mover on the look (lotdraw ran it on its probe landmarks), the fire look in game (converted and installed,
not placed), the overlap a 3x2 civic look would make after a plugin removal (static only, 8.2; the importer no longer
writes one).

Forum sheets (`verify/sc4cmp/forum/`, local): `01_small_police_station.jpg` (SC4 view S next to SC3 slot 2 of the
turned look, 2x3 subtitle, the in-city strip from this round's frame `24_town_z4_r2.png`, matched at RMS 19.5) and
`00_small_police_station_four_sides.jpg` (each column the same side). The 3x3 versions are kept beside them as
`*_pre_civlot.jpg`. In-city match spec: `work/ingame.json` (`work/match_town.py`).

## 4. Suite

`SC4INSTALL=<Steam SimCity 4 Deluxe> SC3PACK_PACKS=MAIN\stage\st_packs PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off
test-slot bash re/tools/bldimport/webtest/run_all.sh dev\civlot\work stage\release stage\kits "<.happy-uploads>\SC4D LEX
Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes stage\st_packs\sc4` (normal mode, after the
fast-forward to main and the baked_sharp default): **41 of 41 steps passed**, wall 2,596 s (log
`dev\civlot\suite_full.log`). Python = page on every case, the SC4 references (install set, packs, props, lot
textures, baseprops) rebuilt by the suite with baked_sharp and equal on both sides.

An earlier run (before the merge) had 40 of 41: `sc4_install.mjs` models.json differed only by the turn note, because
the Python install reference was built in a parallel group before that note was added and the page side after. The
final run has the note on both sides.

Python goldens against main's code (`golden_setup.py` of MAIN 991bea2 into `dev\civlot\g_main`, compared with
`verify/lotshape/work/golden_diff.py`, `dev\civlot\golden_diff.txt`): 1,326 files the same, 14 differ, all in cases
`civic` and `lotshape`, which are the test models this stream changed (civic: the police 2x2 look is now installed;
lotshape: the police hall 3x2 installed turned as 2x3 and the park 2x3 added). The other 8 non-SC4 cases (testmodels,
bld, kenney, styles, ports, landmarks, landmarkdesc, sharp) are byte for byte main's.

## 5. Files

Listed in `re/sessions/STATUS_civlot.md` ("files owned"). Local tools: `work/lab.py` (lotshape's lab pointed at
dev\civlot), `work/match_town.py`. Logs: `work/resize_run*.log`.
