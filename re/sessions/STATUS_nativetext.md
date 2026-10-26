# STATUS nativetext (child of "SC3: owner bugs 10-23"), 2026-10-26

State: round 2 done ("fixed"). Owner picked look B. B is the default, letter spacing is fixed (sub-pixel placement), and
the RCI bars are redrawn at the factor.

- Worktree `Simcity_wt_nativetext`, branch `child/nativetext` from main `742fe1f`. Nothing committed (claude2 policy).
- Test tree `Simcity_stock_nativetext`, instance `re\harness\inst_nativetext` (all 7 mods + `Apps\version.dll` built
  from the worktree). No game left running.
- Results and pictures: `MAIN\verify\nativetext\RESULTS.md` (round 2 section), `MAIN\verify\nativetext\owner_shots\`
  (00..10 round 1, looks A/B; 11..21 round 2, spacing and RCI).

## Files to commit (worktree paths)

| file | change |
|---|---|
| `re/harness/src/sc3resize_ntext.c` | NEW: the NATIVETEXT block (glyph detour, records, Blt propagation incl. self-Blt scroll, compose, looks A/B, sub-pixel look B masks, RCI fill records, cache, census, spacing check) |
| `re/harness/src/sc3resize.c` | hook-up only: `#include` before `rz_hs_pre`, `nt_install()` after `patch_shareread`, `nt_blt(..., fx)` first line of `rz_blt_hook_inner`, `nt_hud()` after `mn_compose`, `nt_dlg()` after `vd_compose`, 7 env lines, 1 FLAGS line |
| `re/analysis/HUD_SCALE.md` | section "Text drawn at the factor" (mechanism, spacing, RCI) |
| `functions.csv` | 6 GZServiceD font rows to C2 (0x100072e2, 0x1000736f, 0x10007477, 0x100070aa, 0x10007ce5, 0x10007d9f) |

`sc3resize_ntext.c` is new under the ignored `/re/*` rule (.gitignore:62), like the other tracked sources there. It
needs `git add -f re/harness/src/sc3resize_ntext.c`, and the build fails without it (sc3resize.c #includes it).
`functions.csv.bak_tracker` (tracker.py backup in the worktree root) is ignored; leave it out.

Merge note: other children (vdscroll, zoomband) edit sc3resize.c. This change touches it only at the hook-up points
and the env block.

## Switches

`SC3RESIZE_NATIVETEXT` 0 off, 1 look A (TrueType), 2 look B (default). `_PHASE=0` old rounded placement (control).
`_RCI=0` RCI bars resampled as before. `_FACE=<face>` (look A). `_LOG=1` glyph census every 10 s, `=2` also cut-glyph
diag. `_DUMP=<abs prefix>` font sheets. `_CTL=<file>` live switch: first digit look, second digit phase (diag).

## Measured (round 2)

Spacing error between neighbouring letters vs native x factor (centroids), ticker scrolling:
- 2.252x, rounded: 0.31 to 0.34 px mean, 1.0 px max, 20 to 23% of pairs > 0.5 px.
- 2.252x, sub-pixel: 0.034 px mean, 0.17 px max, 0 pairs > 0.5 px.
- 3.307x with Reunirse: 0.055 px mean, 0.35 px max, 0 pairs > 0.5 px.
RESULTS.md has the ink-gap measure and the costs.

## Needs owner

1. Look at sheets 11..21 (spacing, RCI, scrolling ticker).
2. Optional call: at 3.3x the thin strokes of the Comic-style title font are a little uneven in look B (edge
   sharpening, not spacing). A lower sharpening gain for the anti-aliased fonts would soften it.
3. Hand test with a real cursor (hover tooltips, budget, query dialog): not run here (posted input only).

## Open items

- Main menu text (MENUSCALE) is not covered.
- Wall-clock costs are noisy (other children's games on this PC). Thread cycles are the stable number.
