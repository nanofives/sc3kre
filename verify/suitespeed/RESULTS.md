# suitespeed: a faster building suite (run_all.sh), round 2026-11-20g

Owner picked "All five" on 2026-11-20. All five are built and every mode was run for real on LIVING-PC.
Worktree `dev\suitespeed\wt`, branch `child/suitespeed`, base main 297672d.

## 1. Verdict

| mode | how (plus the six arguments, `SC4INSTALL`, `SC3PACK_PACKS`, `PROYECTOS_TEST_HUB=off`) | steps | result | suite wall | memory peak |
|---|---|---|---|---|---|
| before: run1 (main 2a81047, serial) | `run_all.sh` | 41 | 41 PASS | 2,843 s (47.4 min) | not logged |
| before: baseline today (main 297672d, serial) | old `run_all.sh` from a HEAD snapshot | 42 | 42 PASS | 2,443 s (40.7 min) | 5.33 GB (cap 6) |
| normal, cold (empty work folder) | default | 41 | 41 PASS | 928 s (15.5 min); 786 s on a quieter PC | 3.16 GB (cap 6) |
| normal, cached rerun | default, same work folder | 41 | 41 PASS | 441 s (7.4 min); 332 s on a quieter PC | 3.43 GB (cap 6) |
| CSS-only change | `SUITE_CHANGED=files:docs/assets/sc3ui.css,re/tools/bldimport/classifier.html` | 4 | 4 PASS, 37 listed as skipped | 14 s | small |
| converter change | `SUITE_CHANGED=files:re/tools/sc4conv/views.py` | 18 | 18 PASS, 23 skipped | 359 s (6.0 min) | not logged |
| deep (releases) | `SUITE_DEEP=1`, `PROYECTOS_TEST_MEM_GB=8` | 42 | 42 PASS | 1,656 s (27.6 min) | 6.56 GB (cap 8) |

Load: the final normal, cached and deep runs (07:24 to 08:30, 2026-11-21) ran with the PC at 55% CPU on average from
other sessions (63 samples in `load.log`: Mashed game runs, Defender). I waited 2 hours for a quiet window and none
came. The "quieter PC" figures are the runs of 00:13 to 00:50 with the same code except the memory fixes of section 6
(`cached3.log`, `css.log`, `conv.log`, and a cold run of 786 s whose per-step log a later run overwrote). The baseline
ran beside my coverage runs for part of its time.

Every check of the old run_all.sh still runs in deep mode, byte for byte, with the same "[N/M] name (t s) PASS" lines
and the same final count line. The normal mode runs every check too, on the install set instead of the whole install,
and drops one step (the page with the growables box ticked, which needs the whole install).

## 2. The five changes

### 2.1 The SC4 install set (normal mode) and SUITE_DEEP=1 (releases)

`re/tools/bldimport/webtest/sc4_install_set.json`: 28 buildings, each with its reason, and the page counts for the set
(28 cards, 23 on). `sc4_install_setup.py --set`, `sc4_install.mjs --set` and `pagetest.mjs --sc4only` convert only
those (sc4conv.py `--only`, sc4web.js `opt.only`). The install is still listed and indexed whole, by slices, so the
index, notes and "read by slices" checks are unchanged. The packed 4-building subset and the 10-building growables run
are as before. `--set` refuses a set without the packed subset.

How the set was chosen (`sc4_set_cover.py`, the evidence tool, never run by the suite):

- Python: sc4conv.py over the whole install with `--growables` under a line tracer (sys.monitoring), every line of
  `re/tools/sc4conv/*.py` and `re/tools/bldimport/*.py` recorded per building while it is written. The 113 civic,
  park, reward and landmark buildings reach 1,020 lines. The 7 buildings the checks name reach 964. A greedy cover added
  7: Hollywood sign (views.py 196-222, the joint tile fit, only it reaches them), Lifeguard tower (props.py 292-298,
  lottex.py 91), Convention Center (props.py 372-378, lottex.py 158, a 5x5 reward), Urgent care clinic (views.py 502),
  Large High School (views.py 291, the flat atlas piece left out), Gateway Arch (sc4conv.py 401, no lot textures),
  Ranger Station (props.py 278). Then 14 for the cases the brief lists: library, museum, jail, college, K-8 school,
  tennis court (big park), Toxic Dump (no population condition, default 20000), Private School 2 (a condition on one
  wealth, default, 4x2 lot), University Admin Tower (r1+r2+r3 summed, 15000), Seafirst Tower (5x5 landmark), Sphynx
  (4x2 landmark), Empire State Building (tall, tiled, 8x8, off), two cemeteries (rewards sharing a name: first on, next
  off).
- Result: the set reaches 1,020 of the 1,020 per-building lines. Of the 1,146 run-level lines it misses 10, all on the
  `--growables` path (sc4conv.py 90, 741, 795, 816, 831-833, 850, 1021, views.py 203), which the growables run and the
  deep page step cover. Growables outside the 10-building growables run reach sc4conv.py 109-146: the old suite never
  converted those in Python either, only the deep page step opens them.
- JS (V8 block coverage, one whole-install convert against one set convert): sc4web.js 1,761 lines ran on the whole
  install, 1,765 with the set, 0 only on the whole. bldweb.js 349 and 349, 0 only on the whole.

Deep mode converts the whole install (113 cards, 82 on), runs the `--sc4grow` page step (423 cards) and builds every
Python reference fresh. A deep run with `PROYECTOS_TEST_MEM_GB` under 8 prints a warning (section 6).

### 2.2 Reuse of the Python reference

Each setup step (golden_setup.py, sc4_*_setup.py x5, sc3pack_testpacks.py, sc3pack_golden.py) runs with
`suite_trace/sitecustomize.py` first on PYTHONPATH. Its audit hook records, in every Python process of the step (the
setup and each sc4conv.py / bldimport.py it starts), every file opened for reading (code included: imports open their
.pyc, mapped back to the .py), every file written, renamed or copied (CopyFile2 included), and every folder listed.
After a passing build `<work>\.suite_cache\<step>.json` keeps the command line, the Python version, a sha256 of every
repo file read, size + mtime of every other input (game tree, SC4 files, the Python library), a hash of each listing,
and size + mtime of every output. The next run skips the build only when all of them match and the outputs are still as
written. `SUITE_REBUILD=1` builds again. Deep mode always builds fresh. The check steps (the page side) always run.

Verified: golden_setup sc4 built (35 s), then cached (0 s: 43 repo files, 269 other inputs, 2,307 outputs). The pack
group: built, cached, a comment added to sc3pack.py rebuilt sc3pack_golden.py only, restoring it rebuilt again,
SUITE_REBUILD rebuilt both. The converter-change run rebuilt all 6 SC4 references on the views.py edit (old and new
sha in the rebuild line). One cached run rebuilt 3 references because `stage\release\Apps\Sys\SYS.PAK` had a new mtime
between runs (22:46, during the baseline). The suite does not write it: install_golden.mjs leaves its size, mtime and
sha256 as they were (checked). That is the key doing its job.

### 2.3 Changed-files mode

`SUITE_CHANGED=<ref>` (1 = main): `git diff <merge base>`, untracked files, and ignored new files under re/tools and
docs (the .gitignore is deny-by-default, so a new tool file stays ignored until `git add -f`). `SUITE_CHANGED=files:a,b`
gives the list by hand. Each file maps to tags (RULES in suite.py): page, css, fonts, pack, bld, sc4, install, all,
none. A step runs when its tags meet a changed file's tags, plus the setup step of its group (cached when nothing it read
changed). Unknown files run everything. A Python tool under re/tools outside the map is looked up in the cache records:
read by a reference build means everything, read by none means nothing (no records: everything). classifier.html changed
only between the sync_css.py markers counts as CSS only. Skipped steps are printed first, each with the code it depends
on. `SUITE_LIST=1` prints the plan without running.

- CSS-only (a comment in sc3ui.css, synced by sync_css.py): sync_css --check, sc3font_check, build_fonts --check,
  fonts_inline. Skipped: the page tests (they check install bytes and DOM state, not style), the goldens, the pack
  reader, every SC4 step.
- Converter (sc4conv/views.py): the 18 SC4 steps. Skipped: the SC3 goldens and page tests, the .bld readers, CSS and
  fonts, the pack reader (none of them imports sc4conv).
- This branch itself (suite.py and the runner files) maps to "all", as it should.

### 2.4 Groups side by side, in one test slot

11 groups: sc3 (golden_setup, golden.mjs, install_golden, zip_golden, bld1999 / bldside when given), sc3page (the 8
golden-case page tests, started once golden_setup is done), bldread, page, pack, sc4dl, sc4packs, sc4props, install,
baseprops, lottex. `SUITE_JOBS` (default 4) run at once, the longest first. Each step's output is held and printed in
the old order (its own lines, then its "[N/M] name (t s) PASS" line), so logs read as before and the Happy progress bar
counts up in order. Then "[suite] wall ... groups: ..." and "<k> of <M> steps passed". `SUITE_JOBS=1` is the old order,
one step at a time.

Memory: the page steps that hand the install's .dat files or the BSC pack to Chrome never run two at once, and the
`--sc4grow` page step runs alone (section 6). Normal-run peaks 3.16 to 3.93 GB under the 6 GB cap.

### 2.5 Chrome retry

`webtest/chrome.mjs` (used by pagetest.mjs, fonts_inline.mjs, sc3pack_pagetest.mjs, check_roundtrip.py): an unreadable
or half-written DevToolsActivePort (the EBUSY flake of 2026-11-19 and 11-20) is read again on the next poll, and a
Chrome with no debugging port or page target in time is stopped by its PID and started once more in a new profile.
sc3font_check.py retries its --dump-dom / --screenshot Chrome once on exit code, empty DOM or missing picture. A page
that runs and reports a wrong result is never retried. No retry was needed in any run of this round.

## 3. Per step (seconds)

Normal, cached and deep are the final runs (55% CPU from other sessions). CSS and converter change are the quieter
runs. In side-by-side runs a step's time includes waiting for CPU, so the sum of steps is larger than the wall.

| # | step | run1 (11-20, 41 steps) | baseline (serial, 42) | normal | cached | deep | CSS change | converter change |
|---|---|---|---|---|---|---|---|---|
| 1 | golden_setup | 160 | 207 | 349 | 0 | 404 | - | - |
| 2 | golden.mjs | 50 | 70 | 259 | 234 | 196 | - | - |
| 3 | install_golden.mjs | 105 | 60 | 91 | 132 | 111 | - | - |
| 4 | zip_golden.mjs | 9 | 5 | 6 | 12 | 8 | - | - |
| 5 | pagetest.mjs kenney | 15 | 10 | 10 | 10 | 10 | - | - |
| 6 | pagetest.mjs bld | 5 | 4 | 4 | 5 | 5 | - | - |
| 7 | pagetest.mjs styles | 24 | 13 | 16 | 17 | 15 | - | - |
| 8 | pagetest.mjs ports | 34 | 13 | 12 | 14 | 13 | - | - |
| 9 | pagetest.mjs landmarks | 33 | 20 | 22 | 27 | 26 | - | - |
| 10 | pagetest.mjs civic | 58 | 17 | 20 | 30 | 25 | - | - |
| 11 | pagetest.mjs lotshape |  | 42 | 115 | 60 | 50 | - | - |
| 12 | pagetest.mjs landmarkdesc | 16 | 22 | 35 | 33 | 35 | - | - |
| 13 | bld_js_check.mjs | 1 | 1 | 1 | 2 | 1 | - | - |
| 14 | bld_js_check.mjs --reader bldweb | 0 | 0 | 0 | 0 | 0 | - | - |
| 15 | check_roundtrip.py | 4 | 3 | 3 | 4 | 3 | - | - |
| 16 | sync_css.py --check | 1 | 0 | 0 | 0 | 1 | - | - |
| 17 | sc3font_check.py | 15 | 9 | 12 | 15 | 12 | 8 | - |
| 18 | build_fonts.mjs --check | 8 | 5 | 6 | 5 | 5 | 4 | - |
| 19 | fonts_inline.mjs | 2 | 2 | 2 | 3 | 2 | 2 | - |
| 20 | sc3pack_testpacks.py | 1 | 0 | 0 | 0 | 0 | - | - |
| 21 | sc3pack_golden.py | 9 | 7 | 8 | 0 | 11 | - | - |
| 22 | sc3pack_golden.mjs | 7 | 3 | 5 | 7 | 6 | - | - |
| 23 | sc3pack_pagetest.mjs | 4 | 3 | 4 | 4 | 4 | - | - |
| 24 | golden_setup sc4 | 52 | 34 | 46 | 0 | 46 | - | 66 |
| 25 | sc4_golden.mjs | 31 | 21 | 50 | 39 | 31 | - | 22 |
| 26 | pagetest.mjs sc4 | 26 | 19 | 26 | 19 | 23 | - | 16 |
| 27 | sc4_packs_setup.py | 123 | 69 | 95 | 0 | 109 | - | 96 |
| 28 | sc4_packs.mjs | 28 | 20 | 51 | 40 | 44 | - | 46 |
| 29 | pagetest.mjs sc4empty diego | 4 | 3 | 4 | 4 | 3 | - | 2 |
| 30 | pagetest.mjs sc4empty im | 2 | 2 | 9 | 4 | 2 | - | 3 |
| 31 | sc4_props_setup.py | 106 | 66 | 281 | 0 | 216 | - | 52 |
| 32 | sc4_props.mjs | 81 | 46 | 67 | 94 | 84 | - | 55 |
| 33 | sc4_install_setup.py | 487 | 398 | 232 | 0 | 855 | - | 187 |
| 34 | sc4_install.mjs | 552 | 534 | 375 | 356 | 485 | - | 149 |
| 35 | pagetest.mjs sc4install | 107 | 99 | 36 | 49 | 94 | - | 24 |
| 36 | pagetest.mjs sc4install --sc4grow | 250 | 229 | deep only | deep only | 222 | - | - |
| 37 | sc4_baseprops_setup.py | 124 | 117 | 174 | 0 | 230 | - | 98 |
| 38 | sc4_baseprops.mjs | 67 | 70 | 103 | 261 | 90 | - | 87 |
| 39 | pagetest.mjs sc4baseprops_inst --sc4with | 32 | 23 | 34 | 42 | 35 | - | 29 |
| 40 | pagetest.mjs sc4baseprops_inst --sc4remember | 26 | 26 | 33 | 37 | 34 | - | 30 |
| 41 | sc4_lottex_setup.py | 112 | 94 | 164 | 2 | 184 | - | 100 |
| 42 | sc4_lottex.mjs | 72 | 57 | 181 | 150 | 112 | - | 83 |

Normal mode runs the install steps with `--set` (28 buildings). Sums of step times: baseline 2,443 s, final normal
2,941 s (wall 928 s), final cached 1,711 s (wall 441 s), final deep 3,842 s (wall 1,656 s).

## 4. What each mode skips, and why

| mode | skipped | why that holds |
|---|---|---|
| normal | 85 of the 113 install buildings, and the `--sc4grow` page step | the set reaches every line the 113 reach, Python and JS (2.1); deep mode runs both for releases |
| cached | the Python builds whose key is unchanged | the key covers every file the build read, listed and wrote; any change rebuilds (2.2); the page side always runs |
| CSS change | 37 steps | none of them depends on sc3ui.css or its copy (2.3) |
| converter change | 23 steps | none of them reads sc4conv or sc4web.js (2.3) |
| deep | nothing | |

## 5. How to run

```
SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe" SC3PACK_PACKS=MAIN\stage\st_packs \
PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh <work> \
  stage\release stage\kits "<JMyers .zip>" stage\st_packs\sc4_jmyers_homes\jar stage\st_packs\sc4
# while working: add SUITE_CHANGED=1 (only what your diff against main touches)
# release: SUITE_DEEP=1 with PROYECTOS_TEST_MEM_GB=8
```

Keep the work folder between runs: the cached references live in `<work>\.suite_cache`.

## 6. Found on the way

- **Pipe stalls (fixed in suite.py).** With the steps' output on a pipe, small steps took 85 to 215 s (bld_js_check
  1 s to 85 s, fonts_inline 2 s to 205 s). A pipe is finished only when every holder closes it, and Chrome children of a
  page test can hold it after their parent exits. Output now goes to a temp file and only the process's own exit counts,
  as with bash. The next cached rerun went from 540 s to 332 s.
- **The `--sc4grow` page step is at the edge of a 6 GB cap on its own.** Serial baseline peak 5.33 GB, the step alone
  5.36 GB. Two deep runs under 6 GB stalled in it (job at 6.00 GB, CAP, Chrome's renderer at 3.66 GB, its GPU process
  crashed once), and pagetest.mjs had no timeout on a dead renderer, so the first one waited 62 min until I stopped it by
  its PID. Now that step runs alone, pagetest's DevTools calls time out after 120 s (the page's own 900 s limit then
  holds), and a deep run under 8 GB prints a warning. Deep at 8 GB: 42 of 42, peak 6.56 GB. Children's serial runs
  logged CAP at 6 GB before this round too (runs.log 2026-11-20 13:45, 21:45, 22:25).
- **CPU contention.** The Python references use several cores each (numpy, OpenBLAS). OpenBLAS's thread count is left
  alone (it can change summation order, and the checks are byte for byte). `SUITE_SETUPS=<n>` limits how many build at
  once. Default: no limit, since the one clean comparison (cold normal on a quiet PC, 786 s) had 4 at once.
- **Next lever, not done.** In the cached run the install group (405 s) is the critical path: sc4_install.mjs converts
  the 28 buildings three times (convert, rerun, a second pick) plus the growables run. The 14 buildings the line cover
  needs would roughly halve it, at the cost of the 14 case buildings the brief asked for. An owner call.

## 7. Files

Worktree (all need `git add -f`, re/tools is deny-by-default): `re/tools/bldimport/webtest/` run_all.sh, suite.py,
suite_trace/sitecustomize.py, sc4_install_set.json, sc4_set_cover.py, chrome.mjs, sc4_install_setup.py, sc4_install.mjs,
pagetest.mjs, pagetest.js, fonts_inline.mjs, sc3pack_pagetest.mjs, sc3font_check.py, and
`re/tools/bldimport/check_roundtrip.py`. MAIN: this file and `re/sessions/STATUS_suitespeed.md`.

Logs here: base.log, final_normal.log, final_cached.log, final_deep.log, cached3.log, css.log, conv.log, load.log,
grow_alone.log, cover_whole/cover.json and cover_set/cover.json (line lists only), v8w.log, v8s.log.
