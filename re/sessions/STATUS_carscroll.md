# STATUS_carscroll (child of the orchestrator, branch child/carscroll from child/cartrips2)

Task: street agents keep animating while the camera moves (owner request 2026-10-16).

## State 2026-10-16 15:40: DONE, waiting for the owner hand test

- Harness released, no game running, keep-awake helper stopped. Games ran only in `Simcity_stock_pausetrips`.
- sc3simrun `[sim] animate_while_scrolling=1` (default on; 0 = today, no patch installed). Final build 5eaa8a2e:
  ANIMATE (scroll step's three rate writes, SIMSPR 0x10043de7/0x10043f60/0x10044003, now 60), STRIPS (view refill only
  on revealed strips, STRTSIM FUN_1001f040 entry), TICKSTRIP (producer tick FUN_1001f44a runs on the revealed strip or
  is skipped while the camera moves).
- Results `verify/carscroll/RESULTS.md`: works for drag, held button, arrows, overscroll; edge scroll not drivable by
  the tools (owner check); zoom/rotate need nothing; FREEZE wins; 0 faults incl. 4 soaks. Frame rate unchanged with
  the 60 fps cap (owner set), 83-93% of today without it. Stock cars: 0 on-screen pop-ins during moves. Route cars:
  street thins during long drags (known limit, reported).
- Hand test: `MAIN\re\harness\handtest_carscroll\`; pictures `MAIN\verify\carscroll\owner_shots\`.
- Not merged (orchestrator integrates). Docs touched: SIM_WHILE_SCROLLING.md, STRTSIM.md section 8.

## State 2026-10-16 17:25: route-car thinning fix (owner decision), arms running

- Decode + baseline B0 (addenda 7, 8): routes end at the old view edge; spawns pop and waste routes; the 2-cell car
  rect deletes cars just off screen on every camera step; supply 3 routes/s cannot refill.
- Fix: sc3simrun CARMARGIN (car rect = view + 8, build 74901709) + sc3cartrips scroll_fill (margin capture, route
  history, strip quotas off screen, roaming cut routes; build 053963fa). Run-time switch X0/X1 for the A/B.
- Queue `Simcity_stock_pausetrips\re\harness\cs_qR.sh`: R1 (Berlin), R2 (1024), C4 (FPS), L5 (soak), V4 (pictures).
  Harness claimed by carscroll until ~23:20; keep-awake helper running (stop it when done).
