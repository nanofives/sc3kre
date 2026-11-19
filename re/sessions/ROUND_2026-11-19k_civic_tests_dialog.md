# Round 2026-11-19k: civic / reward tests, then the civic list dialog

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main 01d6e2f+.
Shipped in sc3mods-2026-11-19b: civic looks (cycle on the stock button), new rewards, Mover for imported buildings.
Records: verify/civmod/RESULTS.md, re/analysis/CIVIC_REWARD.md, verify/mods_release_1119b/RESULTS.md.
Owner (2026-11-19): "Test other civic buttons, and then Civic list dialog".

## Stream civtest (opus / medium): close what 2026-11-19b left untested

Test data with re/tools/bldimport/make_testmodels.py --civmod + bldimport.py build (extend it for the cases below).
Quick in-game checks with pictures, not a soak (owner: light testing).
1. Civic looks on other bases: fire station, school, hospital, and one larger base (college or stadium or a utility
   such as a water pump if it is one of the 17). Per base: the cycle on the button (keys in the log), placed, the
   service works for the look (fire / education / health coverage map or the query window), save + reload.
   For the remaining bases only check the cycle keys (no placing).
2. Rewards on 1x1, 3x3 and 4x4 lots (2x2 was tested): unlock, Rewards list, place, save + reload, Mover.
3. A 3x3 growable from the importer grows in a city with dense commercial demand (sc3compat-a's Maxis Plaza case
   reached 0 lots, as did the stock 3x3 it copies, in Sacramento). Use a city where the stock 3x3 grows.
4. Fix any bug found (sc3resize_civic.c, bldimport.py, the page if a kind is wrong there: byte identity and
   run_all.sh must still pass). Results verify/civtest/RESULTS.md.

## Stream civdlg (opus / high, after civtest is merged): civic list dialog

Pressing a civic button that has imported looks opens a small list window (game UI look, scales with DLGSCALE /
interface scale): the original first, then the looks, each with its name, price and picture if the game can draw
it. Picking one arms the stock tool with that key, the window closes. Esc or close = no tool. A button with no
looks stays exactly stock. Decide with evidence whether the stock catalog window (CIVIC_REWARD.md: the landmark /
reward list) can be reused or a new SIMUI window is simpler. Keep the press-to-cycle as a mods page option only if it
costs nothing. Rules for any UI mod: project-simui-window-model memory, re/analysis on SIMUI windows.

## Rules

Windowed game, posted input or Frida game calls only, never the real mouse or keyboard, test slot, kill only PIDs you
started, delete BMP dumps, no git add / commit. EA content only in the test tree.
