# Round 2026-11-20c: converted SimCity 4 buildings standing above the lawn, then the side-by-side pictures again

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 67f2d4f+.
Found by sc4cmp (verify/sc4cmp/RESULTS.md): 24 of 50 converted SC4 models reach 0.4 to 5.5 m below SimCity 4's ground
(every Small Shops and Retail Stores variant, Ferrrara Inc., Smith Tower by 0.4 m). bldrender.place puts a model's
lowest point on the lawn, so these buildings stand that far above it, lot ground included, with a second lawn edge.
The frame is what the game draws, so it shows in game too (sc4cmp forum pictures 06, 07, 09 and the in-city strips).
Also seen in verify/sc4cmp/forum/04_alamo.jpg: on the SC3 side the Alamo's flag hangs in the air without its pole.

## Stream sc4ground (opus / medium)

1. Measure: over the SC4 install (civic + growables), JMyers and Global Office Center, how many converted models reach
   below SC4 ground and by how much, and why (foundations, basements, a model origin offset).
2. Fix so SC4 ground lands on the SC3 lawn: clip below ground in the converter, or a ground height the renderer takes
   for SC4 entries only, or another route. Decide with evidence. Every non-SC4 golden (OBJ models, .bld, sample pack)
   must stay byte identical. Python = page byte for byte for the SC4 routes.
3. The Alamo flag: find why the pole is missing on the SC3 side (lot crop, prop centre outside the lot, a prop part
   left out) and fix it if it is a converter fault.
4. Check: the affected buildings' frames sit on the lawn (pictures), one of them grown or placed in game
   (sc3dev run, windowed, posted input or Frida only, kill only PIDs you started).
5. Rebuild the forum pictures with re/tools/sc4conv/compare_sheet.py (verify/sc4cmp/RESULTS.md section 6) into
   verify/sc4cmp/forum/ and look at every one. If the extras (forum/extra: City Hall grey hook, Lee Avionics washed out,
   Small Fire Station mostly lawn, Mayor's House) have a converter cause you fixed on the way, say so.
6. run_all.sh with all six args + SC3PACK_PACKS + SC4INSTALL (PROYECTOS_TEST_HUB=off) passes every step,
   sync_css.py --check / --publish if the page changed, guide template only if a guide statement changed.
   Results verify/sc4ground/RESULTS.md, STATUS re/sessions/STATUS_sc4ground.md.

## Rules

SC4 install read in place, EA and community content and pictures never in the repo or docs. Windowed game, never the
real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add / commit.
