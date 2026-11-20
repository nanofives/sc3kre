# sc4ci results (round 2026-11-20): SimCity 4 commercial and industrial buildings, tested and fixed

Input: Maxis' own commercial and industrial growables from the Steam SimCity 4 Deluxe on this PC (read in place, EA's
files: nothing of them or made from them is in the repository or docs), the community packs in `MAIN\stage\st_packs\sc4`
and the owner's share. Pictures in `owner_shots\` (gitignored, owner only). Worktree `dev\sc4ci\wt`, nothing committed.

**Verdict.**

- **Class rule: kept, now with numbers (section 2).** SC3 gives a building its jobs from its class only: jobs per cell
  of `SC3ValveLayer.ini [AgentValveEffects]` (valve 7000) times the lot's cells. Against that, the tool's cuts (<= 100
  jobs light, <= 1,000 medium, else dense) put 52 of 95 SC4 shops and 65 of 124 offices within a factor 2 of SC4's own
  jobs. A per-cell rule (the cut halfway, in log, between SC3's per-cell values) does no better: 52 and 66. Every other
  shop and office is outside what any SC3 class can give on its lot (30 shops and 38 offices have more than twice the
  densest class's jobs, 13 and 20 fewer than half the lightest). Industry: SC4's factories hold 2.5 to 23 jobs per SC3
  cell (median 4.8-7.5), below SC3's lightest industrial class (17 per cell), so the lot decides the class (the lightest
  class with a base of that size). IM (manufacturing) stays dirty: its SC4 air pollution (median 8) is ID's (9), twice
  IHT's (4).
- **Fixes.** (a) A class without a stock base of the lot is no longer written as on: bldimport skipped it at install
  ("class 9300 has no 4x4 lot"), now it gets no class and is off with the reason (1 farm). (b) No dirty class has a 4x4
  base, so 4x4 dirty and manufacturing buildings (7 of SC4's own) take the dense clean class 9100 (the only 4x4 industry,
  air pollution 100 against 8500's 125), with the reason in the note. (c) The atlas reader left 13 of the install's
  buildings out: 48 pieces with no texture area made 11 fail (10 growables and the Large High School), the 2 px fit limit
  2 more offices. All 310 growables and all 113 civic buildings now convert (section 5).
- **Maxis' C and I growables are convertible for testing, all off** (section 1): `sc4conv.py <install> --growables`,
  the page with `?sc4growables` in its address (Open SC4 game then adds them). Off by default in both: whether players
  get them is the owner's call (section 7).
- **In game: 8 of 9 grew** (section 4). Berlin by the first autosave (2.5 game-run minutes): Small Shops (5100, 1x1) 6
  lots, Retail Stores (6100, 2x2) 3, Lam Banking (5500, 2x2) 4, Ferrrara Inc. (a 55 m office, 6700, 3x3) 3. Madison:
  Eyler Refining (dirty, 8300) 4 and Lee Avionics (high-tech, 8700) 4 by save 1, Vilett Textiles (manufacturing, 8500,
  3x3) 1 at 4.9 min, Pumpkin Acres (farm, 9300, 1x1) 1 at 4.9 min. **Alvin's Acres (farm, 2x2) never grew** (two Madison
  runs and Farmsville, 15 saves): neither city develops any 2x2 farm lot (the stock 2x2 farms Farm House and Greenhouse
  and their style twins hold 0 lots in every Madison save). The lot, not the class or the weight: SC3's farms are 1x1
  fields, and 6 of SC4's 7 farms need 2x2 or more.
- **Byte identity and suite** (section 6): the page = sc4conv.py on the growables subset (230 files) and on the whole
  install (113 civic models, the Large High School included). `run_all.sh`: 40 of 40 steps passed.

## 1. Maxis' commercial and industrial growables from the install

`sc4conv.py "<install>" --growables --out <dir>`: the 113 civic / park / reward / landmark buildings as before, plus every
building whose SC4 purpose is 2 (service commercial), 3 (office), 5 (agriculture), 6 (dirty), 7 (manufacturing) or 8
(high-tech) and that is not one of those. Every growable entry is written off (`enabled` false, the note ends "SimCity 4's
own growable from your game, converted for testing: off by default."), `--all` turns them on like any colour.

| | count |
|---|---|
| install buildings with a model | 713 (743 with the 30 without one) |
| C and I growables | 310: 95 shops (CS $ 23, $$ 38, $$$ 34), 124 offices (CO $$ 60, $$$ 64), 7 farms, 34 dirty, 25 manufacturing, 25 high-tech |
| converted | 310 of 310 (before the atlas fixes 298: 12 failed) |
| with a class | 305; 5 without: 4 need a 5x5 or 6x6 lot (2 IM, 2 IHT), 1 farm needs 4x4 and SC3 farms are 1x1 to 3x3 |
| classes | 6100: 73, 5500: 66, 6700: 57, 8300: 33, 8700: 13, 5100: 12, 8500: 12, 9100: 12, 5700: 11, 9300: 6, 8100: 5, 8900: 5 |
| lot props and textures (the 423 buildings, civic included) | props 3,883 of 11,615 rows placed (380 buildings), 4,810 outside the SC3 lot, 2,868 without a readable model; textures 4,390 of 5,962 rows drawn (421 buildings), 1,165 of them cut at the lot edge, 1,572 outside |
| time | Python 6 min 0 s for the whole install with growables (2 min 16 s without, sc4civ) |
| output | 423 models, 5,741 files, 394 MB |
| in a game | 9 buildings made a 1,531,748-byte `B1D10001_bldimport.DAT` (about 170 KB each): all 305 would be about 52 MB |

## 2. The class rule against SC3's own jobs

### 2.1 What SC3 gives a building

bldimport copies the stock base building of the entry's class and lot (batgrow.class_table). A stock C or I exemplar
holds no jobs (TKB1 props 0x64 name, 0x65 class, 0x66 footprint, 0x6B, 0x6C only, read on all 23 C and I bases). Jobs come
from the class: `SC3ValveLayer.ini [AgentValveEffects]`, `valve:supply:demand`, applied per cell of the footprint
(`effect * footprint`, SIMRCI 0x1002f5af, re/analysis/PORTS_AIRPORTS.md). Valve 7000 = jobs (abandon_probe):

| class | jobs per cell (7000 demand) | 1x1 / 2x2 / 3x3 / 4x4 lot | lots with a base |
|---|---|---|---|
| 5100 C light low | 17 | 17 | 1 |
| 5500 C light high | 16 | 16 / 64 | 1, 2 |
| 5700 C medium low | 59 | 236 / 531 / 944 | 2, 3, 4 |
| 6100 C medium high | 57 | 228 / 513 | 2, 3 |
| 6300 C dense low | 123 | 492 / 1,107 | 2, 3 |
| 6700 C dense high | 117 | 1,053 / 1,872 | 3, 4 |
| 8100 I dirty light | 17 | 17 | 1 |
| 8300 I dirty medium | 61 | 244 | 2 |
| 8500 I dirty dense | 127 | 127 / 508 / 1,143 | 1, 2, 3 |
| 8700 I clean light | 17 | 17 / 68 | 1, 2 |
| 8900 I clean medium | 59 | 236 / 531 | 2, 3 |
| 9100 I clean dense | 123 | 1,107 / 1,968 | 3, 4 |
| 9300 farm | 10 | 10 / 40 / 90 | 1, 2, 3 |

Where a class develops (`SC3ZoneLayer.ini [ZoneDeveloperDescriptions]`): commercial light zones grow 5100 (land value
1-89) and 5500 (90-255) only, medium zones add 5700 / 6100 (130 and up), dense zones add 6300 (60-180) / 6700 (181 and
up); industry: 8100 / 8700 / 9300 in light zones (9300 up to land value 90), 8300 / 8900 from medium, 8500 / 9100 in
dense. SC3's commercial "wealth" is that land value band: two bands, SC4 has three wealths. $ -> low, $$ / $$$ -> high is
kept as the tool's choice (no SC3 number to measure it against).

### 2.2 SC4's jobs (capacity 0x27812834, summed over its demand groups)

| SC4 group | buildings | jobs min / median / max | SC3 lot (from the footprint) 1x1 / 2x2 / 3x3 / 4x4 / larger | jobs per SC3 cell median |
|---|---|---|---|---|
| CS $ | 23 | 7 / 59 / 173 | 12 / 10 / 1 / 0 / 0 | 26.0 |
| CS $$ | 38 | 20 / 416 / 2,751 | 7 / 15 / 12 / 4 / 0 | 66.1 |
| CS $$$ | 34 | 35 / 431 / 3,978 | 7 / 12 / 11 / 4 / 0 | 82.2 |
| CO $$ | 60 | 16 / 103 / 6,798 | 4 / 26 / 22 / 8 / 0 | 19.5 |
| CO $$$ | 64 | 26 / 533 / 21,435 | 7 / 22 / 25 / 10 / 0 | 124.0 |
| IR (farms) | 7 | 2 / 6 / 13 | 1 / 5 / 0 / 1 / 0 | 1.5 |
| ID (dirty) | 34 | 5 / 30 / 158 | 5 / 20 / 7 / 2 / 0 | 7.5 |
| IM (manufacturing) | 25 | 18 / 32 / 78 | 0 / 13 / 5 / 5 / 2 | 4.8 |
| IHT (high-tech) | 25 | 18 / 40 / 97 | 1 / 12 / 5 / 5 / 2 | 5.5 |

The I-M pack's author names its building after this number (`!I§§--1542 jobs` holds {0x4300, 1542}), which is the only
check that the property is the job count. [UNCERTAIN: whether SC4 scales it at run time; the converter takes it as stored.]

### 2.3 Rules compared (SC3 jobs of the class given / SC4 jobs; shops and offices that fit 4x4)

| rule | shops within x2 | offices within x2 | median abs(log2 ratio) shops / offices |
|---|---|---|---|
| **the tool's: <= 100 jobs light, <= 1,000 medium, else dense** | **52 of 95 (55%)** | **65 of 124 (52%)** | 0.91 / 0.95 |
| per SC3 cell: <= 31 light, <= 84 medium (log midpoints of 16.5 / 58 / 120) | 52 (55%) | 66 (53%) | 0.85 / 0.91 |
| best: the class of a base of that lot nearest in log | 52 (55%) | 66 (53%) | 0.85 / 0.91 |

The per-cell rule would move 21 offices (5500 +5, 6100 -13, 6700 +8) for one more office within x2. Kept. What no rule
can reach (SC4 jobs against the lightest and the densest class with a base of that lot, same wealth or cleanliness):

| SC4 | more than 2x the densest | less than half the lightest | in range | no base of the lot size |
|---|---|---|---|---|
| shops | 30 | 13 | 52 | 0 |
| offices | 38 | 20 | 66 | 0 |
| farms | 0 | 6 | 0 | 1 |
| dirty | 0 | 29 | 3 | 2 |
| manufacturing | 0 | 18 | 0 | 7 |
| high-tech | 0 | 20 | 3 | 2 |

Industry and farms: SC3 always gives more jobs than SC4 holds (SC3/SC4 median 8.7 dirty, 10.6 manufacturing, 3.4
high-tech, 5.8 farms), whichever class. The rule already takes the lightest class with a base of the lot (the jobs cut
of 100 puts all but 6 factories in "light", then the fallback moves them up only as far as a base exists).

Dirty or clean (SC4 "Pollution at center" 0x27812851, air / water / garbage, medians): ID 9 / 7 / 4, IM 8 / 5 / 4, IHT 4 /
2 / 4. IM is close to ID and twice IHT in air: manufacturing -> dirty kept. SC3Pollution.ini air at the centre: dirty
8100 / 8300 / 8500 = 50 / 100 / 125, clean 8700 / 8900 / 9100 = 8 / 50 / 100.

## 3. Lots

SC4's C and I lots are long: of the 1,920 lots naming these 310 buildings, 2x3 559, 1x2 307, 2x2 253, 3x3 236, 3x4 185,
1x3 77, 1x1 75, 4x4 75, 2x4 55, 4x5 19, 3x5 15, 4x6 12, 5x6 11, 2x5 6, 6x6 6, 3x6 2, 5x5 1, 6x7 1. The SC3 lot is the
smallest square that holds the building (lot_for), and props and textures come from the building's smallest SC4 lot,
so the crop is small:

| SC4 | smallest square 1x1 / 2x2 / 3x3 / 4x4 / larger (off) | smallest SC4 lot long | props lot cropped | share of that lot kept (mean, min) | props placed / outside | textures drawn / cut / outside |
|---|---|---|---|---|---|---|
| shops (94) | 26 / 36 / 24 / 8 / 0 | 52 | 8 | 0.96, 0.06 | 686 / 348 | 393 / 106 / 14 |
| offices (115) | 11 / 47 / 46 / 11 / 0 | 62 | 0 | 1.00 | 1,122 / 78 | 851 / 29 / 0 |
| dirty (34) | 5 / 20 / 7 / 2 / 0 | 15 | 2 | 0.98, 0.67 | 203 / 11 | 141 / 10 / 0 |
| manufacturing (24) | 0 / 12 / 5 / 5 / 2 | 16 | 11 | 0.88, 0.67 | 180 / 56 | 135 / 106 / 8 |
| high-tech (24) | 1 / 11 / 5 / 5 / 2 | 16 | 5 | 0.92, 0.25 | 136 / 25 | 140 / 109 / 8 |
| farms (7) | 1 / 5 / 0 / 1 / 0 | 1 | 0 | 1.00 | 111 / 2 | 43 / 7 / 0 |

(Counted on the first full run, 298 converted; the 12 added by the atlas fix are offices, shops and two factories.)
Off for size: 4 (5x5 / 6x6), plus 1 farm on 4x4 (no 4x4 farm base). The worst crops are small shops on a big SC4 lot
(Stratton Spa, a 1x1 building on a 4x4 lot: 6% of the lot kept) and factories whose smallest lot is 2x3 (two thirds kept).

## 4. In game

Tree `dev\sc4ci\tree`, mods of `dev\sc4ci\inst`, windowed 1600 x 1000, posted input and Frida camera calls only, test
slot. Lab `verify/sc4ci/work/ci_lab.py`: tower_lab.py of sc4pass2 with `anarchy_ind` too, and `--from-save` (load an
earlier run's save with churn off at speed 1 and take the pictures of every id: the first pictures came minutes after the
save and the churn had rebuilt those lots by then). Weight 1 for every building, demand not touched, churn
`anarchy_res/com/ind=5000` while growing (the lever of sc4pass2 and the sample pack). The lab starts the game the way
`sc3dev.ps1 run` does (same exe, mods, `SC3RESIZE_WINMEM=0`, `SC3MODS_MULTI=1`: `sc3wait.launch_game`). Faults: only the
start-up `0xC0000096 at SC3U.exe+0x84122` line every run logs. Game PIDs started and stopped by this session: 1076,
17096, 2044, 1816, 16576, 8072, 9136.

Models: `sc4conv.py <install> --growables --only <9>`, every entry switched on, `bldimport.py build --game
dev\sc4ci\tree` (ids 38000-38008). Lots per autosave (occupant layer of the save):

| id | building (SC4) | class, lot | stats of | city | saves (game-run minutes: lots) |
|---|---|---|---|---|---|
| 38003 | Small Shops (CS $, 49 jobs) | 5100, 1x1 | 126 Ben's Diner | Berlin | 2.5: 6 |
| 38002 | Retail Stores (CS $$, 121 jobs) | 6100, 2x2 | 152 Hurt Plaza | Berlin | 2.5: 3 |
| 38001 | Lam Banking (CO $$, 27 jobs) | 5500, 2x2 | 148 Clothing Boutique | Berlin | 2.5: 4 |
| 38000 | Ferrrara Inc. (CO $$$, 1,147 jobs, 55 m) | 6700, 3x3 | 178 Federal Building | Berlin | 2.5: 3 |
| 38004 | Eyler Refining (ID, 18 jobs) | 8300, 2x2 | 163 Furnaces | Madison | 2.5: 4, 4.9: 4 / 7, 7.5: 4 |
| 38005 | Lee Avionics (IHT, 32 jobs) | 8700, 2x2 | 159 Storage Tanks | Madison | 2.5: 4, 4.9: 4 / 3, 7.5: 2 |
| 38006 | Vilett Textiles (IM, 34 jobs) | 8500, 3x3 | 5039 Mine | Madison | 2.5: 0, 4.9: 0 / 1, 7.5: 1 |
| 38008 | Pumpkin Acres (IR, 2 jobs) | 9300, 1x1 | 5012 Chicken Coop | Madison | 0, 0, 1, 0, 1, 0, 1, 1 (8 saves to 12.6 min) |
| 38007 | Alvin's Acres (IR, 6 jobs) | 9300, 2x2 | 5010 Farm House | Madison x 2, Farmsville | 0 in all 15 saves (Madison 7.5 + 12.6 min, Farmsville 4.9 min) |

The occupant class the save records on each picture lot equals the entry's class (6700, 5500, 6100, 5100, 8300, 8700,
8500). Two saves at the same minute are the autosave pair the game writes (sc4pass2 saw the same).

**Why the 2x2 farm does not grow.** Family 25 (the farm rule's family), lots per member (occupant cells / n^2), Madison
before / during the farm run: Plowed Field (1x1) 97 / 50-55, Wheat Field (1x1) 67 / 33-47, their style twins 1505062 /
1505063 20-61 each, Chicken Coop, Tool Shed, Hans Silo, Windmill 0-4 each, **Farm House and Greenhouse (the two 2x2
members) and their twins 0 in every save**. Farmsville (about 1,280 farm lots): Farm House 1, Greenhouse 1, and its farms
did not redevelop during the run (counts only fell), so the run there was stopped after 3 saves. Madison rebuilds farms,
but only as 1x1 fields. So a 2x2 SC4 farm gets no lot to grow on. Pumpkin Acres, the one 1x1 SC4 farm, grew among the
fields.

Pictures (`owner_shots/`, zoom 4 crops around the lot with the converted building's own frame inset top left, local
only):

| file | what |
|---|---|
| `01_Small_Shops_z4.jpg` | Berlin: two Small Shops side by side among stock housing and shops |
| `02_Retail_Stores_z4.jpg` | Berlin: Retail Stores |
| `03_Lam_Banking_z4.jpg` | Berlin: Lam Banking (low flat office) between stock towers |
| `04_Ferrrara_Inc_z4.jpg`, `05_Ferrrara_Inc_z3.jpg` | Berlin downtown: the 55 m office among stock towers |
| `06_Eyler_Refining_z4.jpg` | Madison industry: the refinery between stock factories |
| `07_Vilett_Textiles_z4.jpg` | Madison: the textile mill, 3x3 |
| `08_Lee_Avionics_z4.jpg` | Madison: the high-tech plant |
| `09_Pumpkin_Acres_z4.jpg` | Madison farmland: the farm among stock wheat and plowed fields |

The full frames (zoom 4 in four rotations for the first id of each run, zoom 3 in four rotations and zoom 2 for every
id) are in `runs/shotCom`, `shotInd`, `shotFarm` `/fd`. How they look: as the houses and civic buildings before (SC4's
light painted in, roofs seen from higher up). bldimport notes that Eyler Refining (34.2 x 40.2 m), Lee Avionics (38 x
32 m), Vilett Textiles (48 x 49.7 m) and Alvin's Acres (33.9 x 32 m) overhang their lots a little.

## 5. Reader fixes: atlas pieces

The first full run with growables skipped 12 growables, all with "atlas piece of texture ... is N px off the view's
projection" (2.01-49.47 px), like the Large High School in sc4civ (59.66 px). Over every multi-mesh atlas view of the
install's 713 models (1,558 views, 8,532 pieces):

- **48 pieces have no texture area**: every vertex has u = 1.0 (texture area 0.0 on all 48), in 18 buildings. They cover
  0-52 px^2 of a zoom-5 view (0.0% of it). Their own fit is fine (0.06-0.58 px), but they are not pieces of the screen
  render, so no offset places them (4-60 px off), and on 11 buildings they made the whole building fail. `compose_atlas`
  now leaves out a piece whose triangles cover less than 0.5 texel^2 (`views._uv_area`, `UV_FLAT`; sc4web.js `uvArea`).
- **The other pieces fit without a gap**: largest per-piece error after rounding, over the 8,484 other pieces: above 1.5
  px 26, above 1.58 18, above 2.0 5, above 2.2 0. Two offices failed the 2.0 limit at 2.10 and 2.16 px. `ATLAS_FIT` 2.0 ->
  2.5 (a wrong transform was 4-60 px).

After both: 423 of 423 convert (113 civic, 310 C and I). The 112 civic buildings that converted before are compared
page against Python in the suite's install step (21 of 21, 113 models).

## 6. Byte identity, suite

| check | result |
|---|---|
| `sc4_install.mjs`, new growables lines (`sc4_install_setup.py` runs `sc4conv.py --growables --only <10>`: one of each purpose, a 4x4 dirty factory, a 5x5 factory, a 4x4 farm, a police station) | 230 files (OBJ / MTL / models.json byte for byte, PNG pixel for pixel), file list, notes, classes (CS$ 5100, CS$$ 6100, CO$$$ 6700, ID 8300, ID 4x4 9100, IM 5x5 none, IHT 8700, IR 9300, IR 4x4 none), every growable off, the police look on: 3 of 3 |
| `sc4_install.mjs` whole (in the suite) | 21 of 21: the whole install, 113 models (the Large High School now converts), byte for byte, 84.5 MB read, rerun, subset pack, frames |
| `run_all.sh`, six arguments, `SC3PACK_PACKS`, `SC4INSTALL`, `PROYECTOS_TEST_HUB=off`, test slot | first run 39 of 40: step 34 (the page opens the install) expected 112 cards and got 113 (the High School); expectation set to 113. Rerun: **40 of 40 steps passed** (`sc4_install.mjs` 21 of 21 again) |
| `sync_css.py --check` / `--publish` | in sync; classifier.html + sc4web.js published to `docs/buildings/importer` |
| guide | `make_docs.py --wt dev\sc4ci\wt --tree stage\release --zip <the 2026-11-18 sample-pack URL>`: only the SC4 text of `docs/buildings/index.html` changed, sample-pack link kept, `stage\sample_pack\README.txt` byte identical (sha256 bdda1dee...) |

Command: `SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe" SC3PACK_PACKS=MAIN\stage\st_packs
PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4ci\work\runall
stage\release stage\kits ".happy-uploads\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes\jar
stage\st_packs\sc4` (paths under MAIN), logs `dev\sc4ci\work\runall1.log`, `runall2.log`.

## 7. Offering Maxis' growables to players: what it gives and costs

Built so it can be tested, off by default: `sc4conv.py <install> --growables`; the page converts them when opened as
`.../importer/?sc4growables` and then Open SC4 game. To offer them: a checkbox beside Open SC4 game that passes the same
option (one line in classifier.html), plus the guide text. Owner's call.

Gives: 305 shops, offices, factories and farms with a class (310 minus 5 too large), each with its SC4 lot's props and
textures. All 8 tried in game grew where their class develops, the 1x1 farm included.

Costs (measured):

| | civic only (today) | with the growables |
|---|---|---|
| the page converting the install (node, sc4web.js, while the suite ran) | 144.6 s, 84.5 MB read, 698 MB of files held in memory | 353.7 s, 171.1 MB read, 1,558 MB held in memory |
| Python (`sc4conv.py`) | 2 min 16 s (sc4civ) | 6 min 0 s, 394 MB written (5,741 files) |
| in the game | | about 170 KB per building in `B1D10001_bldimport.DAT` (9 buildings: 1,531,748 bytes), about 52 MB for all 305 |

What they do not do well: industry gets 3 to 10 times SC4's jobs (section 2.3), 6 of 7 farms need 2x2 or more and do not
grow in our cities (section 4), half the shops and offices are within x2 of their SC4 jobs. The memory the page holds
(1.5 GB with them) is the main risk on a small PC.

## 8. Community packs

The owner's share (`/srv/compartido`, checked 2026-11-20 05:30) holds the same four files as on 11-19: DiegoDL Growable
Pack 2019, Global Office Center, I-M manufacturers lots, the BSC Common Dependencies Pack. No new commercial or industrial
download. What the class rule gives the three C and I packs (all in the suite already; their classes and lots did not
move with this stream's changes):

- Global Office Center: office, 6,500 jobs, 4x4 -> 6700 (grew in Berlin, sc4pass2). Its "Jobs" building (3,150 jobs) has
  no model and is named, not converted.
- DiegoDL (no models in the download): 20 offices and shops, 13 -> 6700 and 1 -> 6100 on 3x3 / 4x4, 6 need 5x5 or 6x6
  (no class); 3 residential towers, 2 -> 4700, 1 needs 5x5.
- I-M: one manufacturing building, 1,542 jobs, blank model (not converted).

## 9. Files

Worktree `dev\sc4ci\wt` (branch `child/sc4ci`, nothing committed):

| file | change |
|---|---|
| `re/tools/sc4conv/sc4conv.py` | `--growables` (`install_growables`, `GROW_*`), install note line, growables off; `class_for`: a class without a base of the lot -> no class, dirty 4x4 -> 9100 (`DIRTY`, `CLASS_FALLBACK`) |
| `re/tools/sc4conv/views.py` | `_uv_area`, `UV_FLAT` (flat atlas pieces left out), `ATLAS_FIT` 2.5 |
| `re/tools/bldimport/sc4web.js` | the same: `opt.growables`, `opt.only`, `classFor`, `uvArea`, `ATLAS_FIT` |
| `re/tools/bldimport/classifier.html` | `?sc4growables` passes `growables` to the converter for an install |
| `re/tools/bldimport/webtest/sc4_install_setup.py`, `sc4_install.mjs` | the growables subset and its 3 checks |
| `re/tools/bldimport/webtest/run_all.sh` | the sc4install page step expects 113 cards |
| `docs/buildings/importer/index.html`, `sc4web.js` | `sync_css.py --publish` |
| `docs/buildings/index.html` | `make_docs.py` from the template |
| `re/analysis/SC4_FORMATS.md` | section 13 |

MAIN (local, gitignored): `verify/sc4ci/` (this file, `owner_shots/`, `runs/`, `work/ci_lab.py`, `city_classes.py`,
`fam_members.py`, `make_shots.py`, logs), `verify/bldpack/work/guide_template.html` (backup `.bak_sc4ci`),
`re/sessions/STATUS_sc4ci.md`. Scratch: `dev\sc4ci\work`.
