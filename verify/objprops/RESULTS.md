# objprops results (round 2026-11-24c): the game's own props on the free part of an OBJ building's lot

**Verdict: done in Python and in the page, byte identical (suite 41 of 41).** Owner 2026-11-24: "skyscraper doesn't have
anything on its floor?". OBJ growables now get props and, for shops, offices and industry, a paved lot ground, both read
at install time from the player's own SimCity 3000 install: the Building Architect's prop library
(`Apps\Res\BA\PROPS`) and ground paints (`Apps\Res\BA\PAINTS\GROUND`). Nothing of EA's art is in git, docs or the sample
pack. In game (Berlin): all four tracked pack buildings grew, the frames the game drew match ours (props included), only
the usual start-up fault line.

## 1. Where props can come from (evidence: re/analysis/BUILDING_ART.md section 8)

| candidate | verdict |
|---|---|
| stock building frames | the dressing is painted into the one lot bitmap per frame: nothing to cut out |
| `Apps\Res\BA\PROPS` | **used**: 421 files, per prop 4 view BMPs (24-bit, key 255,0,255, 32 to 256 px) + a `.met` line per orientation with the box in BA grid units (8 per cell). 32 px per grid unit = 256 px per cell = 4 x zoom 3. View j = SC3 slot j (semi1's cab turns counter-clockwise view to view) |
| `Apps\Res\BA\PAINTS\GROUND` | **used**: 31 TGA paints (types 2 and 10), one per class set as the lot ground |
| `Apps\BACustom\Props` | 4 sample props only |
| `Landscape.DAT`, `FloraSets\`, `Vehicles.DAT` | not read: terrain trees and traffic drawn by the engine per cell; the BA set already covers trees and cars |

Why the BA set: Maxis' own cut-outs made to dress SC3 lots, lit by the BA renderer, with their size, at higher resolution
than any game zoom, and in every SC3U install.

## 2. How (re/tools/bldimport/bldprops.py, transcribed in bldweb.js)

- A prop is a billboard in the 3D render: one vertical quad per slot through the ground point under its lowest opaque
  row, one texel per 1/256 cell, so the BMP lands on screen as the BA drew it, at the zoom's scale, and the model's
  z-buffer hides what stands behind it. bldrender kind 3: texel as is, light 1, no shadow cast, no tone, vibrance,
  grain or contrast. The ground paint replaces the lawn texture (one tile per cell) and keeps the lawn's light and rim.
- Placement: BA grid cells under any model triangle's (u, v) box are taken. Per class a list of props and counts, each
  tried in an order hashed from the model's file name; first box with all cells free inside the lot wins; cars,
  trucks and lamps must touch the lot edge. Same model, same props.
- What each class gets:

| class | ground | props |
|---|---|---|
| houses 3100-3599 | lawn | a car, deciduous tree, small trees, pines, shrubs, garden, pool, lawn chairs, clothesline |
| apartments 3600-4999 | lawn | cars, trees, cypress, playground, picnic table, lamps, benches, planters, shrubs |
| shops 5000-5999 | parking lot1.tga | cars, van, lamps, small tree, benches, planters, newsstand, bin, postbox |
| offices 6000-6999 | skyscraper base1.tga | fountain, trees, tall and small cypresses, car, lamps, planters, cafe tables, benches, bin |
| industry 8000-9299 | concrete lot.tga | truck, van, pickup, tank, barrels, garbage, tyres |

  Not for farms (9300), .bld files, SC4 conversions, landmarks, civic looks, rewards, ports, non-square lots.
- Switch per building: models.json `x_props: {"on": false}` (default on), the page's new "Lot props" box (ticked
  removes the key, so files keep their shape). Run switch (Python): `SC3BLD_PROPS=0`. Missing props in an install are
  left out and named in a note line. Render cache key covers bldprops.py and the bytes of every prop file read.

## 3. Counts (sample pack, rendered in a copy: dev\objprops\work\sample_pack)

236 props on the 18 buildings: each 1x1 house 10 (pines, shrubs, flowering bushes, lawn chairs, clothesline), Big Villa
17, Wide Apartments 18, Apartment Tower 18, Three-Storey Block 15, Corner Shop 9, Shop Row 14, Office Block 27, Glass
Tower 21, Skyscraper 27, Workshop 1, Smoke Works 4, Chimney Factory 4, Long Factory 11.

## 4. Checks

| check | result |
|---|---|
| Python vs page, scratch compare (villa, shop row, long factory, glass tower) | 80 of 80 frames byte identical, same plans |
| `run_all.sh` normal run, six arguments + SC4INSTALL, test slot (`dev\objprops\work\runall3.log`) | **41 of 41 steps**, golden.mjs PASS (every file + frame, 10 cases) |
| cases whose goldens are new (entries with props or a ground paint) | kenney 3 of 3 entries, testmodels 3 of 3, styles 4 of 4, sharp 4 of 4 (some with 0 props but a ground paint). No entry with props in bld, civic, landmarks, landmarkdesc, lotshape, ports, sc4: those entries render through the old path (not byte compared against a main-code run) |
| in game, Berlin, dev\objprops\tree (run sky_berlin3 growth, churn 5000 / 5000) | Skyscraper 38011 5 lots, Glass Tower 38010 15, Office Block 38009 1, Apartment Tower 38006 20 in the last autosave |
| pictures from that autosave (run sky_berlin4, cam settle 8 s) | our frames found in the game's dumps by `work/find_in_dump.py`: 38011 0.84 / 0.80 / 0.59 of opaque pixels equal, 38010 0.82, 38006 0.88, 38009 0.60 |
| faults | only `0xC0000096 at SC3U.exe+0x84122` at start-up, every run |
| sync_css.py | `--publish` done, `--check` in sync, docs/buildings/importer/bldweb.js = source |

Two earlier Berlin runs gave no picture: sky_berlin2 dumped at 0.7 game-minutes (lots still construction sites),
sky_berlin3's camera failed ("camera call failed", 1-2 fps on the busy PC). `work/sky_lab.py` now has `--settle`,
`--spots-save` and `--cam-settle`.

## 5. Pictures (looked at)

| file | what |
|---|---|
| `verify/bldpack/owner_shots/00_whole_pack_z3.jpg` (new; old one `_pre_objprops`) | the 18 buildings with props, zoom 3 view 0 |
| `verify/bldpack/owner_shots/13_berlin_skyscraper_zoom3.jpg` (new; old one `_pre_objprops`) | two Skyscrapers grown side by side in Berlin, zoom 3 view 0. Their plazas are mostly behind a stock tower and power pylons in this view |
| `verify/bldpack/owner_shots/13b_berlin_skyscraper_zoom4_view1.jpg` | the same pair from view 1 at zoom 4: plaza paving, trees, lamps, benches, a parked car at the bases. The better post picture |
| `verify/objprops/owner_shots/berlin_z3_skyscrapers_boxed.jpg` | the whole zoom-3 dump, the three Skyscrapers boxed |
| `verify/objprops/work/small_before_after_z4.png` | 1x1 lots and the Glass Tower before / after at zoom 4 |

## 6. Files (dev\objprops\wt, nothing committed)

re/tools/bldimport/bldprops.py (new, `git add -f`), bldrender.py, bldimport.py, bldweb.js, classifier.html;
docs/buildings/importer/{index.html, bldweb.js} (sync_css --publish); docs/buildings/index.html (make_docs.py; it also
carries a `baked_sharp` sentence from another round's template edit); re/analysis/BUILDING_ART.md section 8.
MAIN, gitignored: verify/bldpack/work/guide_template.html (Lot props section, backup `.pre_objprops`), verify/objprops/.
The `re/tools/netmod/__pycache__` changes in the worktree come from the suite run, not this work.
The shipped sample-pack zip is unchanged: it holds no frames, players get the props when they install.
