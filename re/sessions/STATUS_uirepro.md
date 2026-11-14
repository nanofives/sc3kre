# STATUS uirepro (child of "SC3 Simtropolis feedback triage"), 2026-11-14

## goal
Repro StevieKam84's two reports on 11-10d: (a) two parallel orthogonal roads (avenue) draw nothing, diagonal OK;
(b) UI does not rescale on resize / Alt+Enter at 3440x1440.

## verdict
- (b) DOES NOT REPRODUCE with Auto: 2.4x at 3440x1440, 3.6x fullscreen, also with GOG DDrawCompat loaded. The player's
  picture = a saved Normal (`[hud] scale=0 ver=2`, log `HUDOPT> on: scale 0`, no `HUDSCALE>` line), or the SC3KU
  package (ships no sc3resize.dll).
- (a) DOES NOT REPRODUCE: z-axis and x-axis avenues, avenue + crossing road, diagonal avenue all convert and draw, with
  and without the community mods (102/102 cells identical, 0 refused, 0 reverted). Untested hypothesis: a missing or
  older `mods\netmod\overlay` than the DLL would leave netmod's piece ids (21700.., 20800..) without art.
- Details, log lines, questions for the player: `verify/uirepro/RESULTS.md`. No fix: nothing reproduced.

## built
Nothing. No source changes.

## proven game-side vs static only
Both parts game-side (frame dumps, sc3netmod / sc3resize log lines, piece snapshots). The overlay hypothesis is static only.

## blocked on
Nothing.

## files owned
- `verify/uirepro/RESULTS.md`
- `verify/uirepro/snapAB.json`, `snapA.json`, `snapD.json`, `snapC.json`
- `verify/uirepro/owner_shots/`: `b1_*`, `b2_*`, `b3_*` (12 PNG incl. `_small`), `a1_orth_avenues.png`,
  `a2_orth_avenue_crossing.png`, `a3_diag_avenue.png`, `a4_community_orth.png`, `a5_community_diag.png`
- `re/sessions/STATUS_uirepro.md`

## tree state (dev\uirepro, nothing to commit)
- `tree\Apps`: community DLLs SC3KCivicDeals.dll (Spanish texts), SC3KExtraCheats.dll, SC3KUApacheFlyover.dll added as
  own files, plus `.community-orig` backups. The script's `Copy-Item` re-wrote the three hard-linked
  `Res\Sprites\SC3KU_ApacheFlyover.*` with identical bytes (hash equal), so stage\release and the lxpatch/lvwrap trees are
  unchanged in content. Note for the script: `Copy-Item -Force` writes through hard links, unlike its own `Write-New`.
- DDrawCompat removed again, `inst\sc3resize.ini` absent (Auto). Logs kept in `inst\`: `sc3resize_b2.log`,
  `sc3resize_b3.log`, `sc3netmod_a_stock.log`, `sc3netmod.log` (community run).
- No game running.

## game-harness need
None now.

## asks of other sessions
streply: put the questions in RESULTS.md (package + date, `[hud]` ini section, `HUDSCALE>`/`HUDOPT>` lines, overlay
folder + `overlay:` / `avl:` lines, screenshot) into the reply.
