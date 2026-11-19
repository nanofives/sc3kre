# airsea results (round 2026-11-19g): imported buildings that grow in airport and seaport zones

**Verdict: works in game, data only, no mod code.** Three OBJ test models packed by `bldimport.py` as kinds
`airport` / `seaport` grew on their own in Sacramento by the first autosave (2.5 game-run minutes at speed 4): 10 lots
of the airport fuel depot (38000), 15 of the seaport container stack (38001), 14 of the seaport warehouse 2x2
(38002). They draw at zoom 3 and 4 and in all four view rotations. The page (`classifier.html` / `bldweb.js`) writes
the same bytes as the Python tool. Static evidence: `re/analysis/PORT_PICK.md` (worktree `dev\airsea\wt`).

## 1. How the two zones pick a building (static, PORT_PICK.md)

| zone | rule (family) | what an import becomes | weight |
|---|---|---|---|
| Airport | airpark `0x2207d9ee` (family 3), AddFamily SIMRCI `0x10003022`, Apply `0x100032d1` | a member of the filler list: size 1 and flag 0x100 or no piece type. 1x1 only, stats of Parked Airplane 231 | ignored by the rule: written as N identical Key lines (N <= 20) |
| Seaport | dockyard `0xe2d3fd92` (family 27), AddFamily `0x1002bfec`, Apply `0x1002c12a` (LandUse `0x302a` from `0x1002cc5b`) | an ordinary member, drawn on pier-served cells, 35% from the flag-clear list | the Key weight, as in RCI |

Not targets: the runway family 2 (its filler list is read at entry 0 only, `0x1002b2f0`: an import would replace
Tarmac on every runway) and the pier family 26 (waterfront pieces).

## 2. What was run

| step | command | result |
|---|---|---|
| test models | `make_testmodels.py --ports dev\airsea\work\ports` | fuel depot 1x1 (airport, 5 copies), container stack 1x1 + warehouse 2x2 (seaport, weight 10), two entries that must be refused |
| plan | `bldimport.py list ... --game dev\airsea\tree` | 3 ok; refused: "airport lot 2x2: the airport (airpark filler) grows 1x1", "weight 25: ... at most 20" |
| pack + install | `bldimport.py build ... --game dev\airsea\tree` | 11 overlay files; family 3 got 5 lines of 38000, family 27 one line each of 38001 / 38002 |
| read back | `bldimport.py check ...` | 3 of 3 ok, 20/20 frames each |
| test city | `port_clear.py "Sacramento, CA.sc3" "Sacramento AirSea.sc3" --game dev\airsea\tree` | 134 of 16,466 occupants dropped: every airpark member except the tower (36 lots) and every dockyard member (98) on port cells; runways, tower and piers kept |
| in game | `bld_lab.py --tag run1 --city "Sacramento AirSea"` (test slot, 3 GB cap) | see 3 |
| restore | `bldimport.py restore --game dev\airsea\tree` | 11 files back; overlay BUILDFAM / OccupantAttribs_Korea / CSAttrib_Korea / names sha256 = `stage\release`'s, B1D10001 DAT removed |
| load without | `bld_lab.py --tag run2_removed --city "Sacramento AirSea grown"` (run1's save, nothing installed) | see 4 |

Windowed 1600x1000, mods of `dev\airsea\inst`, posted keys only, camera through the city view on the game thread,
pictures by SC3RESIZE_FRAMEDUMP. Game PIDs 20036 (run1) and 17284 (run2), started and stopped by the lab.

## 3. In game: what regrew (counts from the saves, occupant_layer.py, port-zone cells only)

| id | what | type | before (test city) | first autosave |
|---|---|---|---:|---:|
| **38000** | **Test fuel depot (import, 5 copies)** | 12310 | 0 | **10** |
| 227 / 246 | terminal / hangar | 12310 | 0 / 0 | 6 / 1 |
| 228, 229, 231, 11018 | stock fillers | 12310 | 0 | 2, 4, 3, 10 |
| 221 / 222 / 11010 / 11012 / 11014 / 225 | runway pieces, tarmac, tower (kept) | 12310 | 10 / 2 / 8 / 2 / 8 / 1 | same |
| **38001** | **Test container stack (import, weight 10)** | 12330 | 0 | **15** |
| **38002** | **Test harbour warehouse 2x2 (import, weight 10)** | 12330 | 0 | **14** |
| 224 / 9042 | crane / parking lot (flag-clear list) | 12330 | 0 | 3 / 2 |
| 242, 9043, 9044 | flag-set list | 12330 | 0 | 6, 19, 24 |

- Airport: the fuel depot took 10 of the 29 filler lots, with 5 of the 10 filler-list entries (expected share 50%,
  measured 34% on one save). Terminals and the hangar regrew first, as Apply orders it.
- Seaport: flag-clear list 32 lots (38001 + 38002 + 224 + 9042), flag-set list 49. The imports are 20 of the 23
  flag-clear entries.
- The saved building type (`t18`) of every import is the base's (12310 / 12330), so the airport / seaport valve
  effects of `PORTS_AIRPORTS.md` 1.3 count them like stock port buildings.
- `resize.log`: one fault line in each run, `0xC0000096 at SC3U.exe+0x84122` at 0.66 s / 0.05 s, before the city loads,
  the same line as the bldrender runs. No other fault.

## 4. Load without the package (run2)

The grown save, loaded with the overlay restored: no crash, 0 imported lots left, occupant count 16,410 -> 16,426
after one autosave. Each import lot was replaced by a stock building of the same type and footprint:

| import | replaced by |
|---|---|
| 10 x 38000 airport 1x1 | 10 x 221 Landing Strip Straight (a runway piece) |
| 15 x 38001 seaport 1x1 | 15 x 223 Pier (a pier piece, on land) |
| 14 x 38002 seaport 2x2 | 14 x 240 Seaport Loading Bay |

Same substitution rule as batconvert and stylemix (BUILDING_PICK.md section 7: the loader keeps the type; which
member it picks is [UNCERTAIN], the branch is not read). Here it picks a piece that the developer would never put
there. Not a crash and no other lot changed, but a player who removes the package sees runway strips and pier pieces
on those lots until they are bulldozed. Not pictured (the lab takes pictures only of the imported ids).

## 5. Page and tests

- `bldweb.js`: PORTS / portTable / ruleFamilies / plan / buildFiles transcribed. Golden case `ports` (the three
  models + the two refused entries + `North Shore Cannery.bld` as a 2x2 seaport): golden.mjs 13 of 13 files
  byte-identical, frames 80 of 80; pagetest.mjs ports (the page in headless Chrome, worker renderer) 15 of 15.
- `classifier.html`: a model whose name says airport / hangar / terminal gets kind airport and lot 1x1, seaport words
  give 1x1 or 2x2, with the reason; warnings for an airport lot other than 1x1, a seaport lot above 2x2, an airport
  weight above 20, and ploppables (not imported yet).
- `run_all.sh`: case ports in golden_setup / golden.mjs, pagetest.mjs ports added (steps 25 -> 26 with the six
  arguments). Full run: see 6.

## 6. run_all.sh (all six arguments, SC3PACK_PACKS = stage\st_packs)

`test-slot bash re/tools/bldimport/webtest/run_all.sh dev\airsea\work\runall stage\release stage\kits
"<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes stage\st_packs\sc4`
with `SC3PACK_PACKS=stage\st_packs`: **26 of 26 steps passed** (log `dev\airsea\work\runall.log`). Among them:
golden_setup 5 cases, golden.mjs 65 of 65 (ports 13 of 13, frames 80), install / .zip / restore goldens, pagetest
kenney / bld / styles / **ports** / sc4 / sc4empty x2, check_roundtrip, sync_css, fonts, sc3pack and the SC4 steps.

## Pictures (`owner_shots/`, phone size)

| file | what |
|---|---|
| `01_airport_fuel_depots_zoom4.jpg` | Sacramento airport: white fuel-depot tanks among the regrown terminals, next to the tower |
| `02_seaport_warehouses_containers_zoom4.jpg` | Sacramento port: teal warehouses with yellow gantries and container stacks beside a stock crane |
| `03_airport_zoom3.jpg`, `04_seaport_zoom3.jpg` | the same at zoom 3 |
| `05_airport_four_view_rotations_zoom4.jpg` | the airport in view rotations 0-3 |
| `06_models_next_to_stock_bases.jpg` | offline: each model's 4 slots next to its stock base (231, 224, 240) |

Raw dumps: `runs/run1/fd/` (PNG, no BMP left), counts `runs/<run>/counts.json`, saves `runs/<run>/saves/`.

## Not tested

Query dialog / "Copiar ID" on an imported port lot. A city that zones new airport / seaport land from scratch (the
test city reuses Sacramento's zones). Seaport 3x3 / 4x4 (the dockyard would draw them, `0x1002c12a` tests only the
size against its rect, but no stock member is that big; the tool offers 1x1 and 2x2).
