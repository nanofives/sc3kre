# Round 2026-11-19i: civic / reward research + landmark follow-ups (loop)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main 9009a18+.
Previous: verify/plop/RESULTS.md, re/analysis/PLOPPABLES.md (landmarks as data via Apps\PlugIn .pin + .dat; civic
buildings have their own menu entry and command in MenuItem.INI; rewards come from a fixed list in
Advisor-CityPlanner.ini with unlock rules not read).
Owner (2026-11-19): "Yes, research it" for civic buildings and rewards: research, then propose the smallest mod change
BEFORE building it.

## Stream civrew (opus / high): research only, then a proposal

1. Civic: how a civic menu entry maps to a building (MenuItem.INI, the command ids, the tool / placement path, the
   building's exemplar), what a NEW civic building (e.g. a second police station look, a new school building) needs:
   a new menu entry and command, or can a new building join an existing entry (variants / a picker)? RVAs.
2. Rewards: how Advisor-CityPlanner.ini rewards unlock and get placed (the rules, the reward list, the petition /
   advisor flow), what a new reward needs. RVAs.
3. Proposal: the smallest mod change for each (which DLL, which hook, what data the importer would write), with the
   risks (saves, other mods, menus at other UI scales). No code beyond throwaway probes. Write re/analysis/CIVIC_REWARD.md
   and verify/civrew/RESULTS.md, then stop for the orchestrator.

## Stream plop2 (opus / medium): landmark follow-ups

1. A description field for landmarks in the importer page (models.json `description`, already read by bldimport.py),
   byte identity kept.
2. SC4 landmark / ploppable versions (Global Office Center's landmark lot, verify/sc4pass2) convert to kind landmark in
   sc4conv.py and sc4web.js, byte identity, one placed in game (picture, local only).
3. Is the lot a removed landmark leaves (orange-brown ground) buildable again: test in game, and if not, what clears it.
4. Guide (verify/bldpack/work/guide_template.html + make_docs.py): a "Landmarks" section (kind landmark, lot sizes,
   the plugin files in Apps\PlugIn, removing them and what it leaves), and "Maxis landmark packs" (players' own copies of
   the 2000 packs install through Open SC3 pack, the art is converted). Voice rules, numbers from RESULTS files only.
5. run_all.sh with all six args + SC3PACK_PACKS passes every step; sync_css.py --publish.
Results verify/plop2/RESULTS.md.

## Rules

Windowed game, posted input or Frida game calls only, test slot, kill only PIDs you started, delete BMP dumps, no git
add / commit. civrew writes no repo code (analysis docs only). Maxis packs and SC4 content never in the repo.
