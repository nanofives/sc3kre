# Round 2026-11-19l: SimCity 4 civic / parks / rewards, then SC4's own props, then lot textures

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main.
Owner (2026-11-19): "Civic, parks, rewards, and then SC4's own props, and then Lot textures" (in that order, one stream
at a time). SimCity 4 Deluxe was installed on this PC for it (Steam):
`C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe\` = SimCity_1.dat .. SimCity_5.dat, EP1.dat (Rush
Hour), SimCityLocale.DAT. EA content: read in place, never copied into the repo, docs/ or a release. Pictures local.
Community downloads on hand (stage/st_packs/sc4, server share Compartido): JMyers Homes V3.1, Global Office Center,
DiegoDL lots, I-M lots, BSC Common Dependencies Pack V9e. No community civic / park / reward pack yet.

State of the SC4 route: verify/sc4conv, sc4web, sc4diag, sc4pass2, sc4props, plop2 RESULTS.md, re/analysis/SC4_FORMATS.md,
the guide's "SimCity 4 buildings" section (docs/buildings/index.html#sc4). SC3 side of civic looks and rewards:
re/analysis/CIVIC_REWARD.md, verify/civmod, civtest, civdlg RESULTS.md (17 civic bases, reward population / year,
kinds `civic` and `reward` in bldimport.py and the page).

## Stream sc4civ (opus / high): SC4 civic buildings, parks and rewards

1. Find how SC4 marks a civic building, a park and a reward in its data (occupant groups, building / lot exemplar
   properties, the reward conditions), with evidence from SimCity_1..5.dat / EP1.dat (property ids, counts, examples).
   Write it to SC4_FORMATS.md (layouts and counts only, no EA text dumps).
2. Map them to SC3U: civic -> kind `civic` with the matching base of the 17 (police, jail, fire, hospital, school,
   college, library, museum, the parks, zoo, baseball field, playground, pond, fountain, bus stop, train station),
   rewards -> kind `reward` (population / year from the SC4 conditions where a fair mapping exists, else a stated
   default), the rest (e.g. SC4 services with no SC3 button) -> landmark off, or left out, with a reason on the card.
   Lot = the SC3 base's lot for civic (as bldimport requires), smallest square for rewards and landmarks.
3. A way for the player to use SC4's own buildings: the page reads their own SC4 install (folder picker, or the
   .dat files) as a source like a download, streaming the large files as deps.py does. Python route the same
   (`sc4conv.py <SC4 install>`). Byte identity Python = page (new golden / sc4 test steps), run_all.sh with all six
   args + SC3PACK_PACKS passes, sync_css.py --check / --publish.
4. In game (windowed, sc3dev run, posted input or Frida game calls): one SC4 police or fire station as a civic look
   (list window, placed, coverage), one SC4 park, one SC4 reward unlocked and placed. Save + reload.
5. Guide text update in MAIN verify/bldpack/work/guide_template.html (+ make_docs.py, keep the published sample-pack
   link): what converts and how, numbers from RESULTS only, voice rules. Results verify/sc4civ/RESULTS.md.

## Stream sc4baseprops (after sc4civ is merged): SC4's own props from the player's install

The JMyers test left 3,454 prop rows (54 ids) unplaced, the two most used look like SC4's own. Read props from the SC4
install as one more dependency source (deps.py / sc4web.js), measure again how many rows place, Maxis lots too.

## Stream sc4lottex (after sc4baseprops): lot textures

Driveways, paths, paving of SC4 lots drawn on the lot ground under the building in the SC3 pictures, from the
download, the dependency packs and the SC4 install.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. SC4 / EA / community content and pictures of it never in the repo or docs.
