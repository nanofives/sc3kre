# Avenue program: integration on round/avenues (2026-10-18)

Branch `round/avenues` (worktree `Simcity_wt_avenues`): child/diagave + child/avx + child/boulevard + child/bigrbt
+ child/diagx + child/bvx + child/diagbv: the full first and second waves.
Streams and protocol: `re/sessions/CHILD_PROTOCOL_2026-10-17.md`; each stream's evidence in `verify/<stream>/RESULTS.md`.

## Merge notes
- The shared files (`sc3netmod.c`, `sc3netmod_rbt.c`, `netpack.py`, `netpack.schema.json`) conflict on every merge:
  each block adds a table-line skip, an `#include`, forward declarations, an `rb_file` dispatch, edit / load calls, an
  install gate term and reset terms. Resolution keeps every block.
- Trap found in the bigrbt merge: git auto-merged part of `rbt_install`'s gate, so hand-numbered conflict
  resolutions landed one block off. The result built, but a reset line ran after hooking and switched off DAV's
  middle pieces, AVX and RBT9 (log: `diagonal avenues on (inner 0 0 0)`, no `rbt9:` / `avx: ... on` lines). Fixed by
  rewriting the install tail; a check that every branch's added hook lines survive in the merged files now runs
  after each merge.

## Combined game check (Simcity_stock_diagave, all five packages installed)

| Check | Result |
|---|---|
| Install diagonal_avenue, avenue_junctions, boulevard, big_roundabout, avenue_markings | TrBlkAtt.IXF grew: 1,069 slots, first payload 0xa004 (ixf_insert growth, f92c5c9) |
| DLL start | `avx: avenue junctions on`, `rbt9: automatic 3x3 roundabouts on`, `diagonal avenues on (inner 20500 ...)`, boulevard tables read |
| 3x3 block with avenue arms W and N, a road E, two roads S | `rbt9: edit: (107,97) -> 3x3 roundabout, 4 avenue arm cell(s), 9 cell(s) written` |
| Boulevard along x with a crossing road | `bv: edit: boulevard axis 0, columns 11..23 at row 47, 39 cell(s), 30 written` |
| Save, reload | 48 variant tiles written as base / all 48 restored; every block's load pass wrote 0 |
| Exceptions | 0 in both games |

## After merging child/diagx (0bed815)

Only `netpack.py` and the schema conflicted (diagx rewrote the schema with LF line ends, so the whole file
conflicted; its only change was the `crossing` property, added to the integration file). The crossing art needs
`diagave.py xbuild .` after `build .`; `diagave.py xcheck`: 0 failures.

| Check | Result |
|---|---|
| Install all five packages | TrBlkAtt 1,289 slots, first payload 0xa004 |
| DLL start | avx on, rbt9 on, diagonal avenues on (inner 20500) |
| Two diagonal avenues crossing (axis 0 and axis 1 bands) | `band axis 0 ... 1 crossing(s), 35 written`, `band axis 1 ... 1 crossing(s), 33 written`; dashes, median trees and crosswalks on all four arms (`int3_xx_z4.png`) |
| Exceptions | 0 |

## After merging child/bvx (a30470e)

Conflicts only on the shared hook lines; bvx runs inside BV, so the install gate needed no new term. Survival check:
all added hook lines present (the BV rule lines bvx rewrote are its newer version).

| Check | Result |
|---|---|
| Install six packages (+ boulevard_junctions) | validates, installs |
| DLL start | bvx box pieces read; avx, rbt9, DAV on |
| Boulevard along x crossed by an avenue along z | `bv: edit: ... 43 cell(s), 34 written`; paved box, noses, dashes (`integration_3_bvx.png`) |
| Exceptions | 0 |

Look difference to settle with the owner: avx boxes use a mirror fill of 43 (faint crease at zoom 4), bvx boxes a
per-pixel palette of 43's asphalt (no crease, grainier than the road).

## After merging child/diagbv (21f51a0)

29 conflict blocks over 8 files, three of them real logic clashes:
- DAV (C and twin): diagx's crossing exclusions and diagbv's claimed-cell exclusions combined in the side,
  isolation and write checks.
- BV (C and twin): both branches used end type 4 (bvx: T into an avenue / boulevard; diagbv: bend into a diagonal
  boulevard). The DBV bend is 5 now; the T keeps 4 and its median nose.
- diagave.py: diagx split the band search into two axis loops; diagbv's per-axis claimed set was only defined in the
  first, so axis 0 used axis 1's set and 4 narrowing cases failed `diagbv.py check`. Defined in both: 0 off.

| Check | Result |
|---|---|
| `diagbv.py check` / `diagave.py xcheck` | 0 off (70 footprints) / 0 failures |
| Seven packages validate and install | yes |
| DLL start | avx on, rbt9 on, dbv on, diagonal avenues on |
| Three equal diagonal drags | `dbv: edit: diagonal boulevard axis 0, 11 row(s) ..., 47 cell(s), 47 written` (`integration_4_diagbv.png`) |
| Exceptions | 0 |

Not seen in game on the merged build: the narrowing of a diagonal boulevard into a diagonal avenue (offline only on the
stream's branch too; a test drag landed off-target after a camera error and the rule rightly left the shape alone).
