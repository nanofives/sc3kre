# Round 2026-11-19h: ploppables (loop) + guide update

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspaces from main 3b87c1e+.
Owner (2026-11-19): continue the suggestions in a loop. Done so far: R / C / I growables, airport / seaport imports
(verify/airsea), SC4 conversion incl. lot props (verify/sc4props). Last item: ploppables.

## Stream plop (opus / high): new ploppable buildings (landmarks first)

Samples: stage/st_packs/maxis_addons_2000/ = the official Maxis Landmark Pack 1 and 2 (LandmarkPack1/2.dat + .pin) and
the "SimCity 3000 add-on plugin" installer (MaxisAddOn.dll): Maxis' own way to add ploppable landmarks to SC3 (2000).
Also memory notes: Relocate + build over zoned (Mover, PLOPOVER), BAT buildings as growables (bat_slots: the stock
Replace dialog, [ReplaceableBuildings]), SIMUI window model.
1. Static + live: how the game builds its landmark / reward / civic menus and places a ploppable (catalog data,
   strings, exemplar fields, the tool path), and how the 2000 plugin system (.pin + .dat, MaxisAddOn.dll) adds
   landmarks: does SC3U still load them natively (where do the files go, what reads .pin)? Cite RVAs.
2. Proof: one Maxis landmark pack installed the native way (if SC3U supports it) shows in the landmark menu and can be
   placed; then one of OUR buildings (a test model or a sample pack building) added as a new landmark the same way
   (data only if possible), placed in a city, saved and reloaded, and loaded without the package (what happens).
3. If it works as data: kind `landmark` (and civic / reward if the same path works) in bldimport.py and the page,
   byte identity, run_all.sh passing every step (all six args + SC3PACK_PACKS), and the pack reader (sc3pack.js)
   offering to install .dat + .pin landmark plugins it already identifies. If it needs mod code (a menu entry, a
   tool), describe exactly what and stop for the orchestrator's call.
Results verify/plop/RESULTS.md. Never ship Maxis' landmark packs (EA content): players install their own copies.

## Stream guide2 (opus / medium): guide update for airports / seaports and SC4 props

docs/buildings via the generator (verify/bldpack/work/guide_template.html + make_docs.py): airport and seaport kinds
(what they are, 1x1 airport fillers up to weight 20, 1x1 / 2x2 seaport, what removing the package leaves: runway
strips / pier pieces until bulldozed, from verify/airsea/RESULTS.md), SC4 lot props (the BSC dependencies pack, what
converts, what is missing: SC4's own built-in props, the per-building switch, from verify/sc4props/RESULTS.md). Voice
rules, numbers only from RESULTS files, headless check desktop + 390 px. Results verify/guide2/RESULTS.md.

## Rules

Windowed game, posted input only, test slot, kill only PIDs you started, no git add / commit. plop owns bldimport.py,
bldweb.js, classifier.html, sc3pack.js this round; guide2 owns docs/buildings/index.html and the guide generator.
