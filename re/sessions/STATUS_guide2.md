# STATUS guide2 (round 2026-11-19h)

## goal
Guide (docs/buildings) for players: airport / seaport buildings and SC4 lot props, through the generator.

## verdict
Done. Page regenerated, 21 of 21 headless checks PASS (desktop 1280, phone 390). Details verify/guide2/RESULTS.md.

## built
docs/buildings/index.html via verify/bldpack/work/make_docs.py (template edited in place). No code changes.

## proven game-side vs static only
Text only. Facts from verify/airsea and verify/sc4props RESULTS (their in-game runs). Nothing new run in game.

## blocked on
Nothing.

## files owned
- dev/guide2/wt/docs/buildings/index.html (worktree, branch child/guide2)
- verify/bldpack/work/guide_template.html (MAIN, edited in place)
- verify/guide2/RESULTS.md, guide_check.mjs, guide_check.log, guide_template.before.html, README.before.txt, owner_shots/*.jpg
- re/sessions/STATUS_guide2.md
- stage/sample_pack/README.txt rewritten by make_docs.py, byte-identical (gitignored stage)

## game-harness need
None.

## asks of other sessions
None. Note for plop: when landmarks land, the "What it does not do" ploppables line and #ports neighbour need updating.
