# STATUS autosave3 (child of "SC3 mods page layout + autosave rotation + load crash", 2026-10-28)

## goal
A. Owner: "al cargar un autosave el juego crashea" (sc3mods-2026-10-28). Reproduce, find the cause, fix.
B. Owner: "guardar hasta 3 autosave, el de los últimos 5 minutos, últimos 10, última hora". Three files of fixed
   meaning instead of keep=N.

## verdict (A): owner crash NOT reproduced, two load-adjacent defects found and fixed
Update: owner repro target (MARIANO-PC Big One files + bigcity.ini 1024, main menu, fresh, also maximized 3840x1984,
second loads, plain Big One) = 6 more loads, none crashed. `-Stock` exits on plain Big One the same as on the
autosaves. Detail: verify/autosave3/RESULTS.md runs 9-16. Defensive restart at lock 0 added.
Tree `dev/autosave3/tree` (10-28 base), worktree build of sc3autosave. Seven loads of an autosave file, none crashed:

| # | path | file | sim when saved | result |
|---|---|---|---|---|
| 1 | `-City` at start | Frankfurt autosave1 | paused | alive, no fault |
| 2 | in-game Load City | Frankfurt autosave1 | paused | alive |
| 3 | in-game Load City | Frankfurt autosave1 (overwrote the file the city was loaded from) | running | alive |
| 4 | in-game Load City, save due during the load | Frankfurt autosave2 | paused | alive |
| 5 | in-game Load City, save due | Europolis 1024 autosave1 (6.9 MB) | paused | alive, see defect 1 |
| 6 | main menu Load City | Frankfurt autosave1 | paused | alive |
| 7 | `-Stock` (SC3MODS_OFF=1) `-City` | Frankfurt autosave1 | | alive 40 s: the file itself loads in the stock game |
| 8 | in-game Load City, `SC3AUTOSAVE_DIAG=1` | Europolis 1024 autosave1 | | alive, see diag below |

Only VEH lines in sc3resize.log: the benign start-up `0xC0000096 @ SC3U+0x84122`, and in run 5 first-chance
`0xC0000005 @ KERNEL32+0x1CA9E` read of 0x000000FF called from sc3resize.dll+0x331BC (a guarded probe, handled, not
autosave code). LIVING-PC's Application log has no SC3U crash on 2026-10-28 (last: 2026-10-27 10:05/10:06,
`SC3U+0x143a` from `Simcity_release`), so the owner's crash happened on another PC. Owner's sc3autosave.log /
sc3resize.log from that PC are needed to decide it (asked the orchestrator).

Defect 1 (run 5, `inst/as_1024_reload.log`): the city pointer changed at 267.0 s ("CITY>"), the game thread stayed in
the load until ~303 s, and 6 WM_AUTOSAVE messages the watcher had posted between the tick and the pointer change ran
back to back the moment the load ended: `SAVE> #2` at 304.8 s, then 5 x "unchanged ... dropped" at 1.5-2.5 s each.
The "city just loaded" 20 s guard counts from the watcher seeing the pointer, not from the end of the load, so it had
expired (36 s). `autosave_now` never re-checks that a save is still due, so every queued message is a full save.
Defect 2: the watcher posts a new WM_AUTOSAVE every second while one is still queued (nothing tracks "posted").

Diag (run 8, `inst/as_1024_reload_diag.log`, return addresses on the stack at each WM_AUTOSAVE dispatch):
- main loop: `SC3U+0x61399 / +0x5E866 / +0x5E6A7 / +0x2E61`.
- Load City dialog open: dispatched from the dialog's modal loop (`GZWIND+0x6AC9 ... SIMINIT+0x8A64 ... SIMUI+0x1648C`),
  city lock counter city+0x144 = 3, so the save is put off ("city locked"). The lock guard holds there.
- during the load itself: no dispatch at all between CITY> 173.3 s and the next dispatch at 185.9 s (put off "city
  just loaded"). So no autosave ran inside a load in this run.
- the progress service (SC3U vtable 0x004CF59C) open/close are NOT called by the load: depth stayed 0.

Fix (both in sc3autosave.c): one message in flight at a time (`g_posted`), the handler drops a message that is no
longer due or was posted for another city, and the "just loaded" guard also restarts when the game thread comes
back from a stall (no message for 5 s, i.e. a load), measured on the game thread.

## rotation rule (B), written before building
Files beside the city file (or `dir=`), names as listed in Load City (no extension shown):
- A = `<city> (auto 5 min).sc3`  newest autosave
- B = `<city> (auto 10 min).sc3`
- C = `<city> (auto 1 h).sc3`

Every interval (mods page "Cada:", default 5 min) the city is saved to `<city> (auto).tmp.sc3`. Then:
1. Save failed or empty: tmp deleted, nothing else changes.
2. tmp byte-identical to A: tmp deleted, nothing else changes (paused city).
3. If A exists and (B is missing or B's save is >= 10 min old):
   a. if B exists and (C is missing or C's save is >= 60 min old): B renamed over C;
   b. A renamed over B.
4. tmp renamed over A.
"Age" = now minus the file's last-write time; a rename keeps it, so it is the time that save was made.
With the 5 min default: A is 0-5 min old, B is the previous save (5-10 min), C is 10-65 min old (it takes B's save
when it turns 60 min old). With a 10/15/30 min interval the "5 min" file is the newest save and "10 min" the one
before it. Old `<city>.autosave1/2.sc3` files from earlier builds are left alone (never deleted).
A city whose file is itself an autosave saves under its base name (" (auto ...)" and ".autosaveN" stripped).

## built
`pwsh re/scripts/sc3dev.ps1 build autosave3 -Mods sc3autosave` -> dev/autosave3/inst/sc3autosave.dll (130,560 B), clean.

## proven game-side vs static only
Game-side: rotation sequence with shortened ages (verify/autosave3/RESULTS.md), the three names in Load City, one
in-game load of each file, stale message dropped after each load, first save one interval after the load.
Static only: the real 10 min / 1 h ages (same code path, thresholds from SC3AUTOSAVE_TIERS), intervals 10/15/30.
Owner crash: not reproduced (8 loads), cause not identified.

## blocked on
nothing (owner logs overwritten; orchestrator asks the owner for repro details)

## files owned
- re/harness/src/sc3autosave.c
- re/sessions/STATUS_autosave3.md
- verify/autosave3/RESULTS.md
- (not for git) verify/autosave3/owner_shots/*.png

## game-harness need
none (sc3dev tree only)

## asks of other sessions
- orchestrator: owner's sc3autosave.log + sc3resize.log from the PC where the load crashed.
- orchestrator: BOARD.md line "Autosave every 5 minutes (rotating `<city>.autosave1/2.sc3`" needs the new names, and
  the release README if it names the files. Not edited here (BOARD.md is yours).
- modsui: nothing, the MP_AS_* rows are unchanged.
