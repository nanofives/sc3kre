# nopause: keep the simulation running under pop-up windows (round 2026-11-21)

Owner 2026-11-21 (after popslow): "Yes, add a switch". A mods page row, OFF by default, that keeps the simulation
running while those windows are open. Stock behaviour exactly when off.

## Verdict

**Built in sc3simrun (NOPAUSE block) with a default-off row on the "Activar mods" page. With it on, Budget,
Preferencias (and the mods pages inside it), the landmark list and the Rewards list no longer pause the simulation:
the date runs at the normal rate with each of them open (1.46-1.53 days/s against nominal 1.50 at speed 3; stock and
switch off 0.00). With it off nothing is touched and the measurements match stock.**

**Query is left stock (it still pauses), behind a lab-only switch. This needs an owner call:** the stock query code also
takes `cISC3City::Lock` (vt+0x234) for as long as its window is open. With only the pause skipped, the clock counted
125 days in 20 s with the query window open while the bar date and population did not move, and the date caught up after
the window closed (picture `owner_shots/query_lab_lock_frozen_bar.png`). Skipping the lock too would let the sim change
the objects the query dialog and the code after it are reading, so that was not done.

Why sc3simrun: it already holds the other SimHiddenPause fix (the camera hold, SIMSPR 0x1004401a) and the trace hook on
the same two city vtable slots. sc3resize only gets the page row.

## How it works

Stock (popslow trace, re-checked here from the arming log): each of these windows takes two holds through
`cISC3City::SimHiddenPause` (SIMCITY 0x100058ac, city vt+0x21c: clock Pause, `+0x144 += 1`, heartbeat vt+0x1c(1)) and
gives both back through `SimHiddenUnpause` (0x1000590e, vt+0x220) when it closes:

| window | its own hold / release (return addresses) | second hold / release |
|---|---|---|
| Budget | SIMMISC 0x1000c294 / 0x1000c301 (cIGZGameCommand::Execute 0x1000c22f) | SIMSPR 0x100490ac / 0x10049074 (city view cIGZWin::DoMessage 0x10048d7a, messages 0x62ba7b42 / 0x62ba7b43) |
| Preferencias, mods pages | SIMUI 0x10010a84 / 0x10010b85 (cIGZGameCommand::Execute 0x10010a56) | same |
| landmark list, Rewards list | SIMUI 0x100119c2 / 0x10011ac9 (FUN_10011919) | same |
| Query (lab only) | SIMUI 0x10010c97 / 0x1001148f (sc3_ui_query_handle_tile 0x10010c39), plus city Lock vt+0x234 at entry, Unlock vt+0x238 at the end `[CONFIRMED @ SIMUI 0x10010c39 decomp lines 59-60, 369-371]` | same |

The fix wraps the city vtable slots +0x21c / +0x220 (SIMCITY 0x1001347c / 0x10013480) and decides by return address:

- a hold from a window site is not passed on and is counted, its release is skipped while that count is above 0;
- the SIMSPR city view hold is skipped only while a window hold is counted, so every other modal window (load / save
  dialogs, message boxes, the civic look picker in sc3resize, Query) keeps the stock pause; logged as
  `NOPAUSE> modal window outside the list: city view hold kept (stock pause)`;
- every other caller (camera hold, zoom, rotate, month pass) is stock;
- each return address is checked at arming to follow `call [reg+0x21c]` / `call [reg+0x220]` (FF 9x imm32); a site
  that differs is left stock and logged. All 4 sites and the SIMSPR pair passed on this build:
  `### NOPAUSE: on, 3 of 4 window sites armed, city view hold armed` (Query skipped as lab only).

Switches: `simrun.ini [sim] run_under_windows=0` (default), env `SC3SIMRUN_NOPAUSE=1/0` wins, the mods page row writes
`[env] SC3SIMRUN_NOPAUSE=1` into `sc3mods.ini` when checked (a '+' row, no key when unchecked). `SC3SIMRUN_NOPAUSE_QUERY=1`
(lab) adds Query. Export `sc3simrun_nopause(DWORD out[7])` returns the counters.

## Measurements (popslow_meter, Moscow, 800x600, speed 3, nominal 1.50 days/s, 15 s windows)

| window | switch on, env (`on_800x600_s3`) | switch on, from sc3mods.ini, final build (`final_on_ini_s3`) | switch off (`off_800x600_s3`) | stock (popslow) |
|---|---|---|---|---|
| Budget | 1.51 days/s, held 0.0% | 1.53, 0.0% | 0.00, held 100% | 0.00, 100% |
| Preferencias | 1.53, 0.3% | 1.47, 0.0% | 0.00, 100% | 0.00, 100% |
| mods page | 1.53, 0.0% | 1.47, 0.0% | 0.00, 100% | 0.00, 100% (mods build) |
| landmark list | 1.47, 0.0% | 1.53, 0.0% | 0.00, 100% | 0.00, 100% |
| Rewards list | 1.46, 0.0% | 1.53, 0.0% | 0.00, 100% | 0.00, 100% |
| Query | 1.47, 0.0% (clock only, see verdict; earlier build) | 0.00, 100% (stock, lab only) | 0.00, 100% | 0.00, 100% |
| flyout (control) | 1.51, 0.0% | - | - | 1.50 |

Closed windows in the same runs: 1.43-1.53 days/s. Every skipped hold was followed by its skipped release
(`NOPAUSE> <window> opened ... / closed: its release skipped` pairs in sc3simrun.log, coordinator `+0x144` back to 0 after
each close in the meter). Raw: `verify/nopause/ab/ab.jsonl`, logs `ab_on.log`, `ab_off.log`, `ab_final.log` (gitignored).

## Checks with the sim running under a window (switch on, cheetah, posted input only)

| case | result | picture |
|---|---|---|
| Budget open, months tick | date 1/17 -> 4/16/2066 in 10 s with the window open, population changes | `budget_open_t0.png`, `budget_open_t10s.png` |
| Budget open across a year end, slider moved, OK | the window recomputes with the current figures when a slider moves (Fondos actuales = the bar's funds); after OK funds kept advancing (952,709 -> 1,075,716 over 2 years), nothing reverted; reopened, the Educación slider is where it was left and its estimate is 59,040 against 48,216 before | `budget_edit_after_yearend.png`, `budget_reopened_edit_kept.png` |
| landmark list: pick, OK, place | Ayuntamiento de San Francisco placed while the date ran (5/1 -> 6/10/2066) | `landmark_list_then_placed.png` |
| Rewards list: pick, OK, place | La Bolsa placed (-$60) while the date ran (11/18 -> 12/3/2065) | `rewards_list_then_placed.png` |
| mods page / Activar mods | page works with the sim running; the row checked and OK wrote `[env] SC3SIMRUN_NOPAUSE=1`; the next start read it with no env set (`### NOPAUSE: on`) | `modspage_row_es_default_off.png`, `modspage_row_es.png`, `modspage_row_en.png` |
| saving | Save from the options flyout after a Budget open/close: file rewritten (845,407 -> 853,061 bytes), holds 0 afterwards, the saved city loads at the saved day (2476043) | - |
| Query (lab build) | see verdict | `query_lab_lock_frozen_bar.png` |

Pictures: `owner_shots/` (worktree and MAIN `verify/nopause/owner_shots/`). Stock budget detail seen on the way: the
window's month label ("November 2065") is set when it opens and is not refreshed by a slider move.

The mods page row fits: the left column's five rows under "Simulación y edificios" are 17 px now (were 19), so the column
ends at 355 against the feature column's 356 and the notes, the city checkbox and Volver are where they were
(`modspage_row_es.png`). Texts: es "Sin pausa en ventanas", en "No pause in pop-ups", fr "Pas de pause en fenêtre",
de "Keine Pause bei Fenstern", it "Nessuna pausa nei pop-up", nl "Geen pauze bij pop-ups", sv "Ingen paus i
popup-fönster" (machine translations as the others, `sc3lang.py check`: 359 keys, 0 missing in all 7).

## Found on the way (not changed)

- **sc3perf BUSY sampler can crash the game when a module unloads during a stall.** The first Query check died 6 s after
  the window closed: `VEH FAULT 0xC0000005 at sc3perf.dll+0x586E`, READ 0x5B000051, thread = the BUSY watcher.
  +0x586E is `is_retaddr` +0x3e, called from `busy_sample` +0x282 (resolved with a /MAP rebuild of the same source).
  `exec_ranges()` keeps each module's executable sections from a snapshot at the stall start and `is_retaddr` reads
  `p[-7..-1]` in those ranges with no `__try`, so a module freed after the snapshot leaves a range that faults. The stall
  began 1.2 s after my probe tool's Frida session detached (its agent DLL unloads on detach) during a month pass at
  cheetah (`BUSY> date stopped: 1199 ms ... clock pause 1`). [UNCERTAIN] which module was at 0x5B000000 (not logged).
  Not NOPAUSE code; it needs `busy=1` (shipped) plus a module unload during a stall. Suggested fix for whoever owns
  sc3perf: a `__try` around the reads in `is_retaddr`. The later checks ran in one Frida session and did not hit it.

## Files

- `re/harness/src/sc3simrun.c` NOPAUSE block (hooks, ini/env, export), header Config line, trace hook folded in.
- `re/harness/src/sc3resize.c` MODTOGGLE row `+SC3SIMRUN_NOPAUSE`, `MT_LEFT_DY` 17.
- `re/harness/lang/{es,en,fr,de,it,nl,sv}.txt` key `resize.mt_nopause` (es/en by `sc3lang.py extract`, which also
  re-sorted the existing `resize.mt_lotrect` line).
- `re/tools/nopause_probe.py` (one step per call), `nopause_check.py` (query / lists / mods page in one Frida session),
  `nopause_unpause.py` (wait for the clock, posted unpause click).

Commands (inside the test slot, `PROYECTOS_TEST_MEM_GB=3`: the 8 GB default waited on memory):
`py -3.12 re/tools/popslow_run.py --name nopause --arm mods --out verify/nopause/ab --label on_800x600_s3 --win 15 --reps 1 --pops flyout,budget,prefs,modspage,landmarks,rewards,query --env SC3SIMRUN_NOPAUSE=1`,
the same with `--label off_800x600_s3 --env SC3SIMRUN_NOPAUSE=0`, and `--label final_on_ini_s3` with no env (ini).
