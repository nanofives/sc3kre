# Round 2026-11-15b: owner review of the final junction sheets

Orchestrator: "SC3 Simtropolis feedback triage (Wine patch, land value 255, avenues, UI rescale)".
Rules: `re/sessions/CHILD_PROTOCOL.md`. Base: main `4b761ac`, stage/release 2026-11-15 (NOT released; this round
blocks the release). The owner reviewed `verify/final1115/owner_shots/sheet_final_1..4.png` (before = xsect, after =
the staged build). His words are quoted verbatim; where a request is open to more than one reading, build 2 candidates
(offline mock is fine) and send pictures before making one the default.

## Owner feedback (Mariano, 2026-11-15), per case

| case | owner | stream |
|---|---|---|
| 15_RxDA_L | "is not ok, road doesn't look connected, the end of the diagonal road should be stopping until the very end of the rectal [straight] segment" | diagfix |
| 19_RxDB_L | "is not ok, previously it was better but you only needed to fix the side where it was connecting to the other road" = keep the ORIGINAL boulevard end (xsect before), change only the side where the road joins | diagfix |
| 50, 52, 54, 55 | "on the segment that's horizontal on the upper road there's a missing road" (the upper carriageway of the arm leaving the box to the right: a cell is missing next to the box) | diagfix |
| 29, 31, 32, 33 (yellow) | "the yellow ones have to be revamped": the avenue arm must convert properly, no two-way stub / stock box | orthfix (AVL / BV), with diagfix for any DAV/DBV cell |
| 80 (yellow) | same: on-ramp beside a diagonal avenue. Stock limit today (the On-ramp tool needs a straight road end): find out what it takes first, report before building | diagfix |
| 43 (red) | "red needs to be fixed": boulevard through + diagonal boulevard stem: the 39-style box, for a DB | orthfix |
| 67_Bxrail_cross | "is not fine because the crossing is not following the 3 lane layout" = level-crossing art with the boulevard's 3+3 lanes and median, not the stock 2-lane crossing | orthfix |
| 71_Bxhwy_cross | "is not following the three lanes (there shouldn't be 3 tunnels below the highway" = ONE underpass spanning the boulevard, not one tunnel per road | orthfix |
| 68_DAxrail_cross, 69_DBxrail_cross | "is not following the two lane diagonal layout, there has to be a special texture there that follows properly the diagonal" = diagonal level-crossing art following the DA / DB lanes | diagxnet |
| 72_DAxhwy_cross (and 73) | "there should be a special texture for underpass diagonal" = a diagonal underpass under the highway | diagxnet |

**Owner decisions 2026-11-15: 67 / 71 = the looks of `verify/orthfix/owner_shots/mock_67_71_art.png`; 66 / 70 get the
same treatment (avenue crossing follows its 2+2 lanes, one underpass), orthfix.**

**Owner decisions 2026-11-15: 68 / 69 / 72 / 73 = `verify/diagxnet/owner_shots/mock_sheet_v1.png`, stop lines kept.**

**Owner review 2026-11-16 of the mocks / in-game shots:** 80 "not looking right, ramp is only one way, underneath the
highway there's only 2 tiles needed, and the road is not looking like an avenue"; 15 "both options are wrong, but option A
is better, you still need to fix the median and the road lines starting way further than they should"; 19 "almost
perfect, there's a minor glitch on the end of the avenue and the beginning of the 1 tile road". All three to diagfix.

**Owner decision 2026-11-16: case 80 diamond = "Yes, build it"** (`verify/diagfix/owner_shots/c80_diamond.jpg`, DAVRAMPJ).

**Owner answers 2026-11-16 for 80:** "Underpass too big" (make the diagonal underpass smaller; diagfix may edit
diagxnet's xnet builders) and "Yes, diamond" (entry + exit ramps on each side, median closed at the joints).

**Owner decision 2026-11-16: rail / highway drawn ACROSS an existing diagonal = "Fix it"** (diagxnet; today the line is
cut, as stock does over a plain diagonal road).

**Owner decision 2026-11-16: case 80 joint = "Dedicated joint"** (not the generic DAV T box; mock first).

**Owner decision 2026-11-15: case 80 = "Full build now"** (verify/diagfix/REPORT_80_onramp.md plan, ~3 days, joint
art, regression incl. 78/79 and shipped on-ramp strips).

Not mentioned by the owner (keep as they are, do not regress): every other green case, 66 (A x rail), 70 (A x highway).
Check 66 / 70 once against the new 67 / 71 looks and say if they now look inconsistent (owner call, do not change).

Also still open from before: 49 drawn diagonal boulevard first is timing-sensitive (diagfix).

## Merged so far (main)

- 78b959e diagfix 12 (DBVXFILL, 50 52 54 55). 854be1a orthfix 11-15b (66 67 70 71 art, 43 box, 29-33 boxes; 31-33
  need arms of 10+ cells). 35eb5ed diagxnet (68 69 72 73 crossings / underpasses, package diagonal_xnet 30000..30069).
  47dab82 diagxnet DAVXHEAL (rail / highway drawn across an existing diagonal). diagxnet CLOSED, ship set kept
  (dev/diagxnet/ship + SHIP.md, KEEP). Merged sc3netmod compiles.
- orthfix CLOSED 2026-11-16 (worktree removed; dev/orthfix kept by KEEP: the only copy of its ship art in
  dev/orthfix/ship + SHIP.md; after the stage/src install delete KEEP and `sc3dev remove orthfix`).
- 8e8a6b3 diagfix 14 (52 / 55 corner boxes as T, no empty-art cells; dbvx_build guard).
- dc06270 diagfix 15 (case 19 glitch), 7d8cff7 diagfix 16 (case 15 A fixed), d3ea8ce diagfix 17 (case 80: DAVRAMP +
  DAVRAMPJ diamond, pieces 30400..30403, shapes 29120..29129). Merged sc3netmod compiles.
- INSTALL ORDER for the next stage (diagfix): the new sc3netmod.dll + netpack.py / schema from main BEFORE reinstalling
  diagonal_avenue (16 davxr lines expected); diagonal_xnet 0.1.1 (dev/diagxnet/ship) must be installed or every
  build shows the stock underpass.
- Owner 2026-11-16: underpass size "Yes, that's right" (diagonal_xnet 0.1.1 as is). Integration waits for 49:
  "Fix 49 first" (49 drawn DB first must hold over 10+ fresh reverse builds). Then integration again
  (orthfix ship 11-15b: boulevard 0.5.0, boulevard_diagonal 0.2.0, avenue_diagonal_t, avenue_dbv_t; diagfix
  diagonal_boulevard update; diagxnet diagonal_xnet), re-stage, final check, owner sheet.

## Integration 2026-11-17

- b6281ac diagfix 18 (DBVREPASS, case 49 reverse order: 16 / 16).
- stage/src: backup `stage/src_netmod_backup_20261117`; 11 netpack steps (boulevard 0.5.0, boulevard_diagonal 0.2.0,
  diagonal_avenue, diagonal_boulevard, avenue_diagonal_t, avenue_dbv_t, diagonal_xnet 0.1.1), ledger 26 packs, all 12
  SHIP table counts match. `stage/bins_1117` = DLLs from main b6281ac (dev/integ1117).
- `stage/release` = 2026-11-17 (3,679 files; vs 11-15: 117 changed, 15 added, 0 removed); old copy
  `stage/release_1115_old`. NOT deployed.
- Final check on fresh `dev/final1117` by diagfix: sweep 0 off m21, reverse orders hold, diamond OK; sheet 39 green,
  3 amber (31 32 33 short arms + 32 wedge), 0 red (`verify/final1117`, main 532e65e).
- Owner 2026-11-17: "Fix 31-33 first" -> orthfix in `dev/shortarm`, merged 73826b8 (avenue_dbv_t 0.2.0).
- stage/src: backup `stage/src_netmod_backup_20261117b`, avenue_dbv_t 0.1.0 -> 0.2.0 (32 dbvx / 40 avlj).
  `stage/release` = 2026-11-17b (3,680 files; vs 11-17: 94 changed, 1 added, all mods/netmod; DLLs = bins_1117);
  old copy `stage/release_1117_old`. NOT deployed.
- Showcase gallery child (`dev/showcase`, brief ROUND_2026-11-17_showcase.md) shoots every junction family on this
  build; its ISSUES.md doubles as a last visual check before release.

## File / block ownership

| stream | owns |
|---|---|
| diagfix | `sc3netmod_dav.c`, `sc3netmod_dbv.c` EXCEPT the DAVXNET block; packages diagonal_avenue, diagonal_boulevard |
| orthfix | `sc3netmod_bv.c`, `sc3netmod_avl.c`, `sc3netmod_avx.c`, its two marked blocks in dav.c (DAVBBEND guard, DAVBVOUTER); packages boulevard, boulevard_junctions, boulevard_diagonal, avenue_ends |
| diagxnet | the DAVXNET block in dav.c / dbv.c (and a new block of its own if needed), new package(s) for diagonal rail / underpass art |

A change in another stream's file or block: ask the orchestrator first.
Granted 2026-11-15: orthfix builds the avenue T / crossing box for 29 31 32 33 in its own marked blocks DAVJAV / DBVJAV
inside dav.c / dbv.c (cause: an avenue meeting a band at 45 degrees ends on a plain band edge on one half and on the
band's single-road T on the other, so AVL refuses; the fix is an avenue box with avlj joins, like 40 / 44's BV boxes).

## Ids (piece ids are 16-bit; scan clean 2026-11-15 in re/tools/netmod, re/harness/src, stage/src, stage/release)

- diagfix: 22786..22798 (left), plus 30400..30599
- orthfix: 30200..30399
- diagxnet: 30000..30199
- Curve SHAPE ids: orthfix 29000..29119 + 29200..29299, diagfix 29120..29199; ask for more. 29504 / 29541 taken.
- orthfix pieces: 30200..30208 = 67/71 art twins, 30209..30232 = 43 DB opening box.

## Rules

Same as round 2026-11-14b: one commit per fix after a full 80-case regression in BOTH draw orders for the cases that
have reverse builds (order_case.py / order_cmp.py / rev_cases.py), on a tree that has EVERY current pack (copy
`stage/release`-equivalent: install the ship sets or build the tree fresh from stage after main merges). Pictures to the
orchestrator for every new look before it becomes the default. Each fix behind its own off switch. Light testing
otherwise. Package art is gitignored: keep a ship dir + SHIP.md per stream.
