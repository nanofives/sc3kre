# STATUS suitespeed (round 2026-11-20g, a faster building suite)

## goal
run_all.sh (47.4 min on main 2a81047, verify/suitetime/run1.log) faster without a looser check: a small fixed SC4 install
set with a deep switch, reuse of the Python reference, a changed-files mode, groups side by side in one test slot, one
Chrome retry at start-up.

## verdict
Done (2026-11-21 08:40). All five built, every mode run for real, all passing. Full detail: verify/suitespeed/RESULTS.md.

| mode | steps | result | wall |
|---|---|---|---|
| baseline, old run_all.sh, serial (today) | 42 | 42 PASS | 2,443 s |
| normal, cold | 41 | 41 PASS | 928 s (786 s on a quieter PC) |
| normal, cached rerun | 41 | 41 PASS | 441 s (332 s quieter) |
| CSS-only change | 4 | 4 PASS | 14 s |
| converter change | 18 | 18 PASS | 359 s |
| deep (SUITE_DEEP=1, cap 8 GB) | 42 | 42 PASS | 1,656 s |

The final runs had the PC at 55% CPU from other sessions (load.log).

## built (worktree dev\suitespeed\wt, branch child/suitespeed)
- `webtest/suite.py`: the runner (steps, 11 groups, cache, changed-files map, output held and printed in the old order);
  run_all.sh only starts it, same arguments and env
- `webtest/suite_trace/sitecustomize.py`: the audit-hook tracer behind the Python reference cache
- `webtest/sc4_install_set.json`: the 28-building install set, each with its reason, page counts 28 cards / 23 on
- `webtest/sc4_set_cover.py`: the evidence tool (per-building line coverage, V8 comparison), never run by the suite
- `webtest/chrome.mjs`: Chrome start-up with one retry; sc3font_check.py retries its Chrome once on start-up failure
- `--set` in sc4_install_setup.py / sc4_install.mjs, `--sc4only` in pagetest.mjs + pagetest.js; pagetest.mjs DevTools
  calls time out after 120 s (a dead renderer used to hang it with no limit)

## proven vs static only
- Install set: 1,020 of 1,020 per-building Python lines of the 113 buildings; 10 run-level lines missed, all on the
  --growables path. JS: sc4web.js and bldweb.js, 0 lines run by the whole install and not by the set.
- Cache: hit, miss on a code edit, rebuild switch, converter edit rebuilding all 6 SC4 references, all measured.
- Changed-files: CSS-only and converter runs above, real edits, restored after.

## owner calls / notes for the orchestrator
- Deep runs need PROYECTOS_TEST_MEM_GB=8: the --sc4grow page step peaks at 5.3-5.4 GB on its own (also in the old serial
  suite) and two deep runs under 6 GB stalled in it. suite.py warns.
- Next lever not taken: the install group is the critical path of a cached run; cutting the set to the 14 buildings the
  line cover needs would roughly halve it, at the cost of the 14 case buildings the brief asked for.

## blocked on
nothing

## files owned (all need `git add -f`: re/tools is deny-by-default)
re/tools/bldimport/webtest/run_all.sh, suite.py, suite_trace/sitecustomize.py, sc4_install_set.json, sc4_set_cover.py,
chrome.mjs, sc4_install_setup.py, sc4_install.mjs, pagetest.mjs, pagetest.js, fonts_inline.mjs, sc3pack_pagetest.mjs,
sc3font_check.py; re/tools/bldimport/check_roundtrip.py. MAIN: re/sessions/STATUS_suitespeed.md,
verify/suitespeed/RESULTS.md.

## game-harness need
none (no game runs)

## asks of other sessions
none
