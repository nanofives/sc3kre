# STATUS ladder (child of "SC3: owner bugs 10-23", 2026-10-25)

Owner request: "update the confidence ladder with all the things you have developed".
Worktree `Simcity_wt_ladder` (branch child/ladder from main c9602a3). No game launches.

## State: DONE, applied (Milestone 2)

- Orchestrator go: apply `ladder_batch_all.tsv`, the primary and secondary sets, 336 rows, with `--legacy-names`.
- Applied: `tracker.py batch` reported `APPLIED 336 record(s); verified blast radius = 336`.
- Follow-up batch: `ladder_batch_fix_subsystem.tsv` (3 rows) set `font-render` on three of those C1 rows. Blast radius 3,
  same rows, so the total stays 336.
- `git diff -U0 functions.csv` vs c9602a3: 336 lines out, 336 in. Sample `tracker get` rows were checked.
- Whole file, before -> after:

  | level | before | after |
  |---|---|---|
  | C0 | 38,439 | 38,150 |
  | C1 | 5,088 | 5,080 |
  | C2 | 1,833 | 2,003 |
  | C3 | 298 | 421 |
  | C4 | 11 | 15 |

- Write-up: `verify/ladder/RESULTS.md` (rules, per-module counts, every changed row).

## Files to commit (worktree `Simcity_wt_ladder`)
- `functions.csv`
- `verify/ladder/RESULTS.md` (not ignored)
- force-add (`verify/*/*` is denied in .gitignore):
  - `verify/ladder/ladder_batch.tsv`
  - `verify/ladder/ladder_batch_secondary.tsv`
  - `verify/ladder/ladder_batch_all.tsv`
  - `verify/ladder/ladder_batch_fix_subsystem.tsv`
  - `verify/ladder/ladder_plan.tsv`
  - `verify/ladder/counts_before.json`
  - `verify/ladder/counts_after.json`
  - `verify/ladder/tools/` (`refbodies.py`, `gen.py`, `rows_named.py`, `rows_secondary.py`, `counts.py`, `bodies.json`,
    `secondary_cites.tsv`)
- MAIN `re/sessions/STATUS_ladder.md`
- Do NOT commit: worktree `functions.csv.bak_tracker` (the tracker's backup, ignored).

## Merge note
`functions.csv` is spliced per record, and only these 336 records differ from c9602a3. If main's `functions.csv` changed
in the meantime, re-apply `ladder_batch_all.tsv` and then `ladder_batch_fix_subsystem.tsv` on main with
`tracker.py batch --legacy-names --apply` instead of merging the CSV by hand.
