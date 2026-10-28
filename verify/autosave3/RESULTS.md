# RESULTS - autosave3 (2026-10-28): autosave load crash + three autosave files

Child of "SC3 mods page layout + autosave rotation + load crash". Worktree `dev/autosave3/wt` (branch
`child/autosave3`, from main 5748523), tree `dev/autosave3/tree` (10-28 base). One source file changed:
`re/harness/src/sc3autosave.c`. Posted input only, frames via `SC3RESIZE_FRAMEDUMP`, no real mouse or foreground.

## A. "al cargar un autosave el juego crashea": not reproduced

8 loads of an autosave file, all alive, no autosave-side fault:

| # | path | file | result |
|---|---|---|---|
| 1 | `-City` at start | Frankfurt autosave1 (saved paused) | alive |
| 2 | in-game Load City | Frankfurt autosave1 | alive |
| 3 | in-game Load City | Frankfurt autosave1, saved with sim running, over the file the city came from | alive |
| 4 | in-game Load City, a save due during the load | Frankfurt autosave2 | alive |
| 5 | in-game Load City, a save due | Europolis 1024 autosave1 (6.9 MB) | alive, defect 1 |
| 6 | main menu Load City | Frankfurt autosave1 | alive |
| 7 | `-Stock` (no mods) `-City` | Frankfurt autosave1 | alive 40 s: the stock game loads the file |
| 8 | in-game Load City, `SC3AUTOSAVE_DIAG=1` | Europolis 1024 autosave1 | alive, diag below |

VEH lines seen: the benign start-up `0xC0000096 @ SC3U+0x84122`, and in run 5 first-chance `0xC0000005 @
KERNEL32+0x1CA9E` reading 0x000000FF from sc3resize.dll+0x331BC (a guarded read, handled, not autosave code).
LIVING-PC's Application log has no SC3U crash on 2026-10-28, so the owner's crash was on another PC. That PC's
`Apps\sc3autosave.log` and `Apps\sc3resize.log` (VEH FAULT lines) would show where it died.

So the file content, the ".autosave1" name and our hooks during a load are cleared on this PC for these cases.
Not covered: the owner's own city (Big One sized saves, `BigOne_owner.autosave1.sc3` from the 10-28 release check
loaded fine there), a crash some time after the load.

### Owner repro target (MARIANO-PC: Big One, bigcity.ini size=1024 selected=1, main menu, "crashed right away")
Owner files pulled from MARIANO-PC copied into `dev/autosave3/tree/Cities` (`Big One.autosave1.sc3` 4,402,461 B,
`Big One.autosave2.sc3` 4,561,103 B; their `Big One.sc3` is byte-identical to the tree's), their `bigcity.ini` into
`dev/autosave3/inst` (sc3bigcity log: "size 1024"). Build with the fixes below. All loads by posted clicks:

| # | path | file | window | result |
|---|---|---|---|---|
| 9 | fresh game, main menu Load City | Big One.autosave1 | 800x600 | alive, city shown |
| 10 | second load, from inside the running city | Big One.autosave2 | 800x600 | alive, played 30 s |
| 11 | third load, inside the city | Big One.autosave1 | 800x600 | alive, played 20 s |
| 12 | fourth load, inside the city | Big One.sc3 (plain) | 800x600 | alive, played 20 s |
| 13 | fresh game, main menu Load City | Big One.autosave2 | 800x600 | alive |
| 14 | fresh game, main menu Load City, window maximized before the tick | Big One.autosave1 | 3840x1984 | alive, 863 MB, 20 s more |
| 15 | `-Stock -City` | Big One.sc3 / autosave1 / autosave2 | 800x600 | all three exit within 2 s, no Application Error event |
| 16 | `-Stock -City` (control) | Frankfurt | 800x600 | runs 40 s |

Run 15 shows the stock game exits on the plain Big One exactly as on the two autosaves, so the stock control cannot
separate them: in the stock game the owner's autosave behaves the same as the plain file. With mods on, no run crashed
and no VEH fault other than the known handled ones. Remaining differences from MARIANO-PC that were not reproduced:
its own sc3resize.ini / perf.ini / netmod packs, GPU and driver, 2560x1351 at 120 dpi (tested 3840x1984 at 240 dpi).
Verdict: owner crash still not reproduced on LIVING-PC, cause not identified. Nothing found that is specific to the
autosave file.

Defensive item (orchestrator ask): at a city change the queued message is dropped (`g_post_city` cleared) and the
interval restarts when the new city's lock counter city+0x144 is first read as 0. Log: `CITY> lock 0, interval starts`
1.0 to 3.0 s after each `CITY> city` in runs 9-14. Whether the load had fully ended at that moment is not measured;
the "message waited > 5 s" guard still covers a long load.

### Defects found next to the load (fixed)
1. Queued saves after a long load. Run 5 (`dev/autosave3/inst/as_1024_reload.log`): city pointer changed at
   267.0 s, the game thread stayed in the load until ~303 s, then `SAVE> #2` at 304.8 s and 5 x "unchanged, dropped"
   back to back, 1.5-2.5 s each = about 10 s of freezes right after the load. Cause: the watcher posts WM_AUTOSAVE
   every second while a save is due, nothing tracks a message already queued, the handler never re-checks that the
   save is still due, and the "city just loaded" 20 s guard counts from the watcher seeing the new pointer (it had
   expired by the time the load ended).
2. Same root: a message posted for the old city could run on the new one.

Diag, run 8 (`dev/autosave3/inst/as_1024_reload_diag.log`, return addresses on the stack at each dispatch):
- main loop dispatch: `SC3U+0x61399 / +0x5E866 / +0x5E6A7 / +0x2E61`.
- Load City dialog open: dispatched from its modal loop (`GZWIND+0x6AC9`, `SIMINIT+0x8A64`, `SIMUI+0x1648C`), city
  lock city+0x144 = 3, save put off. The lock guard covers dialogs.
- no dispatch at all inside the load (173.3 s pointer change, next dispatch 185.9 s, put off "city just loaded").
- the progress service vtable SC3U 0x004CF59C open/close are not used by the load (depth stayed 0).

Fix: the watcher posts only when no WM_AUTOSAVE is queued (`g_posted`), the handler drops a message posted for
another city or one no longer due, and a message that waited over 5 s in the queue (the game thread was stuck, a
load) restarts the 20 s "just loaded" wait from that moment. Checked in the rotation run: after each in-game load the
log shows `SAVE> message was for another city, dropped` and the first save one interval after the load, no burst.

## B. Three autosave files

Rule (also in `re/sessions/STATUS_autosave3.md`):
- A `<city> (auto 5 min).sc3` newest, B `<city> (auto 10 min).sc3`, C `<city> (auto 1 h).sc3`.
- Each save goes to `<city> (auto).tmp.sc3`. Failed or byte-identical to A: tmp deleted, nothing moves.
- Else, when A exists and B is missing or its save is >= 10 min old: B moves to C when C is missing or >= 60 min old,
  then A moves to B. Last tmp becomes A. Ages = file last-write time (kept by the rename) = when that save was made.
- Default 5 min interval: A 0-5 min old, B the save before it (5-10 min), C 10-65 min old.
- `keep=` is gone from autosave.ini. Files named by older builds (`<city>.autosave1/2.sc3`) are left alone. A city
  loaded from an autosave saves under its base name (" (auto ..." and ".autosaveN" stripped).
- Test switch `SC3AUTOSAVE_TIERS=<b>,<c>` (seconds) shortens the 10 min / 1 h ages.

Run (`SC3AUTOSAVE_SECONDS=30`, `SC3AUTOSAVE_TIERS=60,150`, Frankfurt, sim running, `dev/autosave3/inst/as_rotation.log`):
```
SAVE> #1 ... (auto 5 min).sc3
ROT> A (31 s) -> B (was -1 s)                       SAVE> #2
ROT> B (62 s) -> C (was -1 s)   ROT> A (31 s) -> B   SAVE> #3
ROT> A (31 s) -> B (was 62 s)                       SAVE> #4   (C 93 s < 150 s: kept)
ROT> A (31 s) -> B (was 62 s)                       SAVE> #5
```
Load City shows the names as `Frankfurt, Germany (auto 1 h)` / `(auto 10 min)` / `(auto 5 min)` with preview, and
each of the three loaded in-game (posted clicks), population and date matching the preview.
The mods page "Cada:" group (5/10/15/30) needs no change: with 10/15/30 the "5 min" file is the newest save and the
"10 min" file the one before it.

Pictures (`verify/autosave3/owner_shots/`, not for git):
- `loadcity_list_three_files.png` the list with the three files, "(auto 10 min)" selected
- `loaded_auto_10min.png`, `loaded_auto_1h.png`, `loaded_auto_5min.png` (selection + loaded city)
- `before_list_old_names.png` the old `.autosave1/2` names, for comparison
- `bigone_autosave1_fresh.png`, `bigone_autosave2_secondload.png`, `bigone_autosave1_mainmenu_maximized.png` (runs 9, 10, 14)

## Notes for the owner
- Loading an autosave and then using the game's own Save writes into that autosave file (the game's file name now
  points at it), which the rotation later replaces. Same as before this change. Use "Guardar como" to keep it.
- Not tested: interval 10/15/30 in game, an unnamed city, the real 10 min / 1 h ages (only the shortened test ages).
