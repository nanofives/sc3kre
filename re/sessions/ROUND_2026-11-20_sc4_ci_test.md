# Round 2026-11-20: SimCity 4 commercial and industrial buildings, tested and fixed

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main 0ff206c+.
Owner (2026-11-20): game props and lot textures stay ON by default ("Keep on"), next "Test C and I packs".
State: of the commercial and industrial SC4 buildings only one office tower (Global Office Center) was ever tried in
game (verify/sc4pass2). The class rule for C and I is the tool's own, not measured (guide: "$ = low wealth, $$ or $$$
= high, up to 100 jobs light, up to 1,000 medium, more dense").
Sources: the SC4 install (C:\Program Files (x86)\Steam\steamapps\common\SimCity 4 Deluxe\, Maxis' own C and I
growables are in it, EA content: read in place, never in the repo, docs/ or a release, pictures local), the BSC
Common Dependencies Pack and the packs in MAIN stage\st_packs\sc4, and community C and I downloads the owner adds to
\\mariano-server\Compartido (read over SSH: scp -i ~/.ssh/id_ed25519_rpi mariano@mariano-server.local:/srv/compartido/...).

## Stream sc4ci (opus / high)

1. Corpus: Maxis' own commercial and industrial growables from the install (CS$, CS$$, CS$$$, CO$$, CO$$$, IR farms,
   ID dirty, IM manufacturing, IHT high-tech), converted through the same code as a download. Today "Open SC4 game"
   converts civic, parks, rewards and landmarks only: add the growables behind it so they can be tested, all off by
   default, and report the numbers. Whether the page offers them to players is the owner's call: say what it would
   take and what it gives.
2. The class rule with evidence: SC4 wealth and jobs per building against the jobs of the SC3 stock buildings of each
   C and I class and lot size (bldimport takes stats from a stock building, so the SC3 class decides jobs, pollution,
   demand). Keep the rule or change it, with the numbers. Farms (SC3 9300) and dirty / clean industry the same.
3. Lots: C and I SC4 lots are often long (1x2 .. 4x6). Count how many fit 1x1..4x4 as the smallest square, how many
   stay off for size, what the yard / props / textures crop costs on long lots.
4. In game: a few commercial (shops, offices) and industrial (dirty, manufacturing, high-tech, a farm) buildings
   grown where those classes develop (Frankfurt for dense commercial, Sacramento or Madison for industry), with
   pictures next to stock buildings. A growable that does not grow: find out why (class demand, lot, weight).
5. Fix what breaks (readers, classes, lots, the page). Python = page byte for byte, run_all.sh passes every step
   (all six args + SC3PACK_PACKS + SC4INSTALL, PROYECTOS_TEST_HUB=off), sync_css.py --check / --publish.
6. Community C and I packs from the share when the owner adds them: same checks. If none by the end, say so.
7. Guide template (MAIN verify/bldpack/work/guide_template.html + make_docs.py, keep the sample-pack link): replace the
   "only the office tower was tried" lines with what was measured. Results verify/sc4ci/RESULTS.md.

## Rules

Windowed game, never the real mouse or keyboard, test slot, kill only PIDs you started, delete BMP dumps, no git add /
commit. SC4 / EA / community content and pictures of it never in the repo or docs.
