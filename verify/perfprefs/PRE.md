# perfprefs: FPS counter and profiler toggles in Preferencias (pre-registration, 2026-10-12)

Owner: "quiero un toggle en preferencias para desactivar el FPS counter y el profiler".

## What is on screen today (release 2026-10-12 defaults, perf.ini overlay=1 busy=1)

Only sc3perf draws text (no TextOut/DrawText in sc3resize, sc3bigcity, sc3overscroll, sc3simrun):
1. FPS line, top-left, yellow on black (`draw_overlay`, gated by `g_overlay`, perf.ini `overlay`).
2. Red SIM BUSY / DATE STOPPED line plus up to two dark-red call-chain lines under it (`busy_thread` text,
   drawn whenever the text is non-empty, perf.ini `busy` turns the whole detector off at startup).
The sampling profiler (`profile=1`) writes files only and draws nothing.

## Design

- Two checkboxes in the left half of "Opciones generales", row under "Ir a los desastres automatico" (local y 400):
  "Ver FPS" (x 18) and "Ver perfilador" (x 120). Ids 0x02F95B48 / 0x02F95B49, above 0x02F95B11 so the dialog's
  command handler SIMUI FUN_10058f14 only returns for them.
- Read back on close next to HUDOPT. OK applies, any other close (Esc, close box) keeps the old values.
- sc3perf exports `sc3perf_show_get()` / `sc3perf_show_set(bits)`. sc3resize resolves them with GetProcAddress when the
  dialog is built. No sc3perf, or an sc3perf without the export: no checkboxes.
- The setter changes the flags the overlay reads every final present, so the change shows on the next frame.
- Persistence: perf.ini (sc3perf's own file): `overlay` (existing key) and new `busy_show` (default 1).
  `busy` stays the detector switch (hook, stall log); `busy_show` only hides the drawing.
  SC3PERF_OVERLAY / SC3PERF_BUSY_SHOW env still override at startup.
- Defaults: unchanged release behaviour (both shown).
- Opt-outs: SC3RESIZE_PERFPREFS=0 (no checkboxes), and SC3RESIZE_HUDOPT=0 removes them too (same detours).

## Tests and expected results (instance re/harness/inst_perfprefs, 256 city, windowed)

| # | step | expected | fail if |
|---|------|----------|---------|
| T1 | open Preferencias in a city | both boxes checked, no overlap with "Suavizado" or game rows | box missing, overlap, unchecked |
| T2 | uncheck "Ver FPS", OK | FPS line gone on the next grab, game city intact under it; log `PERFPREFS> OK: fps 0` | line still drawn |
| T3 | reopen, check it, press Esc | box shows checked while open, after Esc FPS still off | Esc applied |
| T4 | red line visible (A, a modal that holds the clock, or a stall), uncheck "Ver perfilador", OK, same trigger again (B) | A shows the red line, B does not, log still has BUSY> lines in B | B draws the line |
| T5 | restart the instance | perf.ini overlay=0 busy_show=0, no FPS line, dialog shows both unchecked | values lost |
| T6 | main menu Preferencias | same two boxes, saved state | missing or wrong state |
| T7 | check both, OK | both back at once | |
| T8 | SC3RESIZE_PERFPREFS=0 | no boxes, HUDOPT controls still there | |
| T9 | stock install, final check | boxes present, toggles work | |
