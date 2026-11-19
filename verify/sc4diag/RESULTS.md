# sc4diag results (round 2026-11-19c): diagonal SC4 houses off by default

**Verdict: the converter now finds the houses set at 45 degrees in the SC4 data and writes them off, and none grew
in Sacramento.** The deciding field is the building's **foundation model**, not the lot. On the BSC JMyers Homes
Pack V3.1, 36 of 110 buildings are diagonal: every colour of Acorn, Allegheny, Empire, Fleetwood, Four Seasons and
Homestar. `sc4conv.py` and the importer page (`sc4web.js`) write them with `enabled: false`, a note, and
`x_sc4.diagonal: true`, and the page puts a "diagonal" badge on their cards. Python and the page stay
byte-identical (`run_all.sh` 13 of 13 steps). One install made by the page grew in Sacramento for 10 game-run
minutes: 0 diagonal houses in all 5 saves (62 to 80 converted lots, all 12 straight designs). In the previous
round's saves 22 to 34 lots were diagonal.

Nothing from the pack is in the repository or `docs/`. The pictures in `owner_shots/` are for the owner only.

## 1. How a diagonal house shows in the SC4 data

| candidate | what the pack shows | usable |
|---|---|---|
| lot object rotation (lot exemplar 0x88EDC900.., word 2) | 0-3 only, quarter turns (42 of 42 lots, the building row has 1, 2 or 3) | no: no 45-degree value exists |
| lot corner flag 0x4A4A88F0 | 8 = one road side (24 lots), 9 / 12 = two sides (18 lots). Set on Homestar, Commodore, Fleetwood, BonnaVilla and Colonial lots as well | no: also set on straight houses |
| lot name "Corner Lot" | Acorn, Four Seasons, Allegheny, Empire. Missing on Fleetwood and Homestar | no: a name, and it misses 2 designs |
| occupant size / S3D view box | an axis-aligned box: Acorn and Allegheny 11.99 x 11.99 m, but Homestar 13.97 x 14.12, Fleetwood 15.57 x 14.48 | no |
| **foundation model** (building exemplar 0x88FCD877 -> type 0x11 exemplar, group 0x361CF9D5, its S3D model) | real geometry (25 to 125 vertices, SC4_FORMATS.md 6), one per design. Its outline runs along the box axes or at 45 degrees | **yes** |

The rule (`views.foundation_diagonal`, the same steps in `sc4web.js`): read the foundation's zoom-5 rotation-0
mesh, and keep its **outline** edges: an edge with one triangle, or more than two, or two triangles that are not
coplanar (this drops the inside diagonal of a flat quad). Keep the horizontal ones (height change <= 0.05 m,
length >= 0.05 m). An edge is diagonal when the shorter of |dx|, |dz| is at least half the longer one, which is
26.6 to 63.4 degrees from an axis. The house is diagonal when diagonal edges make at least half the outline length.
It uses only plain float arithmetic in a fixed order, so the page gets the same bits.

| design | foundation | 45-degree share | | design | foundation | 45-degree share |
|---|---|---|---|---|---|---|
| Abby Glen | JFM_AbbyGlen_FND_03 | 0.00 | | Fleetwood | JFM_Fleetwood_FND | **1.00** |
| Acorn | JFM_Acorn_FND_01 | **1.00** | | Four Seasons | JFM_FourSeasons_FND_01 | **1.00** |
| Allegheny | JFM_Allegheny_FND_01 | **1.00** | | Golden West | JFM_GoldenWest_FND_01 | 0.00 |
| Blue Ridge | JFM_BlueRidge_FND_01 | 0.00 | | Heritage | JFM_Heritage_FND_02 | 0.00 |
| BonnaVilla | JFM_BonnaVilla_FND | 0.00 | | Homestar | JFM_Homestar_FND_01 | **1.00** |
| Commodore | JFM_Commodore_FND 01 | 0.00 | | Lavoy | JFM_Lavoy_Foundation_01 | 0.00 |
| Craftsman | JFM_Craftsman_FND | 0.00 | | Liberty | JFM_Liberty_FND_01 | 0.00 |
| Destiny | JFM_Destiny_FND_01 | 0.06 | | Narrow Lot Colonial | JFM_Narrow Lot Colonial_FND | 0.00 |
| Empire | JFM_Empire_FND_01 | **1.00** | | Shotgun | JFM_Shotgun_FND | 0.00 |

The values sit at 0.00-0.06 or at 1.00, with nothing in between, and the same in all four rotations of every
foundation. All colours of a design name the same foundation (110 of 110 buildings name one), so on this pack every
design is either straight in all its colours or diagonal in all of them.

**Check by eye** (`owner_shots/00_check_sheet.jpg`, one sheet): one row per design, its foundation outline from
above, and every colour's SC4 view S picture with the foundation outline drawn on it through that view's fitted
camera (`views.fit_camera`, the same projection the converter uses). The 45-degree outline (red) follows the walls
of all 36 Acorn, Allegheny, Empire, Fleetwood, Four Seasons and Homestar pictures. The straight outline (yellow)
follows the walls of the other 74, Shotgun's 8 colours included. No colour differs from its design.

## 2. What the converter writes

- `enabled: false` for a diagonal building, also with `--all`. `--diagonal` (page: `convert({ diagonal: true })`)
  treats them as any other building: that output equals the previous round's 18-on `models.json` layout.
- `notes` begins with: "Diagonal, off by default: the SC4 author set this house at 45 degrees on its lot (its
  foundation JFM_Acorn_FND_01 runs at 45 degrees for 100% of its outline), and SC3 has no diagonal buildings."
- `x_sc4.diagonal` (bool) and `x_sc4.foundation` ({name, share_45}, or null when there is no foundation).
- Colour pick (`pick_colours`): the k-th design still gets its k-th colour. If that colour is diagonal, it gets the
  k-th of its straight colours, and none if all are diagonal. On JMyers the 12 straight designs keep the colour they
  had before (same ids 38000, 38021, ...), and the 6 diagonal ones have nothing on: 12 enabled, previously 18.
- A rerun over an old `models.json` turns a diagonal building off unless the player switched it on by hand (the
  `x_sc4.auto` merge).
- The page: a "diagonal" badge (struck through, like "off") on each of the 36 cards, with the reason as its tooltip,
  and the report line "110 models, 12 enabled, 36 set at 45 degrees in SC4 (6 designs) off by default since SC3 has
  no diagonal buildings". `classifier.html` is not edited: `sc4web.js` watches `#grid` and adds the badge.
- Guide (`docs/buildings/index.html` SC4 section, and the pack template `verify/bldpack/work/guide_template.html`):
  one sentence in step 3, one item in the limits list.

## 3. Evidence

| check | result |
|---|---|
| `run_all.sh` (test slot, pristine `dev\sc4diag\tree`) | **13 of 13 steps**. `sc4_golden.mjs` 130 of 130: 110 buildings OBJ / MTL / 4 textures, models.json byte-identical, folder = zip, rerun merge, the 3 new checks below, 11 game files + ids.json, 240 of 240 frames. pagetest sc4 18 of 18 |
| new: diagonal off with the note | 36 of 110, 0 of them on, every one with the note, no note on a straight building, every straight design exactly 1 on |
| new: `--diagonal` route | the page's models.json = `sc4conv.py --diagonal`'s (250,520 bytes, 18 on) |
| new: colour pick on mixed designs | 8 made-up designs (the JMyers pack has no mixed one): page `a - g j - l p r` = Python |
| new (pagetest sc4): the page marks the diagonal cards | the 36 badged cards = the 36 diagonal entries, tooltip with the reason |
| page install (`pagetest.mjs --case sc4 --sc4zip --apply`) | 12 buildings rendered + installed by the page, 18 of 18 checks, every game file byte-identical to `bldimport.py` |

## 4. In game: Sacramento, page install

`bld_lab.py --tag page1` (test slot, windowed 1600 x 1000, posted input only, mods of `dev\sc4diag\inst`, churn
`anarchy_res=5000`, speed 4, autosave every 150 s). Counts from the saves (`count_saves.py`: every occupant in the
converter's id range 38000-38109, mapped through `ids.json` to its model and its `x_sc4.diagonal`).

| save | game-run minutes | stock occupants | converted lots | diagonal | designs grown |
|---|---|---|---|---|---|
| 1 | 2.5 | 11,912 | 62 | **0** | 12 of 12 |
| 2 | 4.9 | 11,912 | 62 | **0** | 12 |
| 3 | 5.0 | 11,628 | 64 | **0** | 12 |
| 4 | 7.5 | 11,453 | 80 | **0** | 12 |
| 5 | 10.0 | 11,386 | 77 | **0** | 12 (4 to 10 lots each) |
| before (round sc4web, 18 on, its saves 1 / 3 / 4) | 2.4 / 5.0 / 7.5 | | 84 / 117 / 99 | 22 / 34 / 25 | 18 |

Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every lab run logs at start. **The first launch of this run
crashed** 13.5 s in, as the city finished loading: `0xC0000005 at SIMCITY.DLL+0x1783`, NULL read (`runs/page1_fault1/resize.log`
line 215), before the game was unpaused and before any converted building was drawn. The retry of the same tree
and files ran clean. [UNCERTAIN: cause not read; no earlier run in `verify/` logged this address. Not linked to this
task's change, which only changes which models.json entries are on.]

Pictures (`owner_shots/`, local only: they show the pack's houses):

- `00_check_sheet.jpg`: section 1's check sheet, every design and colour.
- `01_sacramento_page_install_zoom4.jpg` (820 x 1180, phone-sized portrait): one Sacramento street at zoom 4, 6
  converted houses of 5 designs (Commodore, Craftsman, Destiny, Golden West, Lavoy) boxed in yellow among stock
  houses, numbered legend. Found in the dump by their own frames (the finder of verify/sc4conv/work).
- `02_sacramento_page_install_zoom4_unmarked.jpg`: the same street without boxes.

Run files: `runs/page1/` (`counts.json`, `diag_counts.json`, `resize.log`, `fd/*.png`, `saves/`), no BMP left.

## 5. Limits

- A building that names no foundation, or whose foundation cannot be read, is not checked (`x_sc4.foundation:
  null`) and is treated as straight. Every JMyers building has one. [UNCERTAIN: other packs. A BAT author can
  leave out the foundation, and then only the pictures would tell.]
- The rule reads the foundation's outline. A straight house on a foundation with 45-degree corners cut off would
  stay straight as long as the cut-offs are under half the outline. Not in this pack: the straight designs have
  0.00 to 0.06.

## Files

Worktree `dev\sc4diag\wt`: `re/tools/sc4conv/views.py`, `re/tools/sc4conv/sc4conv.py`,
`re/tools/bldimport/sc4web.js`, `docs/buildings/importer/sc4web.js` (`sync_css.py --publish`),
`re/tools/bldimport/webtest/sc4_golden.mjs`, `golden_setup.py`, `pagetest.mjs`, `pagetest.js`,
`docs/buildings/index.html`. In MAIN (gitignored, local): `verify/bldpack/work/guide_template.html`,
`verify/sc4diag/` (this file, `count_saves.py`, `work/shots.py`, `runs/`, `owner_shots/`).

Whole suite: `test-slot bash re/tools/bldimport/webtest/run_all.sh <work> <pristine tree> <stage\kits> <SC4 .zip> <the same download unpacked>`.
