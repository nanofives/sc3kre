# Round 2026-11-19g: airports and seaports as import targets + SC4 lot props (loop)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main 0387f6e+.
Owner (2026-11-19): "let's continue with your suggestions in loop": airports / seaports, then ploppables, plus SC4
lot props. Steam / retail Building Architect support waits for the owner's Baapp.exe files (only GOG exists here).

## Stream airsea (opus / high): imported buildings that grow in airport and seaport zones

Background: re/analysis/BUILDING_PICK.md (16 rule classes; Apply selects the family by LandUse except the airport and
seaport rules 0x100032d1, 0x1002b04c, 0x1002d27f), memory note "Ports and demand cap" (airports / seaports raise the
C / I demand ceiling via valves 5001 / 8001), re/tools/netmod/netpack_growables.py, re/tools/bldimport/ (bldimport.py,
bldweb.js, classifier.html, models.json kinds: growable today; airport / seaport reserved).
1. Static: how the airport and seaport zone developers pick a building (rules, families, lot classes, sizes, the
   runway / dock pieces vs the buildings), with RVAs. What a new building needs to be picked there.
2. Proof of concept in game: one new building (one of our test models or a sample pack building) grows in an airport
   zone and one in a seaport zone, in a city where those zones develop (pictures, counts from the saves). Off switch
   / clean removal like the other imports.
3. If it works: kinds `airport` / `seaport` in bldimport.py and the page (models.json, classifier suggestions, install),
   byte identity Python vs page kept, run_all.sh passes every step (add steps). If it cannot work without code in a
   mod DLL, say exactly what code and stop for the orchestrator's call.
Results verify/airsea/RESULTS.md.

## Stream sc4props (opus / medium): SC4 lot props baked into converted buildings

Background: verify/sc4pass2/RESULTS.md section 3 (props use the same S3D box-and-picture format; 61 of 97 I-M prop ids
and 0 of 9 tower prop ids are in the BSC pack), re/tools/sc4conv/, sc4web.js. Packs: stage/st_packs/sc4/ (BSC Common
Dependencies Pack V9e zip with the 1.64 GB jar inside), stage/st_packs/sc4_jmyers_homes/ (JMyers lots use BSC props).
1. Read SC4Lot lot objects (prop id, position, rotation per lot) and the BSC prop exemplars / models (streaming, the jar
   is huge: index once, cache the index).
2. Bake the props that are found into the converted building's art: reproject each prop like a building at its lot
   position and composite it around the house in every view and zoom (SC3 growables cannot carry separate props).
   Props not found are listed. An option to switch props off per building (models.json x_sc4.props).
3. JMyers houses with their fences / trees / cars, grown in Sacramento, pictures next to the no-props version.
4. Python first, then the page (sc4web.js) reading the deps zip by folder pick or zip, byte identity kept, run_all.sh
   passes every step. If the page part does not fit this round, finish Python + tests and report.
Results verify/sc4props/RESULTS.md. Nothing from SC4 packs into the repo or docs/.

## Rules (both)

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, STATUS at every
milestone, no git add / commit. Coordinate file ownership: airsea owns bldimport.py / bldweb.js / classifier.html this
round; sc4props owns re/tools/sc4conv/ and sc4web.js. Needed changes in the other's files go through the orchestrator.
