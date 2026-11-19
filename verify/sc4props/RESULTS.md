# sc4props results (round 2026-11-19g): SC4 lot props baked into converted buildings

**Verdict: done in Python and in the page, byte-identical.** `sc4conv.py --deps "<BSC Common Dependencies Pack
V9e.zip>"` reads the 1.7 GB zip by streaming (indexed once in 20 s, then cached), places the fences, trees, cars and
flower beds of each building's SC4 lot around the house in its own OBJ (`<stem>_props.obj`), so bldimport draws them
in every SC3 view and zoom, and lists every prop it could not place. On the JMyers pack: **486 of 5,190 prop rows
placed on 72 of the 110 buildings**; 3,454 rows name 54 prop ids that are in no pack given (the two most used,
`1EDF0000` 1,380 rows and `28330000` 804, are by their id pattern SC4's own props [UNCERTAIN: no SC4 install read]).
The per-building switch is `x_sc4.props.on` in models.json (a rerun keeps the player's choice; `--no-props` writes them
off). The page (`sc4web.js`) does the same when the player picks the BSC zip together with the download in "Open SC4
.zip": `sc4_props.mjs` **130 of 130**. In game: section 5.

Nothing from the packs is in the repository or `docs/`. Pictures in `owner_shots/` are local, for the owner.

## 1. Command

```
py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder> --out <folder> --deps "<BSC Common Dependencies Pack V9e.zip>"
          [--deps <another pack>] [--deps-cache DIR] [--no-props]
py -3.12 re/tools/sc4conv/deps.py index|find <pack> [prop ids]       # the index alone / what an id resolves to
```

Cache: `%LOCALAPPDATA%\sc4conv\` (`<zip>-<size>-<mtime>.idx.json` 17,410 prop exemplars + 1,481 cohorts, `.map.npy`
789,999 S3D / FSH locations, `entries\` the fetched prop models and textures). First run on the JMyers pack: index
20 s + fetch 4 s (4 of 171 DBPF files, 224 entries); later runs read nothing from the zip.

## 2. How a lot prop becomes part of the house (`props.py`, SC4_FORMATS.md 9)

| step | rule (evidence) |
|---|---|
| lot | the building's smallest SC4 lot (1x2 over 1x3 for the JMyers houses) |
| resolve | the download first, then each `--deps` pack, a later file winning. A family id: its members active on 1 July, sorted, member (row index) mod count. Seasonal trees: the lot holds four variants at one spot with SimulatorDateInterval 365 and their own start + duration (0xCA7515CC / 0x4A764564); the summer one is kept (378 rows of another season dropped) |
| model | Resource Key Type 1, or the first state-0 record of Type 4 (fences, seasonal trees); Type 0 not read |
| frame | the street is the lot's +z edge (front setback 13.3-13.7 m on every 1x2 / 1x3 lot), house rotation 2 = lot frame unturned; a prop turns by (its rotation - the house's) quarter turns in the sense the BAT views turn, checked on the Four Seasons corner lot's driveway textures [UNCERTAIN: no SC4 screenshot compared] |
| views | per SC3 rotation slot, the prop's zoom-5 view whose SC4 camera is 22.5 degrees from the slot's, as for the house; a 7-vertex box view gets its back walls + floor (cut-outs show what SC4's camera saw, as for the house) |
| SC3 lot | a 16 m (n x 16 m) window in the house's frame: across the lot it keeps the SC4 lot's own width (the house off-centre as in SC4), along the depth it starts at the house's back wall and keeps the front yard. Props whose centre is outside: left out (866 rows). Props reaching past the edge by up to 1 m (fences on the SC4 lot edge): moved in; more: left out. One zero-area triangle spans the window so bldrender's centring puts the window on the SC3 lot |
| files | `<stem>.obj` unchanged (the house alone, byte for byte as before), `<stem>_props.obj` + `.mtl`, prop textures `sc4prop_<group>_<instance>.png` once per pack texture. models.json `file` names the props OBJ while `x_sc4.props.on` |

`x_sc4.props` per building: `on, lot, rows, placed, nudged, outside_sc3_lot, other_season, missing, unreadable,
window_m, used [[name, count]], missing_ids [[id, count]]`. The report lines (printed by sc4conv.py, in the page note):
"Lot props: 486 of 5190 prop rows placed (72 buildings), 866 outside the SC3 lot, 378 of another season, 3454 in no
pack given, 6 without a readable model" and "Props not found (54 ids, rows in brackets; ...): 1EDF0000 (1380), ...".

Not done: lot textures (driveways, paths; their FSH are in the BSC pack, group 0x0986135E), so cars stand on SC3's
lawn. Clipping a view box at the lot edge was tried and dropped: it cut away the faces some SC3 views see (a 26.6 m
fir showed only its crown in two of the four views).

## 3. Pictures (offline, bldrender at zoom 4, x2)

| file | what |
|---|---|
| `01_props_vs_none_a.jpg` | 56 Amber Creek Road (board fences), 14 Orange Street (white rail fence, car), Golden West (car, fence): the four SC3 views without and with props |
| `02_props_vs_none_b.jpg` | 1717 13th Street (pine, car, heather), 1515 Spring Crest Street (car, flower beds), 893 Auburn St. |

## 4. Tests

| check | result |
|---|---|
| `sc4_props.mjs` (new, after `sc4_props_setup.py`) | **130 of 130**: the BSC zip streamed by the page route (size + slices + stream, never read whole), index counts = Python (171 / 17,410 / 1,481), 110 buildings OBJ + MTL (house and props) byte for byte and textures pixel for pixel, 80 prop textures (sc4prop_*.png), models.json, the file list, `--no-props`, the rerun switch, bldweb pack = `bldimport.py pack` (11 files + ids.json), every frame |
| `run_all.sh` (test slot, after main 7f41ebe (airsea) was merged in: its ports steps and the 2 props steps both kept; pristine `stageelease`, JMyers zip + `sc4_jmyers_homes\jar`, `stage\st_packs\sc4`, SC3PACK_PACKS=`stage\st_packs`) | **28 of 28 steps** (`work/run_all2.log`): 19 base + 3 SC4 + 4 SC4 packs + 2 props. The existing SC4 checks are unchanged in what they compare (models.json now carries `x_sc4.props` on both routes) |

## 5. In game

**All 12 grew in Sacramento by the first autosave (2.4 game-run minutes): the 6 designs with the most placed props,
each installed twice, with and without props, 101 lots in all.** `bld_lab.py` (test slot, `dev\sc4props\tree`,
windowed 1600 x 1000, posted input only, churn `anarchy_res=5000`, speed 4, autosave 150 s), models folder
`work/lab1/` (the converter's output with each of the 6 designs entered twice: `<stem>_props.obj` "(props)" and
`<stem>.obj` "(no props)").

| design | props placed | id with props: lots | id without: lots |
|---|---|---|---|
| 1515 Spring Crest Street (Blue Ridge) | 3 | 38021: 3 | 38022: 5 |
| 893 Auburn St. (BonnaVilla) | 2 | 38029: 6 | 38030: 7 |
| 14 Orange Street (Destiny) | 7 | 38045: 7 | 38046: 6 |
| Golden West | 4 | 38074: 16 | 38075: 8 |
| 56 Amber Creek Road (Heritage) | 8 | 38076: 6 | 38077: 9 |
| 1717 13th Street (Liberty) | 3 | 38098: 4 | 38099: 11 |

Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every lab run logs at start. 27 zoom-3 / zoom-4 dumps
(`runs/run2/fd/`, PNG, no BMP left). The houses were found in the zoom-4 dumps by their own frames
(`work/find_in_dump.py`, score >= 0.6 of the opaque pixels): 11 of the 12 ids (not 38021, Blue Ridge with props: its lots were outside or covered in the dumps taken, so shot 04 has no crop for it). The first run
(run1) gave nothing: a relative `--out` made the game's log path relative to `Apps\`, so the lab never saw the city
come up.

| file | what |
|---|---|
| `03_sacramento_props_vs_none_a.jpg`, `04_..._b.jpg` | per design the house without and with props as the game drew it (zoom 4 crops x2, boxed) |
| `05_sacramento_zoom4_boxed.jpg` | one whole zoom-4 dump, the props houses boxed yellow, the no-props ones blue |

How it looks (03 / 04): the fences, cars and trees stand on the house's own lot and move with it; the lot is still
SC3 lawn (no SC4 lot textures), and SC4's own shrubs and flowers (the missing `1EDF0000` / `28330000`) are absent.
[Owner call: whether the props are worth it per design, and whether the default should be on.]

## 6. Files

Repo (worktree `dev\sc4props\wt`, branch `child/sc4props`, nothing committed): `re/tools/sc4conv/deps.py` (new),
`props.py` (new), `sc4conv.py`, `dbpf.py`; `re/tools/bldimport/sc4web.js`; `webtest/sc4_props_setup.py`,
`webtest/sc4_props.mjs` (new, need `git add -f`), `webtest/run_all.sh` (+2 steps when the 6th argument's folder holds
the BSC zip), `webtest/pagetest.mjs` + `pagetest.js` (`--sc4deps`); `re/analysis/SC4_FORMATS.md` section 9.
