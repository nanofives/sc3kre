# STATUS nativetext (child of "SC3: owner bugs 10-23"), 2026-10-26

State: round 3 done ("fixed"). Owner report "letters flicker, their sharpness changes constantly" (look B, 10-26b):
cause found and fixed, measured before/after in the same tree.

- Worktree `Simcity_wt_nativetext`, branch `child/nativetext`, fast-forwarded to main `0284ba7` by the orchestrator, then the
  round 3 edits on top. Nothing committed (claude2 policy).
- Test tree `Simcity_stock_nativetext`: instance `re\harness\inst_nativetext` (all 7 mods from the worktree, sc3resize with
  the fix) and `re\harness\inst_before` (same mods, sc3resize without the fix, for the A/B). No game left running, harness
  claim released.
- Results and pictures: `MAIN\verify\nativetext\RESULTS.md` (section "Round 3"), `owner_shots\22_flicker_frames_before_after.png`,
  `owner_shots\23_flicker_line_x3.png`.

## Round 3 in short

The glyph detour (`nt_add`) never set the record's `kind`, and record slots are reused. After RCI bar fills had gone
through a surface's records, new glyph records inherited `kind` 1, were checked as fills, failed and stayed resampled, a
different set of letters each time the game redrew the text (every frame with the sim running: the advisor portrait
animates). Fix: `memset` the record before filling it.

Advisor text at 2560x1351, sim running 3 min, 18 10-s windows each:
- before: 17.7% of glyph-frames changed on screen with their native cell unchanged (231,869 sharp <-> resampled flips),
  3,962 of 4,140 dialog frames changed, 11,000 px per frame;
- after: 2 of 2,987,939 glyph-frames, 0 flips, 0 of 6,333 dialog frames.
- NATIVETEXT cost fell from 12.3 to 13.7 ms to 4.1 to 4.6 ms per frame (rejected glyphs had made their groups miss the cache).

## Files to commit (worktree paths)

| file | change |
|---|---|
| `re/harness/src/sc3resize_ntext.c` | the fix (record cleared in `nt_add`); diag `SC3RESIZE_NATIVETEXT_FLICK=1|2` (per-glyph frame-to-frame stability, report line every 10 s, per-glyph and per-dialog log lines at 2); per-record `own` / `why` arrays used by it |
| `re/harness/src/sc3resize.c` | `SC3RESIZE_NATIVETEXT_FLICK` env line; FRAMEDUMP burst: the req file takes `<tag> <N> [x0 y0 x1 y1]` for N consecutive presents, optionally cropped (single-frame requests unchanged) |
| `re/analysis/HUD_SCALE.md` | "Text drawn at the factor": the flicker cause and fix |

Round 1/2 files are already on main (10-26b).

## Switches

`SC3RESIZE_NATIVETEXT` 0 off, 1 look A, 2 look B (default). `_PHASE=0` rounded placement. `_RCI=0` RCI bars resampled.
`_FACE`, `_LOG=1|2`, `_DUMP`, `_CTL` as before. NEW `_FLICK=1|2` (diag).

## Needs owner

1. Look at 22 and 23, then the game itself with the sim running over an advisor text: letters should hold still.
2. Still open from round 2: hand test with a real cursor (hover tooltips, budget, query dialog); optional lower sharpening
   gain for the thin Comic-style title strokes at 3.3x.

## Open items

- Main menu text (MENUSCALE) is not covered.
