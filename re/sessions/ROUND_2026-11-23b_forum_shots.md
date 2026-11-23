# Round 2026-11-23b: forum pictures re-taken, SC4 civic buildings on their own lot

Orchestrator: "SC3: pending items after recent rounds + SC4 style status". Rules: re/sessions/CHILD_PROTOCOL.md.
Workspaces from main. Owner review 2026-11-23 of the Simtropolis draft (verify/showcase/site/make_st_post_1123.py):
1. the before/after style picture (verify/stylepick/owner_shots/sp08_moscow_before_after_pick_na.png) looks identical
   on both sides;
2. the "Choose a look" picture (verify/mods_release_1121/owner_shots/12_police_list_sacramento_en.png) shows Spanish
   (list header "Edificios disponibles", "Comisaria", the ticker): make it English;
3. the Small Police Station comparison must use the 2x3 lot it has in SimCity 4 (today 3x3, the stock button's lot);
4. more building comparisons;
5. every earlier building picture re-taken with the current prop loading and lot size work.

## Stream civlot (opus / high): SimCity 4 civic buildings and parks on their own SimCity 4 lot

Today a civic look from SC4 ("Open SC4 game", sc4civ) keeps the stock button's lot, coverage and price
(docs/buildings/index.html, "From your own SimCity 4"). Landmarks and rewards already keep their SC4 lot, non-square
up to 5x5 (lotshape, lotdraw LOTRECT, re/analysis/LOT_SHAPES.md, CIVIC_REWARD.md).
1. Evidence first: where a civic look's lot size comes from (occupant / exemplar, the civic list window, placement
   tool footprint, coverage, save record) and whether a look can have a lot other than its base building's without
   breaking coverage, price, save/load, Move, bulldoze, and the stock game opening the save. Cite addresses.
2. If it holds: SC4 civic looks and parks go on their SC4 lot (smallest SC4 lot that fits, up to 5x5, non-square
   with the "Non-square buildings" row on, as landmarks do), importer page + Python byte for byte, behind an entry
   key or page option if a fallback to the stock lot is needed. If it does not hold, stop and report why with evidence.
3. Check in game: SC4's Small Police Station placed on 2x3 from the Police list in Madison, coverage circle on the
   crime map, save + reload, the save opened in the stock game. Windowed, posted input or Frida only.
4. The Small Police Station forum sheet re-made on the 2x3 lot (re/tools/sc4conv/compare_sheet.py, the in-city strip
   from this round's game frames) into verify/sc4cmp/forum/01_small_police_station.jpg and 00_..._four_sides.jpg.
5. Suite (CHILD_PROTOCOL suite modes), guide lines that change. Results verify/civlot/RESULTS.md,
   STATUS re/sessions/STATUS_civlot.md.

## Stream forumshots (opus / medium): every forum picture re-taken, more comparisons

Start after reading civlot's brief: do not touch the Small Police Station sheets (civlot makes them). Everything
else:
1. Re-convert and re-render the SC4 comparison set with the current converter (props from the BSC Common
   Dependencies Pack if present on \\mariano-server\Compartido or the owner's downloads, and from the SC4 install;
   lot textures; ground fix; tree peel; landmarks and rewards on their SC4 lot, Non-square buildings on). Recipe:
   verify/sc4cmp/RESULTS.md section 6. Re-make every sheet in verify/sc4cmp/forum/ and forum/extra/ with in-city
   strips from new game frames (Madison / Berlin, windowed, posted input or Frida only).
2. More comparisons: at least 8 more SimCity 4 buildings, Maxis' own only (never community buildings): more civic
   (fire, school, hospital, library, museum where SC4 has them), parks, rewards (Mayor's House 2x3, Courthouse),
   landmarks (Hagia Sofia 5x5, others with non-square lots), and growables across R / C / I and sizes. Look at every
   sheet before keeping it.
3. "Choose a look" in English: the full window English (list header, building names, ticker), via the English text
   swap in a dev tree (memory reference-english-screenshots, SC3MODS_LANG=en). Police list with the three styles,
   Sacramento. Also re-take City Properties with the Mix box in the same English tree.
4. Style pick before/after that shows the difference: same city, same camera, before the pick and after enough game
   time that new lots visibly grew in the picked style (or a crop / markers on the lots that changed), plus a control
   that existing buildings kept their look. Results-only numbers (count of new lots per style) from the run.
5. Look at every picture before keeping it, list what each shows. Output in verify/forumshots/ (pictures +
   RESULTS.md with one line per picture: file, what it shows, city, zoom). STATUS re/sessions/STATUS_forumshots.md.

## Rules

SC4 install and downloads read in place, EA and community content and pictures never in git or docs (pictures stay in
gitignored verify/ folders and the .happy-share draft). Windowed game, never the real mouse or keyboard, test slot,
harness claim before any game run, kill only PIDs you started, delete BMP dumps, no git add / commit.
