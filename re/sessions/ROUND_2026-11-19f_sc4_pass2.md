# Round 2026-11-19f: SC4 conversion, second pass (more packs)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main.
Previous: verify/sc4conv, verify/sc4web, verify/sc4diag (JMyers only). Owner downloaded more packs (2026-11-19).

## Input (local only, never in git or docs): MAIN\stage\st_packs\sc4\

- `Global Office Center.zip`: own .SC4Model (0x5ad0e817 group 0x3352a0bb), growable / ploppable / landmark lots,
  .SC4Desc files. A tall office tower: the first non-house, non-installer pack.
- `DiegoDLGrowablePack2019_Vanilla_DN.zip`: 23 towers, ONLY .SC4Lot + .SC4Desc; readme: each building's model is a
  separate download. A lot-only pack.
- `I-M manufacturers lots.zip`: lots + a blank.SC4Model, reusing SC4's own built-in industrial buildings. Lot-only.
- `SC4D LEX Legacy - BSC Common Dependencies Pack V9e.zip` (1.7 GB, a .jar inside): props and textures for lots.

## Stream sc4pass2 (opus / medium)

1. Global Office Center: convert with sc4conv.py and the page (sc4web.js), byte identity kept. Tall-building checks:
   the box-and-picture reprojection on a tall narrow building, night textures (ignored or used?), the class mapping
   for an office (CO$$ / CO$$$ to SC3 commercial classes, say which), lot size (how big SC4 lots map), the
   growable vs ploppable vs landmark versions (convert the growable, identify the others as ploppables for later).
   Grow it in a dev tree (a city with high-wealth commercial demand, or the churn setting the sample pack used),
   picture next to stock towers.
2. Lot-only packs (DiegoDL, I-M): the converter and the page must say plainly that the pack holds no building models,
   name which buildings are missing (from the descriptors / LText / exemplar model keys), and for DiegoDL quote the
   readme's dependency list if present. No crash, no empty install. Tests for both.
3. BSC Common Dependencies Pack: read its .jar contents (props, textures), measure what a lot's props would need
   (prop exemplars, their models are the same box-and-picture S3D?), and report whether converting lot props
   (fences, trees, cars around a converted building) is feasible and how. Report only, no build this round.
4. run_all.sh must pass every step (extend sc4_golden for the tower). Do not edit classifier.html, sc3ui.css,
   sync_css.py, sc3font.js (child gamefont) or bldfile.py / bldweb.js / sc3pack.js (children sc3compat-a / -b).
Results MAIN\verify\sc4pass2\RESULTS.md, STATUS MAIN\re\sessions\STATUS_sc4pass2.md.

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, no git add /
commit. Nothing from SC4 packs into the repo or docs/.
