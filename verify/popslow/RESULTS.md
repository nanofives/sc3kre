# popslow: simulation speed with a pop-up open (round 2026-11-21)

Player (Simtropolis 2026-11-21): "the simulation speed drops when a pop-up menu appears. It isn't a big issue".

## Verdict

**The mods cause no slowdown. What the player sees is the stock game pausing the simulation while a modal window is
open, and the mods keep that exactly as stock.** No game change was made (the brief keeps stock behaviour).

1. **Modal windows stop the date completely, stock and mods alike**: Budget, Preferencias (and the mods page inside it),
   Query, the landmark list ("Elige un edificio destacado") and the Rewards list. Every open window measured 0 days with the
   clock held 100% of the time, all of it the coordinator UI hold `city+0x144`. On close the date resumes at full rate.
   Paused time is dropped, not replayed: Resume restarts the clock's time base and the clock callback skips every fire while
   the pause count `clock+0x54` is non-zero (`cmp [esi+0x54],0; jne` `[CONFIRMED @ SIMCITY 0x1000a885]`).
2. **Who holds (traced, identical in both builds)**: each modal window takes exactly two holds through
   `cISC3City::SimHiddenPause` (SIMCITY 0x100058ac, city vt+0x21c: `+0x144 += 1`, clock Pause) and releases both through
   `SimHiddenUnpause` (0x1000590e) when it closes. No mod takes or keeps a hold. Callers (return addresses, `verify/popslow/holdtrace_*.jsonl`):

   | window | hold 1 (the window's own call) | hold 2 |
   |---|---|---|
   | Budget | SIMMISC `cIGZGameCommand::Execute` 0x1000c22f (ret 0x1000c294, release 0x1000c301) | SIMSPR city view `cIGZWin::DoMessage` 0x10048d7a (ret 0x100490ac, release 0x10049074), reached from GZWIND through GZServiceD 0x100039d7 |
   | Preferencias, mods page | SIMUI `cIGZGameCommand::Execute` 0x10010a56 (ret 0x10010a84 / 0x10010b85) | same |
   | Query | SIMUI `sc3_ui_query_handle_tile` 0x10010c39 (ret 0x10010c97 / 0x1001148f) | same |
   | Landmark list, Rewards list | SIMUI `FUN_10011919` (ret 0x100119c2 / 0x10011ac9) | same |
   | Reunirse, advisor page, petition, flyouts, Review flyout windows | none | none |

   In the modded run the Query call chain passes through sc3resize (ret 0x1005fbeb, its query hook) but the hold is the
   same stock SIMUI one. Static: `sc3_ui_query_handle_tile` calls vt+0x21c at entry and vt+0x220 at its end with the query
   dialog's vt+0x2c between them; the measured hold lasts as long as the window is open, so that call does not return
   while the window is open.
3. **Non-modal windows do not slow the date** (Reunirse, advisor page, petition, the advisor page a ticker click opens,
   flyouts, the six Review flyout windows): at speed 3 (nominal 1.50 days/s) mods 1.47-1.53 open against 1.45-1.55 closed,
   at 800x600 Normal and at 1600x1200 Auto (2.0x). Stock 1.15-1.50 (its month pass holds the clock 2-9%, so it is noisier).
4. **Frames**: in the stock game the text-redrawing dialogs (Reunirse, advisor, petition, landmark and Rewards lists) cost
   49-93 ms of UI-thread CPU per frame and run at 1.3-5.0 frames/s (3-4 ms per frame with nothing open). With the mods
   (shipped `perf.ini`, `sysmem=1`) the same dialogs cost 3.6-5.0 ms per frame at 800x600 and 9.7-11.6 ms at 2x (7-9 ms
   with nothing open at 2x). The mods page at 2x is the heaviest modded window, 17.8 ms per frame, and it pauses the sim
   anyway. Street agents move by elapsed time per tick, capped at 250 ms (`cSC3OccupantManagerAnim::DoAnimationTick`,
   SC3U 0x00426140), so a low frame rate does not slow cars above about 4 frames/s. So the mods make pop-ups cheaper, not
   dearer.
5. **Cheetah speed on 2 cores** (game pinned to 2 logical CPUs as a stand-in for a weaker PC): stock and mods both show
   long stalls with nothing open (UI thread blocked, about 0.3 frames/s, clock held 70-100% by the month-pass bracket and
   sim work). Closed/open pairs move both ways by up to 2x, so this setup cannot show a pop-up effect. No consistent
   direction in either build.

### Possible follow-ups (owner calls, not done)
- A mods-page switch to let modal windows keep the sim running (skip the two SimHiddenPause calls while a window is open,
  like sc3simrun does for camera moves). It changes stock behaviour, so only if the owner wants it.
- Dev trap: `dev/<name>/inst` has no `perf.ini`, so `sysmem=0` there (Reunirse 5 fps at 800x600 with mods). The release
  ships `Apps/perf.ini` with `sysmem=1`. Copy `stage/release/Apps/perf.ini` into `inst/` to measure the player's config.
- Side note: the stock Reunirse list page opened off-client at (1296,506) in a fresh stock process after a 1600x1200
  modded run (slot storage not traced, `re/analysis/REUNIRSE_POSITION.md`); measured by moving it with MoveTo vt+0xcc.

### Suggested line for the player
The game itself pauses the simulation while the budget, query, preferences (and our mods page), landmark and rewards
windows are open, and starts it again when you close them. The mods keep that behaviour. Advisor and petition windows
do not pause it.

## Method

- City `Moscow, Russia.sc3`, fresh load per arm, LIVING-PC (shared with other sessions), dev tree `dev/popslow/tree`.
  Stock control = `sc3dev run -Stock` (sc3winonly only, 800x600 window). Mods = all 11 mods with the shipped `perf.ini`.
  2x arm = client resized to 1600x1200 with posted WM_SIZING (HUD Auto -> factor 2.000, logged).
- `re/tools/popslow_meter.py`: ReadProcessMemory only. Day count `clock+0x4c` (clock = `city+0x130`, city =
  `*(*(SC3U 0x004fa86c)+0x48)`, both vtables checked), pause count `+0x54`, coordinator counters `city+0x140/+0x144/+0x148`
  sampled at 50 Hz, thread CPU by GetThreadTimes (UI thread = owner of the Gonzo window).
- `re/tools/popslow_ab.py`: per pop-up a closed window then an open window (15-20 s), frames counted by a Frida counter on
  the SIMSPR render-view frame 0x1001cab9 and the heartbeat 0x00426140 (they agree with sc3perf's own fps column),
  pop-ups opened and closed by posted clicks found through the UI tree, speed set with the GZ speed message.
- `re/tools/popslow_run.py` runs one arm (launch, unpause by a posted click, resize, optional `--cores`, `--trace`, stop
  own PID). `re/tools/popslow_holdtrace.py` logs SimHiddenPause / SimHiddenUnpause callers. `re/tools/popslow_table.py`
  makes the tables below. All runs inside the test slot.
- Commands: see `re/sessions/STATUS_popslow.md` (MAIN). Raw data (gitignored, worktree): `verify/popslow/ab/ab.jsonl`,
  `verify/popslow/holdtrace_{stock,mods}.jsonl`, logs `verify/popslow/*.log`.

Columns: n = closed/open pairs; UI ms/frame = UI-thread CPU per frame; Locks/s = sc3perf surface Locks (mods only).
"news" = the advisor page opened by a click on the ticker. review<i> = Review flyout item i (2 = Budget). In the 2x arm
the ticker click missed (no dialog in the open window).

## Speed 3, all pop-ups

**stock_800x600_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 1 | 1.45 | 1.50 | 2% (0%) | 91.1 | 220.8 | 3.6 | 2.4 | - |
| reunirse | 1 | 0.20 | 1.15 | 9% (0%) | 17.3 | 1.8 | 2.6 | 78.9 | - |
| advisor | 1 | 1.15 | 1.35 | 3% (0%) | 34.1 | 5.0 | 3.8 | 49.2 | - |
| petition | 1 | 1.45 | 1.40 | 6% (0%) | 61.0 | 1.3 | 3.9 | 93.1 | - |
| news | 1 | 1.49 | 1.32 | 9% (0%) | 69.2 | 1.3 | 3.6 | 91.5 | - |
| budget | 1 | 1.44 | 0.00 | 100% (100%) | 69.3 | 93.4 | 3.3 | 2.7 | - |
| prefs | 1 | 1.40 | 0.00 | 100% (100%) | 148.2 | 96.6 | 2.9 | 2.5 | - |
| landmarks | 1 | 1.33 | 0.00 | 100% (100%) | 110.2 | 3.7 | 3.5 | 55.7 | - |
| rewards | 1 | 1.45 | 0.00 | 100% (100%) | 134.4 | 3.5 | 3.1 | 68.3 | - |
| query | 1 | 1.45 | 0.00 | 100% (100%) | 137.2 | 118.3 | 3.1 | 2.4 | - |

**mods_800x600_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 1 | 1.50 | 1.50 | 0% (0%) | 75.7 | 29.3 | 3.6 | 3.0 | 99 |
| reunirse | 1 | 1.50 | 1.49 | 0% (0%) | 26.1 | 29.5 | 3.5 | 3.7 | 22721 |
| advisor | 1 | 1.45 | 1.50 | 0% (0%) | 14.6 | 101.7 | 2.3 | 3.6 | 50481 |
| petition | 1 | 1.50 | 1.50 | 0% (0%) | 104.1 | 99.2 | 3.0 | 4.1 | 90905 |
| news | 1 | 1.50 | 1.50 | 0% (0%) | 99.7 | 62.7 | 3.3 | 5.0 | 77017 |
| budget | 1 | 1.50 | 0.00 | 100% (100%) | 105.2 | 103.3 | 3.2 | 2.4 | 43 |
| prefs | 1 | 1.50 | 0.00 | 100% (100%) | 65.1 | 95.0 | 3.6 | 2.2 | 45 |
| landmarks | 1 | 1.50 | 0.00 | 100% (100%) | 90.3 | 92.5 | 3.2 | 2.9 | 61539 |
| rewards | 1 | 1.45 | 0.00 | 100% (100%) | 89.8 | 38.1 | 3.2 | 3.0 | 32098 |
| query | 1 | 1.55 | 0.00 | 100% (100%) | 56.6 | 43.9 | 3.9 | 2.3 | 28 |
| modspage | 1 | 1.50 | 0.00 | 100% (100%) | 98.1 | 92.0 | 3.6 | 2.1 | 56 |

**mods_1600x1200_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 1 | 1.50 | 1.50 | 0% (0%) | 54.1 | 25.2 | 7.8 | 9.2 | 272 |
| reunirse | 1 | 1.50 | 1.50 | 0% (0%) | 59.4 | 59.9 | 6.6 | 10.6 | 57176 |
| advisor | 1 | 1.50 | 1.50 | 0% (0%) | 60.0 | 59.1 | 7.6 | 9.7 | 29087 |
| petition | 1 | 1.50 | 1.50 | 0% (0%) | 59.0 | 58.0 | 8.8 | 11.6 | 53948 |
| news | 1 | 1.50 | 1.50 | 2% (1%) | 41.5 | 48.3 | 11.5 | 11.3 | 456 |
| budget | 1 | 1.50 | 0.00 | 100% (100%) | 54.5 | 19.1 | 9.5 | 12.7 | 202 |
| prefs | 1 | 1.45 | 0.00 | 100% (100%) | 8.3 | 37.3 | 9.9 | 11.1 | 350 |
| landmarks | 1 | 1.50 | 0.00 | 100% (100%) | 45.2 | 50.7 | 9.8 | 10.4 | 34498 |
| rewards | 1 | 1.50 | 0.00 | 100% (100%) | 45.7 | 25.0 | 9.6 | 13.7 | 20454 |
| query | 1 | 1.50 | 0.00 | 100% (100%) | 27.1 | 45.8 | 12.7 | 9.1 | 359 |
| modspage | 1 | 1.50 | 0.00 | 100% (100%) | 49.8 | 41.4 | 10.0 | 17.8 | 325 |

## Speed 3, Review flyout windows; cheetah on 2 cores

**stock_800x600_s4_c2**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 2 | 4.20 | 3.72 | 36% (0%) | 149.0 | 92.5 | 3.0 | 3.4 | - |
| reunirse | 2 | 3.75 | 4.07 | 32% (0%) | 55.9 | 1.6 | 3.8 | 81.7 | - |
| advisor | 2 | 4.40 | 3.77 | 39% (0%) | 127.5 | 2.2 | 3.3 | 49.3 | - |
| petition | 2 | 2.95 | 3.40 | 45% (0%) | 42.1 | 0.9 | 4.8 | 85.7 | - |
| news | 2 | 4.02 | 3.30 | 42% (0%) | 95.8 | 45.0 | 3.7 | 48.4 | - |

**mods_800x600_s4_c2**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 2 | 2.77 | 3.50 | 39% (0%) | 10.0 | 19.3 | 4.1 | 4.2 | 198 |
| reunirse | 2 | 5.17 | 1.93 | 46% (0%) | 55.6 | 13.1 | 3.4 | 5.3 | 26786 |
| advisor | 2 | 0.79 | 2.90 | 51% (0%) | 1.8 | 8.3 | 3.9 | 5.4 | 12616 |
| petition | 2 | 4.20 | 4.66 | 19% (2%) | 35.7 | 53.8 | 3.1 | 3.9 | 31170 |
| news | 2 | 2.25 | 4.04 | 25% (0%) | 23.9 | 26.7 | 3.4 | 5.6 | 42060 |

**mods_1600x1200_s4_c2**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| flyout | 2 | 1.87 | 1.70 | 72% (0%) | 5.7 | 2.0 | 10.2 | 16.1 | 136 |
| reunirse | 2 | 1.69 | 2.05 | 66% (0%) | 0.9 | 1.8 | 18.7 | 28.8 | 2556 |
| advisor | 2 | 4.22 | 2.37 | 55% (0%) | 9.0 | 4.3 | 17.4 | 18.6 | 3403 |
| petition | 2 | 3.62 | 5.06 | 15% (0%) | 11.5 | 14.7 | 17.9 | 19.7 | 15142 |
| news | 2 | 3.72 | 4.06 | 23% (0%) | 9.7 | 10.5 | 18.3 | 19.6 | 492 |

**stock_review_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| review0 | 1 | 1.40 | 1.47 | 3% (0%) | 130.9 | 61.8 | 3.3 | 3.7 | - |
| review1 | 1 | 1.40 | 1.47 | 2% (0%) | 72.9 | 101.9 | 3.8 | 4.1 | - |
| review3 | 1 | 1.40 | 1.47 | 5% (0%) | 55.5 | 45.3 | 4.8 | 4.6 | - |
| review4 | 1 | 1.40 | 1.47 | 4% (0%) | 48.4 | 7.0 | 4.4 | 14.1 | - |
| review5 | 1 | 1.40 | 1.40 | 4% (0%) | 53.7 | 88.7 | 4.8 | 4.7 | - |
| review6 | 1 | 1.40 | 1.47 | 6% (0%) | 136.2 | 20.4 | 3.6 | 12.5 | - |

**mods_review_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| review0 | 1 | 1.53 | 1.53 | 0% (0%) | 96.5 | 112.9 | 3.1 | 2.6 | 211 |
| review1 | 1 | 1.47 | 1.53 | 0% (0%) | 112.1 | 107.4 | 2.7 | 2.7 | 518 |
| review3 | 1 | 1.47 | 1.53 | 0% (0%) | 111.6 | 110.5 | 2.7 | 2.7 | 226 |
| review4 | 1 | 1.47 | 1.53 | 0% (0%) | 109.1 | 108.2 | 2.9 | 2.8 | 10106 |
| review5 | 1 | 1.53 | 1.53 | 0% (0%) | 89.1 | 105.3 | 2.9 | 3.2 | 198 |
| review6 | 1 | 1.47 | 1.53 | 0% (0%) | 84.5 | 102.6 | 3.2 | 3.7 | 8094 |

**mods2x_review_s3**

| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open | UI ms/frame closed | UI ms/frame open | Locks/s open |
|---|---|---|---|---|---|---|---|---|---|
| review0 | 1 | 1.53 | 1.53 | 0% (0%) | 51.7 | 48.1 | 10.0 | 11.8 | 450 |
| review1 | 1 | 1.47 | 1.53 | 0% (0%) | 52.6 | 48.7 | 9.0 | 11.6 | 589 |
| review3 | 1 | 1.53 | 1.47 | 0% (0%) | 41.5 | 32.9 | 14.5 | 14.0 | 369 |
| review4 | 1 | 1.47 | 1.53 | 0% (0%) | 44.6 | 32.3 | 11.9 | 14.3 | 3425 |
| review5 | 1 | 1.47 | 1.47 | 0% (0%) | 14.7 | 9.1 | 10.1 | 13.3 | 194 |
| review6 | 1 | 1.47 | 1.47 | 3% (0%) | 14.6 | 4.1 | 13.6 | 21.0 | 427 |
