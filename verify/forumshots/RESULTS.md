# forumshots results (round 2026-11-23b): forum pictures re-taken, 17 more comparisons, English UI, style pick before / after

Worktree `dev\forumshots\wt` (fast-forwarded to main 42df68e after civlot and bakedsharp, no code change, nothing
committed). SimCity 4 Deluxe (Steam) read in place. Maxis buildings only. Every picture holds EA art: local only
(`verify\` is gitignored), never in git or docs. All game runs were windowed in `dev\forumshots\tree`, driven by posted
messages and Frida game calls. The real mouse and keyboard were never used. Only PIDs this session started were stopped.

## Verdict

- **29 comparison sheets** in `verify/sc4cmp/forum/` (02 to 29) plus `extra/lee_avionics.jpg`. 00 and 01 (Small Police
  Station) are civlot's and were not touched. Converted with main's converter: `baked_sharp` for every building,
  civic looks and parks on their SimCity 4 lot (civlot), landmarks and rewards on their SimCity 4 lot, props from the
  install, lot textures, ground fix, tree peel.
- **27 of 29 sheets have an in-city strip** from this round's game frames. The 2 without one: Eyler Refining and
  Maxis Theatre (both grew, 6 and 3 lots, but churn had replaced the lot by the time the camera got there).
- **17 new comparisons** (brief: at least 8): Mayor's House (2x3), Hagia Sofia (5x5), City Hall (3x4), Main Library
  (3x4), Faneuil Hall, Large Fire Station (2x3), Small Fire Station (1x2), Elementary School (2x3), Medical Clinic
  (1x2), City Museum (2x3), Local Branch Library, Tennis Court (1x2), Maxis Theatre, Walton Plaza, Chez Eyler, Dao
  Chemicals, Tsvirkunov Electronics.
- **"Choose a look" and City Properties fully in English** (window title, list header, building names, ticker).
- **Style pick before / after** with the same camera: blue-roof North American houses before, red-roof European
  houses on the same blocks after, the landmarks and part of the houses unchanged.

## Pictures

Sheets: `verify/sc4cmp/forum/` (copies in `verify/forumshots/sheets/`). Left SimCity 4 (drawn through SC4's own camera
from SC4's own views), right SimCity 3000 (the converted building's zoom-4 frame), strip below from a game frame.

| file | what it shows | city of the strip | zoom |
|---|---|---|---|
| 02_courthouse.jpg | Courthouse reward, 3x3, fountain and flower beds, in a row of placed SC4 landmarks by the river | Madison | 4 |
| 03_gazebo.jpg | Gazebo park, 1x1, gazebo, lamp and bushes, next to the Local Branch Library | Madison | 4 |
| 04_alamo.jpg | The Alamo landmark on its 2x3 SC4 lot with the flag pole kept (baked_sharp) | Madison | 4 |
| 05_independence_hall.jpg | Independence Hall, 2x2, between Faneuil Hall and the Main Library | Madison | 4 |
| 06_small_shops.jpg | Small Shops, 1x1, grown on a commercial street with SC3 shops | Berlin | 4 |
| 07_retail_stores.jpg | Retail Stores, 2x2, grown between SC3 towers | Berlin | 4 |
| 08_lam_banking.jpg | Lam Banking, 2x2, grown on a plaza block | Berlin | 4 |
| 09_ferrrara_inc.jpg | Ferrrara Inc., 3x3 tower, two grown side by side among SC3 towers (SC4 view W, slot 2) | Berlin | 4 |
| 10_eyler_refining.jpg | Eyler Refining, 2x2 dirty industry. No strip | | |
| 11_vilett_textiles.jpg | Vilett Textiles, 3x3, grown in the industrial district | Madison | 4 |
| 12_pumpkin_acres.jpg | Pumpkin Acres farm, 1x1, among SC3 farms (a farm house partly in front) | Madison | 4 |
| 13_mayors_house.jpg | Mayor's House reward on its 2x3 SC4 lot with the hedges and gardens | Madison | 4 |
| 14_hagia_sofia.jpg | Hagia Sofia landmark on 5x5, by a farm and the placed City Hall (SC4 view N, slot 1) | Madison | 4 |
| 15_city_hall.jpg | City Hall reward on 3x4 | Madison | 4 |
| 16_main_library.jpg | Main Library reward on 3x4, by the river | Madison | 4 |
| 17_faneuil_hall.jpg | Faneuil Hall landmark, 2x2 | Madison | 4 |
| 18_large_fire_station.jpg | Large Fire Station on 2x3 (SC4 lot 3x2, installed turned a quarter, SC4 view E) | Madison | 4 |
| 19_small_fire_station.jpg | Small Fire Station on its 1x2 SC4 lot (was extra/ on the 3x3 stock lot) | Madison | 4 |
| 20_elementary_school.jpg | Elementary School on 2x3 with its parking lot and yard | Madison | 4 |
| 21_medical_clinic.jpg | Medical Clinic on 1x2 with its parking lot | Madison | 4 |
| 22_city_museum.jpg | City Museum on 2x3, by a road and the ball park | Madison | 4 |
| 23_local_branch_library.jpg | Local Branch Library, 2x2, parking and lawn | Madison | 4 |
| 24_tennis_court.jpg | Tennis Court park on 1x2 | Madison | 4 |
| 25_maxis_theatre.jpg | Maxis Theatre, 3x3 commercial. No strip | | |
| 26_walton_plaza.jpg | Walton Plaza, 3x3 office tower, grown downtown, partly behind an SC3 glass tower | Berlin | 4 |
| 27_chez_eyler.jpg | Chez Eyler, 1x1 shop, grown in a row of SC3 shops | Berlin | 4 |
| 28_dao_chemicals.jpg | Dao Chemicals, 3x3 dirty industry, grown by an SC3 plant | Madison | 4 |
| 29_tsvirkunov_electronics.jpg | Tsvirkunov Electronics, 3x3 high-tech, grown by the river | Madison | 4 |
| extra/lee_avionics.jpg | Lee Avionics, 2x2 high-tech. SC3 side still reads washed out, so not in the set | Madison | 4 |

English UI (`verify/forumshots/ui/`, tree text `ENGLISH` swapped for `English-UK`, `SC3MODS_LANG=en`, no FPS line):

| file | what it shows | city | zoom |
|---|---|---|---|
| choose_a_look_police_sacramento_en.png | "Choose a look", "Buildings Available:", North America / Europe / Asia: Police Station, "Look 1 of 3", English ticker. The first row is cut at "Police Stat" (the list box is narrower than the row) | Sacramento, 800x600 | 3 |
| choose_a_look_police_europe_selected_en.png | the same window, Europe row picked, European station picture, "Look 2 of 3" | Sacramento, 800x600 | 3 |
| city_properties_mix_box_sacramento_en.png | "City Options", Buildings icons with "Mix all three styles" ticked, English ticker | Sacramento, 800x600 | 3 |
| city_properties_mix_box_sacramento_en_1430.png | the same at 1430x900 (HUD scale Auto, larger window) | Sacramento | 3 |
| city_properties_european_mix_off_en_1430.png | European icon picked, Mix unticked: the pick made for the before / after run | Sacramento | 3 |

Style pick (`verify/forumshots/`, frames and spare pairs in `runs/sp/`):

| file | what it shows | city | zoom |
|---|---|---|---|
| style_pick_before_after.jpg | the same camera on cell (95, 65): before the pick (stock save) and after (88 s + 6 min at speed 4 with European picked, Mix off), plus a full-size detail. Before: blue-roof houses. After: red-roof European houses on the same blocks. The church, the domed building, the warehouse and part of the blue houses are unchanged | Sacramento, 1430x900 | 3 |
| runs/sp/pair_*.jpg | 5 more spots (165,165 / 45,95 / 125,225 / 105,175 / 185,235), same layout, same result | Sacramento | 3 |

**Counts from the run** (`stylepick_count.py "Sacramento, CA.sc3" save_after_6min.sc3`): 16,417 buildings, 6,880
kept (same cell, same key), 9,537 new or rebuilt. New: European 7,131, base 2,400 (buildings no set re-skins, they look
North American as in a stock European city), Asian 4, North American copies 0, re-skinnable base 2. Kept: 4,712
re-skinnable base buildings still stand with their base id in a set-0 city, so they kept their North American look
(the control). The saved stylepick record: style European, mix 0. The 4 Asian and 2 re-skinnable base buildings: the
first game ran about 1 min with Mix still on before the pick was made.

## How

| step | command / tool |
|---|---|
| convert | `sc4conv.py <SC4> --growables --all --only <work/only.txt> --out work/conv_main` (29 buildings, main's defaults) |
| render + install | `bldimport.py build work/conv_main --game dev\forumshots\tree` (ids 38000-38028) |
| civic, park, reward, landmark in Madison | `work/lab.py place` (building layer vt+0x38, Frida on the game thread). Hagia Sofia and City Hall were refused by that call (placed 0, cost 0, at 6 cells) and were placed with the stock tool instead: `lab.py arm` + posted mouse move and click |
| growables | `work/grow_lab.py` (sc4ci's ci_lab): Berlin for the 7 commercial, Madison for the 5 industrial and the farm, churn anarchy 5000, autosave 150 s. All 13 grew (Berlin by 5.0 min, Madison by 15.0 min). Pictures re-taken with `--from-save` (churn off), because the first pictures came after churn had rebuilt the lots |
| frames | zoom 4, four rotations (`lab.py cam` + `dump`, SC3RESIZE_FRAMEDUMP), 1430x900 for the placed ones, 1600x1000 for the grown ones |
| strips | `work/match_ingame.py` (sc4cmp's FFT matcher) -> `work/ingame.json`. Kept by eye: `work/ingame_final.json` (27). RMS on the kept frames: placed ones 2.6 to 3.7 (Courthouse 21.2 and City Museum 19.6 on slot 3: the right building with a neighbour overlapping), grown ones 5.2 to 29.6, plus Walton Plaza 46.2, Vilett Textiles 33.1, Pumpkin Acres 43.6 (looked at: the right building with neighbours in front) |
| sheets | `work/sheets.py <out> --ingame work/ingame_final.json --game-root <MAIN>`: compare_sheet.py unchanged, with this round's picture list and a crop that stays out of the HUD and keeps its aspect |
| style pick | `work/sp_lab.py` (launch with churn, shots with a zoom change first), `work/make_sp.py` |

## Found on the way

- **Crash, not fixed (not this stream):** Sacramento, churn anarchy 5000, speed 4, 105 s after the City Properties
  pick: `VEH FAULT 0xC0000005 at STRTSIM.DLL+0x94DB`, read of address 0, main thread, stack through STRTSIM+0x2D468,
  +0x12F75, SC3U.exe+0x2638B, SIMSPR+0x1CB09, sc3overscroll+0x1B6F / +0x2146 (`runs/sp/resize.log` was overwritten by
  the next launch, the lines are quoted in STATUS). One occurrence. The run went on from the autosave made 17 s before.
- `lab.py cam` (SetZoomAndRotation) does not move the camera when zoom and rotation are unchanged: the first six
  before / after pairs were all the load view. `sp_lab.py shots` now goes through another zoom first (memory note on
  showcase gallery traps already says "recentre needs a zoom change").
- Choose a look: the first row text is cut ("North America: Police Stat") in English at 800x600.
- compare_sheet's subtitle has no label for class 8900: Tsvirkunov Electronics reads "Growable building".
- compare_sheet's strip crop could include the HUD on a 1430x900 frame when the building is large (Hagia Sofia at
  x0.77): fixed in this round's wrapper only (`work/sheets.py`), compare_sheet.py unchanged.
- No BSC Common Dependencies Pack used: not in Downloads, `\\mariano-server\Compartido` refused access. Maxis lots
  need none (0 prop rows "in no pack given"), and community props stay out of the pictures this way.
- Residential growables: the converter does not convert SimCity 4's homes from an install, so there is no R
  comparison (C and I only).

## Files

Local only, nothing for git: `verify/forumshots/**` (RESULTS.md, sheets, ui, style pick, runs, work scripts, logs),
`verify/sc4cmp/forum/02..29*.jpg`, `extra/lee_avionics.jpg`, `sheet_forumshots.json`. Removed from `forum/extra/`:
city_hall, small_fire_station, mayors_house (now 15, 19, 13). Test saves in `dev\forumshots\tree\Cities\`
(`forumshots madison.sc3`, `sp_cont.sc3`, `sp_after6.sc3`).
