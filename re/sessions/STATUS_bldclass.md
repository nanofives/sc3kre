# STATUS bldclass (child, sonnet / medium)
## goal
re/tools/bldimport/classifier.html: standalone model classifier page, writes models.json (round 2026-11-18b).
## verdict
done, checks passed (see verify/bldclass/RESULTS.md); direct folder write and glTF/FBX unverified (need owner)
## built
classifier.html, samples/*.obj, samples/models.json
## proven game-side vs static only
static page only, no game involved
## blocked on
nothing
## files owned (worktree MAIN\dev\bldclass\wt)
re/tools/bldimport/classifier.html
re/tools/bldimport/samples/make_samples.py, house_a.obj, shop_a.obj, factory_a.obj, models.json
re/tools/bldimport/check_roundtrip.py (when added)
verify/bldclass/RESULTS.md, roundtrip_output.txt, grid_light.png, preview_dark.png, edit_multi.png, phone.png (MAIN, gitignored pictures except RESULTS.md)
## game-harness need
none
## asks of other sessions
none
