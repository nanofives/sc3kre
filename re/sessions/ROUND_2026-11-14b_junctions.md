# Round 2026-11-14b: fix every red and yellow case of the intersection sweep

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces made from main `bada3bc`.
Owner request (Mariano, 2026-11-14): "will you fix all the red and yellow ones?" (red = BROKEN, yellow/amber =
refused by design, in `verify/xsect/RESULTS.md` and the sheets in `verify/xsect/owner_shots/sheet_*.png`).

## Inputs every stream uses

- Sweep record: `verify/xsect/RESULTS.md` (case, build, log line, verdict), `verify/xsect/cases/<id>.json` +
  `<id>_grid.txt` (cells and piece ids), `verify/xsect/STATUS` = `re/sessions/STATUS_xsect.md`.
- Sweep tooling (on disk in MAIN, untracked): `verify/xsect/sweep.py`, `ramp.py`, `logsum.py`, `sheets.py`,
  `clear_boxes.py`. Read `sweep.py` first: it rebuilds any case by id on a saved city, shoots it and reads it back.
- Sandbox cities, already copied into your tree's `Cities\`: `xsect_sandbox_clear.sc3` (flat, no water, no trees,
  $50M) and `xsect_sweep_built.sc3` (all 80 cases built with the 11-10d code).
- The lab build call can fail to answer the Frida client although the game applied it: the sweep driver reconnects.

## Streams and file ownership

| stream | owns (edit freely) | cases, in order |
|---|---|---|
| `diagfix` | `sc3netmod_dav.c`, `sc3netmod_dbv.c` | 1) rail / highway cut by a diagonal band: 68, 69, 72, 73, then 80 (on-ramp beside a DA). 2) diagonal x diagonal: 48, 49, 50, 52, 53, 54, 55. 3) orthogonal band meeting a diagonal: 15, 19, 34 (135-degree bends, DAVTOUCH), 16, 17, 18, 31, 32, 33, 43, 44 (DB lane gaps), 38, 40, 41, 42 (B lanes end in lone boxes / stem as stock), yellow 27, 28, 29, 39. 4) the two DA bands re-tiled on every later edit (cases 40 and 41, 438 log lines) |
| `orthfix` | `sc3netmod_bv.c`, `sc3netmod_avl.c`, `sc3netmod_avx.c` | yellow 26 (A x B corner), 37 (B x B corner), 62 (A narrowing into R), 63 (4 roads side by side), 67 (B x rail), 71 (B x highway) |

A change one stream needs in the other's file goes in its own clearly marked block with an off switch, and the
orchestrator is told before it is written (both streams merge into main).

## Rules for this round

- Rail and highway cells are never overwritten by an avenue or boulevard conversion. That is fix 1 of `diagfix`,
  reported as its own "fixed" milestone so it can merge and ship first.
- **Owner decision 2026-11-14: case 63 = option A, two avenues side by side** (existing pieces, AVL pairing rule).
- **Owner decision 2026-11-14: boulevard corners 26/37 = square kerbed corner box as shown** (BVCORNER default on).
- **Owner decision 2026-11-14: road / band meeting a diagonal at 135 degrees (15, 19, 34, 41) = taper + bend**
  (`verify/diagfix/mock/mock_a2_v2.png`). Family b) 48 = paved-box corner (`mock_b_v1_corner.png`), shown, no objection.
- **Owner decisions 2026-11-15:** case 34 keeps the ROUNDED outer kerb; boulevard x diagonal (38-44) = the three looks
  of `verify/orthfix/owner_shots/mockdiag_options.png`; families c) / d) (49 53 50 54 52 55) = the paved-box look of
  `verify/diagfix/mock/sheet_cd.png`.
- **New look = owner call.** A yellow case that needs a piece shape the game or our packages do not have yet: build
  a candidate (existing art or `netart.py` route, memory `project-net-art-kit`), shoot it, and send the picture to the
  orchestrator before making it the default. 63 (4 roads side by side) has no agreed look: propose options
  (two avenues, a wide boulevard, stay stock) with pictures, do not pick.
- Package art is gitignored and reaches a release only through `stage\src` (`netpack.py install`). List every art
  change under "files owned" with where it lives.
- Regression: after each milestone re-run the WHOLE sweep (all 80 cases) on `xsect_sandbox_clear.sc3` and diff the
  verdicts and the per-case piece ids against `verify/xsect/verdicts.json` / `final_cells.json`. A case green before
  must stay green. Write the new run to `verify/<stream>/` (never overwrite `verify/xsect/`), with a contact sheet of
  every case whose picture changed (before | after).
- Each fix in its own block or behind its own env/ini switch (`SC3NETMOD_<NAME>=0`), one start-log line.
- Light testing otherwise (memory feedback-light-testing): the sweep is the test.

## Ship checklist (orchestrator, before the next release)

Code merges land on main as they pass. Package art is gitignored, so `stage\src` is updated in ONE step at the end
of the round (back up `stage\src\mods\netmod` first, then `netpack.py install` each changed pack, then re-stage):
- [x] main 40107e1: diagfix DAVXNET (code only, no art)
- [x] main 51a4f76: orthfix BVXING + 22400 (code). Art to install: `avenue_ends` with `art/22400` (copy of 22001)
      and `ct_22400`, `boulevard` 0.4.0 (bvr_20769..20780 lanes, no art). Frozen packs: ask orthfix for the ship set.
- [x] main de0933e: orthfix BVCORNER (default on) + BVQUAD (63). Art: `boulevard_junctions` 0.2.0 with art
      22401..22420. FROZEN SHIP SET for all three orthfix packs: `dev/orthfix/ship/` + `SHIP.md` (install exits 1 on
      a style_mix report crash after writing, check the ledger, not rc).
- [x] main ba48e8d: diagfix DBVCAPCLEAN, DAVDBVWIN, DAVXAVL, DAVBVBEND, dbvlanes.py art-copy fix (code only).
- [ ] diagfix stale-art fix (pictures approved in m3 sheet, 16 17 18 green): `fix_dbv_art.py stage/src/mods/netmod/packs/diagonal_boulevard`
      then `netpack.py install` that pack into stage/src (the script only fixes the pack dir, the overlay needs the install): `diagonal_boulevard` art 21917 <- 20952, 21918 <- 21029, 21919 <- 21030
      (`verify/diagfix/fix_dbv_art.py`), approved, apply after its pictures.
- [x] main acd1938: orthfix BVDIAG rule part (38 39 40 convert up to the band, code only).
- [x] main 7d1df99: diagfix DAVBEND135 + DAVBENDSTUB (case 15, owner's taper + bend). Art: `diagonal_avenue` bend set
      22430..22441, durable copy `dev/diagfix/packs_src/diagonal_avenue` (KEEP file in dev/diagfix); the stale-art
      fix is already applied in `dev/diagfix/packs_src/diagonal_boulevard`. Each reinstall rebuilds the overlay (~25 min).
- Ids: orthfix 20769..20789, 22400..22429, 22470..22487 (39 box). diagfix 22430..22469, 22362..22399, 22488..22498, 22600..22699, 22700..22798. 22499 and 22799 taken (hwlanes / hwx_build).
  Curve SHAPE ids (global): orthfix 29000..29119, diagfix reserve 29120..29199. Builders already own 22800-22999,
  23000-23299, 23400-23420, 23600-23899, 23950, 24000-24999 (bvlanes), 25000-25499 (avdiag), 25500-25999 (avdiamond),
  26500-26999 (avends/bl), 28200-28599; 27xxx is scattered.
- [x] main 60311b0: diagfix DBVBEND135 (+ mirror, case 19, art 22442..22457 in dev/diagfix/packs_src/diagonal_boulevard)
      and DBVBROW (case 42).
- [x] main d7fcc10: orthfix 42/43/44 stems + BVBEND (41, OFF until diagfix's 41/45 bend sets).
- [x] main b0bc914: orthfix BVOBOX (39 box). Art: NEW package `boulevard_diagonal` (22470..22487), in
      `dev/orthfix/ship/` + SHIP.md (check: 2 `bvo` lines in its table).
- [x] main 380dd35: diagfix 7-8 (34 / 41 / 45 bend sets, 48 corner, 38 / 40 boxes). Art: `diagonal_avenue`
      22370..22387 + 22600..22661, `diagonal_boulevard` 22388..22399, in dev/diagfix/packs_src.
- [x] main a2e223b: orthfix BVBEND default on + the DAVBBEND guard (39 back to its box).
- [x] main 2b564ed (other round, issue #3): sc3simrun SANDBOX + GENTLE, both off by default, share 25. Code only.
- [x] main d4bfea9: orthfix DAVBVOUTER (39 diagonal-first). orthfix CLOSED, ship set kept (dev/orthfix/KEEP).
- [x] main c10785b: diagfix 10, DBVX c/d boxes (49 50 52 53 54 55, pieces 22721..22785) + DAVX_MAX 128.
      Art: `diagonal_boulevard` art 22700..22785 in dev/diagfix/packs_src. Open: 49 drawn DB first, 45 axis-1 mirror.
- [x] main b5b3c9a: diagfix 11 (45 axis-1 mirror). diagfix SHIP.md in dev/diagfix/packs_src.
- [x] INTEGRATION 2026-11-15: backup `stage/src_netmod_backup_20261115`; 11 netpack steps into stage/src (ledger 23
      packs: boulevard 0.4.0, boulevard_diagonal 0.1.0 new, diagonal_avenue 0.8.0, diagonal_boulevard 0.3.0, ...),
      all 8 table counts match; every install exits 1 from the `_print_report` style_mix crash AFTER writing (netpack
      bug, still to fix). `stage/bins_1115` = 12 DLLs built from main b5b3c9a (dev/integ1115) + main's lang tables.
      `stage/release` = 2026-11-15 (3,664 files; vs 11-10d: 117 changed, 14 added incl. sc3mods_patch.sh LF, 0 removed);
      old copy kept as `stage/release_1110d_old`. NOT deployed (LAN / GitHub need the owner's go + Jotti scan).
- [ ] Final sweep on fresh `dev/final1115` (from the new stage): 80 cases both orders, owner sheet of the 36 cases.
- [ ] whatever the rest of the round adds (corner boxes 22401.., diagonal shape families).
- [ ] `sc3mods_patch.sh` into the GitHub zip with LF (round 2026-11-14), new sc3simrun.dll (LVWRAP).
