# Round 2026-11-20g: a faster building suite (run_all.sh)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: re/sessions/CHILD_PROTOCOL.md. Workspace from main after sc4trees.
Owner (2026-11-20): children reported the suite takes 45 minutes, "is there anything we can do to speed up testing";
after the measured breakdown the owner picked "All five".
Measured (verify/suitetime/run1.log, main 2a81047 before lotshape, every step line now carries its wall time):
41 of 41 in 2,843 s = 47.4 min. SC4 install group (steps 32-35) 1,396 s = 49%: sc4_install.mjs 552, sc4_install_setup.py
487, pagetest sc4install --sc4grow 250, pagetest sc4install 107. SC4 download group 886 s. Everything else 561 s. The
Python reference builds (golden_setup 160, sc4_install_setup 487, sc4_baseprops_setup 124, sc4_packs_setup 123,
sc4_lottex_setup 112, sc4_props_setup 106, golden_setup sc4 52) = 1,164 s. One known flake: Chrome start-up EBUSY on
DevToolsActivePort (a pagetest step failed once, passed alone).

## Stream suitespeed (opus / medium)

1. Small fixed install set: about 20 buildings from the SC4 install that cover every path (civic of each service, park,
   reward with a population rule and the default, landmark, square and non-square lots, 5x5, a texture-atlas view, a
   tiled tall building, the Large High School case, a growable of each purpose for --growables, props from the install,
   lot textures). Chosen with evidence (which code branches each one hits), listed in one place. The whole install
   (and the --sc4grow page step) only with a deep switch (e.g. SUITE_DEEP=1), which releases use.
2. Reuse the Python reference: each setup step stores a key (hash of the Python code it runs, its inputs and arguments)
   next to its output and skips the build when the key matches the last passing build. A forced rebuild switch.
   Byte-identity checks stay exactly as strict (the page side always runs).
3. Run only what a change touches: a mode that maps changed files (git diff against main or a given ref) to step
   groups (page / CSS / fonts / pack reader / bldimport + bldrender + bldweb / sc4conv + sc4web / install), plus "all".
   Unknown files run everything. Print what was skipped and why.
4. Groups side by side: run the independent groups in parallel inside one test slot (memory cap: check
   PROYECTOS_TEST_MEM_GB, children used 6), output kept per group and printed in order, the "[N/M] name (t s) PASS"
   lines and the final count unchanged so the Happy progress bar still works.
5. Chrome retry: one retry when Chrome fails to start (the EBUSY flake) in pagetest.mjs and the other headless tools.
6. Time it: a full normal run, a deep run, a cached rerun, and a changed-files run for a CSS-only change and a
   converter change, all with the per-step times. Every check that ran before still runs in the deep mode. Results
   verify/suitespeed/RESULTS.md, update the run_all.sh header and the guide only if they mention timings,
   STATUS re/sessions/STATUS_suitespeed.md.

## Rules

Test slot for every run, PROYECTOS_TEST_HUB=off (the SC4 install exists only on this PC). SC4 / EA / community content
never in the repo. No git add / commit.
