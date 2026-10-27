# artrecover: netmod package art rebuilt from the shipped overlay (2026-10-27)

## Verdict

All 18 shipped packages rebuilt. A real `netpack.py install` from the recovered sources reproduces the shipped
`mods\netmod\overlay` + `tables` **byte for byte: 113 of 113 files identical** (sha256, `files_113.sha256`). No
painter re-render was needed. No game run was needed either, because the byte check passed.

## What was lost and what was installed

The cleanup removed the gitignored `art/<id>/` png_dirs (+ `anchors.json`) of every package and the stage ledger.
Manifests, lanes / paint / recipe json and painter scripts are tracked and were intact.

Installed set, found from the overlay: the 17 packages with a `tables\*.txt`, plus `avenue_markings`. That package
only reskins 11204, so it writes no table, and it shows up as the changed 11204 frame table in the overlay's
`CSATTRIB.IXF`. No `example_*` package is installed. `example_bridge_style`, `example_template_rotonda` and
`example_roundabout_lamps` reuse ids of shipped packages, so they cannot be installed alongside them. Install order does
not matter: netpack merges in package name order every time (selftest U3).

## Why it is recoverable (netpack.py `compile_art` + `merge`)

- Each PNG becomes one pixel record. `image_to_surface` is the exact inverse of `span_to_image` (`png_roundtrip`), and
  the encoder + `qfs_encode.compress_stream(quick=1)` are deterministic.
- The variant's frame table (`CSAttrib_Korea.IXF`, or `CSATTRIB.IXF` for a reskin) holds `(group, piece << 16 | j)` for
  each frame position. `j` indexes the package's record list (the source frame's distinct records in first-use order,
  then any split records), so the table gives each position's pixel + anchor.
- A PNG is written only where the record differs from the source frame. anchors.json gets an entry only where the size
  or anchor differs. Every anchor had the `{L, T, w-L, h-T}` form anchors.json expresses.

## Per package (`recover_write.log`)

| package | items | png_dirs | PNG files | anchors entries | split records |
|---|---:|---:|---:|---:|---:|
| avenue_junctions | 79 (3 stock art) | 76 | 1,430 | 0 | 0 |
| avenue_lanes | 19 (8 stock art) | 10 | 184 | 158 | 0 |
| avenue_markings (reskin 11204) | 1 | 1 | 12 | 0 | 0 |
| big_roundabout | 27 | 27 | 540 | 0 | 0 |
| boulevard | 57 | 57 | 1,320 | 1,116 | 0 |
| boulevard_junctions | 57 | 57 | 1,128 | 0 | 0 |
| boulevard_slopes | 12 | 12 | 240 | 80 | 0 |
| diagonal_avenue | 100 (3 stock art) | 83 | 1,680 | 1,492 | 0 |
| diagonal_boulevard | 134 | 134 | 3,020 | 2,122 | 0 |
| highway_ask | texts only, no art | - | - | - | - |
| highway_avenue | 24 | 24 | 480 | 480 | 0 |
| highway_core | 2 | 2 | 40 | 40 | 0 |
| highway_dd_cloverleaf | 120 | 120 | 2,400 | 2,400 | 0 |
| highway_diagonal_cloverleaf | 252 | 252 | 5,040 | 5,040 | 0 |
| hwt_trumpet | 114 | 114 | 2,280 | 2,280 | 0 |
| hwx_cloverleaf | 52 | 52 | 1,040 | 1,040 | 0 |
| road_slope_ends | 24 | 24 | 480 | 477 | 0 |
| roundabout | 2 (recipe, built at install) | - | - | - | - |

Total: 21,314 PNG files in 1,045 png_dirs (diagonal_avenue and avenue_lanes share some dirs between variants, so
21,646 frame PNGs land in 21,314 files), 818 anchors.json files, 85 MB.

## Checks

1. **Per frame, after write** (`netpack_recover.py --write`): every item compiled again from its written png_dir with
   `netpack.compile_art`, and each position's ordinal, pixel record and anchor record compared with the shipped ones.
   0 differences across 1,060 checked items. The 14 stock-art items were confirmed equal to the source frames, and the 2
   recipe items are covered by step 2.
2. **Full merge** (`netpack_recover.py --compare`, which calls `netpack.merge` the same way install does): 113 of 113
   files identical (`compare.log`, one `[N/113] file STATUS` line each). This covers the roundabout recipe art (netart,
   deterministic), lanes / VPATHATT, rules, texts and SYS.PAK.
3. **Real install** into `dev\artrecover\tree`: I removed the tree's old `mods\netmod` (plain directories of hard links,
   so `stage\src` was unchanged: still 113 files, same hashes). Then I seeded the ledger with 17 packages (sources copied
   to `packs\`, the same entries `install` writes) and ran the real CLI
   `netpack.py install examples/roundabout --tree dev/artrecover/tree`. That one install merges all 18 packages and
   writes every output + the ledger. The result is the same end state as 18 sequential installs, because each install
   re-merges every installed package. One merge takes 6 min 38 s, so 18 sequential installs would cost about 1 to 2 h.
   Result: `sha256` of the 113 files equals the shipped list exactly.

## The stage source (for the orchestrator to move)

`MAIN\dev\artrecover\tree\mods\netmod` now holds `ledger.json` (overlay mode, 18 packs, 96 files),
`packs\<name>\` (23,028 files, 85 MB, the recovered art included), `overlay\` and `tables\`. That is exactly what
`stage_lan_release.py --game` expects from a stage source. I did not touch `MAIN\stage\src` or `MAIN\stage\release`.
To adopt: replace `stage\src\mods\netmod` with this folder. `sc3dev remove artrecover` refuses while the tree holds a
ledger, so the copy is protected until then. Pristine copy of the shipped files: `dev\artrecover\shipped\`.

## Keeping it from recurring (proposal, not done)

The brief suggested committing package art. **The publish policy does not allow it.** Memory
`project-sc3kre-publish-policy` makes the 2026-10-23 netmod exception for release assets only ("never into git").
`sc3kre` is public, and the PNGs are painted over Maxis frames. Options, in my order of preference:

1. **The shipped overlay is the backup.** Every release asset carries `mods\netmod\overlay` + `tables`, and
   `netpack_recover.py` turns it back into sources with a byte-identical install (shown here). Commit the tool and add a
   line to `NETPACK.md` 1 and CHILD_PROTOCOL section 5. Cost: none. Limit: it only covers art that has shipped.
2. **Snapshot `stage\src\mods\netmod\packs` + `ledger.json` onto the LAN server** (mariano-server) at every LAN publish,
   next to the release, so the stage source survives the loss of this PC.
3. A **private** git repo (not sc3kre) for `re/tools/netmod/examples/*/art`, if version history of the art is wanted.
   85 MB of PNGs, so LFS or a separate bare repo on mariano-server.

## Files

- New, to commit: `re/tools/netmod/netpack_recover.py` (worktree `dev\artrecover\wt`, branch `child/artrecover`).
- Gitignored, not for commit: the recovered `re/tools/netmod/examples/<pkg>/art/**` in that worktree (a second copy is
  in the tree's `packs\`).
- Logs here (ignored): `recover_write.log`, `compare.log`, `files_113.sha256`.
