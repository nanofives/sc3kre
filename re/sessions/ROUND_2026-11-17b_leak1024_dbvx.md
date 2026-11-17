# Round 2026-11-17b: rotation leak on a 1024 city + junctions 49 / 51 / 53

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces made from main 877628c (= release sc3mods-2026-11-17c + records).
Base tree: `stage/release` = LAN 2026-11-17c. Test cities kept from the cleaned-up workspaces: `stage/sandbox_1117c/`
(`xsect_sandbox_clear.sc3`, `xsect_sweep_built.sc3`, `xsect_flat.sc3`, `showcase_clean1.sc3`, `showcase_clean1_nz.sc3`,
`showcase_clean2.sc3`, `showcase_built_pristine.sc3`, `rotleak Berlin.sc3`). Copy what you need into your tree's `Cities\`.

| stream | owner request | expected |
|---|---|---|
| leak1024 | "Leak test on 1024" (2026-11-17, after release 2026-11-17c) | the rotation / zoom leak measured on a 1024 city, fixed build against the 2026-11-17 behaviour |
| dbvx49 | "Fix 49 / 51 / 53" (same message) | the three short-arm junctions still mixed after DBVSHORT get the mod's pieces |

Owner order: cleanup, leak test, fix 49 / 51 / 53, then a gallery of all the junctions (next round, on the build that
carries the dbvx49 fix).

## leak1024

Background: `verify/rotleak/RESULTS.md` and `re/sessions/STATUS_rotleak.md`. Stock SIMSPR PrepareImage (0x10012b98)
AddRefs twice, sc3perf's sprite budget made it about 5x faster. SPR_IMGREF (sc3perf, main fd32aff) fixed it: on Berlin,
100 paused rotations grew 0.69 MB each (15.5 before, crash at rotation 94). Its record says: "1024 cities were not run
here. The code path is the same, and a 1024 city's view holds more art per rotation."

Do:
- `Europolis 1024.sc3` (in the base tree's `Cities\`). If it is too sparse to load the view with art, say so and add a
  denser 1024 city (your call, in your tree only).
- Arms: A = 2026-11-17c as shipped (all mods, SPR_IMGREF on). B = the same with `SC3PERF_SPR_IMGREF=0` (the 2026-11-17
  behaviour). Stock cannot load a 1024 city, so there is no stock arm.
- 100 rotations paused at zoom 4 and at the widest zoom, each arm. Then the 15-minute soak (sim running, rotations,
  zoom round trips, minimap jumps) as in rotleak, each arm. Record private MB, largest free block, VEH faults, crash
  (time, rotation number, signature). Reuse `verify/rotleak/` tools (`rotmem.py`, `soak.py`, `ab100.sh`).
- Answer in numbers: MB per rotation on 1024 for A and B, whether A's residual is still flat across 100, and the
  measured largest free block at the end. If A's residual per rotation is clearly larger than Berlin's, find which art
  it holds (rotleak's "Residual" section has the method) and report. No code change without the orchestrator's OK.

Model / effort: sonnet / medium (measurement with existing tools).

## dbvx49

Background: `verify/diagarm/RESULTS.md` section 6 ("Open"). After DBVSHORT (main 60d89c2):
- 49 DA x DB cross at 4 rows, 51 DA x DB T2 and 53 DB x DB cross in the showcase's layout: "one core cell off every
  template". In 49 the diagonal avenue's 4-row arm ends exactly at the box (no arm past it). At 3 rows on the sandbox
  49 / 51 / 53 already reach the 6-row baseline (5 / 5 / 4 stock cells), so the open shapes are the showcase layout
  (`showcase_built_pristine.sc3`: 13 / 12 / 12 stock cells) and 49 at 4 rows.
- diagarm's note: these need new crossing template variants (`dbvx_build`).

Do:
- Reproduce on `xsect_sandbox_clear.sc3` (arms 3, 4, 6 rows, both draw orders) and in `showcase_built_pristine.sc3`.
- Fix so 49 / 51 / 53 get their junction boxes at those arm lengths, with an off switch for any C change. A package
  change bumps its version and is installed in YOUR tree only. The orchestrator installs it into `stage/src`.
- Pictures: before / after per case at zoom 4, phone-sized JPEG, in `verify/dbvx49/owner_shots/`.
- Regression: full 80-case sweep on a fresh sandbox, read back against the released stage (`verify/final1117/s1`, as
  diagarm's `cmp_stage.py` did): every case other than 49 / 51 / 53 identical. Short-arm layouts 19 34 43 45 50 52 54
  55 unchanged. Berlin read-back 0 cells differ with the fix on and off.
- Out of scope unless it is the same mechanism: 50 52 54 55 with 3-row stems, DA family at 3 rows (diagarm section 6).

Model / effort: opus / high (junction rule and template work in `sc3netmod_dbv.c` / the DBVX templates).

## Rules (both)

Windowed game, posted input only (never the real mouse, keyboard or foreground), test slot for long runs, kill only
PIDs you started, delete BMP dumps once converted, STATUS file at every milestone, no `git add` / `git commit`.
