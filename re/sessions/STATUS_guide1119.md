# STATUS guide1119 (2026-11-19)

**goal**: bring docs/buildings/index.html up to date for players: Simtropolis BA packs, render kit, SC4 sc4pass2 facts.

**verdict**: done. Details `verify/guide1119/RESULTS.md`.

**built**: guide regenerated through `verify/bldpack/work/guide_template.html` (edited in place, MAIN, gitignored) +
`make_docs.py` (`--zip` set to the 2026-11-18 sample pack URL, so that link is unchanged).

**proven**: headless Chrome 13 of 13 PASS at 1280 and a true 390 px phone (`verify/guide1119/guide_check.log`),
pictures `verify/guide1119/owner_shots/`.

**blocked on**: nothing.

**files owned**:
- `dev/guide1119/wt/docs/buildings/index.html` (the only repo change)
- MAIN local: `verify/bldpack/work/guide_template.html` (generator source, edited in place), `verify/guide1119/`
  (RESULTS.md, guide_check.mjs, guide_check.log, owner_shots/), this file.
- Side effect: `make_docs.py` also rewrote `stage/sample_pack/README.txt` (same generator, same inputs).

**game-harness need**: none. **asks of other sessions**: none.
