# STATUS_onramp (child of "SC3: owner hand-test bugs 10-21 (highways + avenues)")

## goal
Owner report on LAN build 2cedb34: after placing an on-ramp the light-blue pre-selection disappears and no more ramps can
be placed until another tool is picked and the On-ramp tool picked again. Decide with an A/B whether it is stock; if a
mod causes it, find and fix the cause.

## design
Arms (fresh launch of a lab copy each): A = sc3resize only (stock tools), B = full release set, then bisect B.
Lead suspect: the stock selection point cap (NET_RAMPS.md 1.2, DAT_100322a4 < 0x200, reset only by the drag path
builder FUN_1000488d).

## built
inst_onramp (B: all 7 mods + mods_launch from 2cedb34 sources, sc3netmod from the worktree with RAMPCAP), inst_onramp_A (sc3resize only).

## proven in game vs offline only
IN GAME, both arms: STOCK. The add-point cap DAT_100322a4 hits 512 after ~55 mouse moves (~9 points per move);
then no preview, $0, click places nothing. Same counts at every step in A (resize only) and B (all 7 mods). Demolish+reselect
does not fix it, Road tool+reselect resets the counter. No bisect needed. Owner asked for the fix (2026-10-22): RAMPCAP built and checked in game (see verify/onramp/RESULTS.md):
3 ramps in a row with 100-move sweeps (cap stays 3), undo/redo of a 4th, save + reload identical, final DLL 5/5 clean starts.
Startup crashes investigated: races between mods, not RAMPCAP. 6 of 56 launches died; 4 logged: sc3perf module-unload read (fixed),
sc3perf x sc3netmod VirtualProtect restore on a SimTransit page (fixed), sc3overscroll x sc3simrun restore race on SIMSPR page
0x10043000 (fixed). No-restore rule applied to resize/simrun/overscroll/undo: 30 of 30 clean starts. Details: verify/onramp/RESULTS.md.
Sheets: MAIN\verify\onramp\owner_shots\onramp_fix_sheet.png, MAIN\verify\onramp\owner_shots\onramp_ab_sheet.png

## blocked on
nothing

## files owned
- Simcity_wt_onramp: re/harness/src/sc3netmod_tmpl.c (RAMPCAP, marked `task onramp`),
  re/harness/src/sc3perf.c (module pin in rc_watcher + exec_ranges), re/harness/src/sc3netmod.c (write_code: no restore),
  re/harness/src/sc3resize.c, sc3simrun.c, sc3overscroll.c, sc3undo.c (no protection restore, RW unlocks -> RWX),
  verify/onramp/RESULTS.md (new), re/analysis/NET_RAMPS.md (1.2: one measured paragraph)
- MAIN verify/onramp/owner_shots/*.png (game frames, not for commit)

## instance
Simcity_stock_hwlight\re\harness\inst_onramp (+ inst_onramp_A ...), last PIDs 43068 (A), 63496 (B), 66968 (reload) + 4 start checks, all stopped

## needs owner
Look at onramp_fix_sheet.png; hand test on the next LAN build.

## asks of other streams
-
