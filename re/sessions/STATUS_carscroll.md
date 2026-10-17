# STATUS_carscroll (child of the orchestrator, branch child/carscroll from child/cartrips2)

## State 2026-10-16 23:25: DONE (route-car thinning fix: partly met), waiting for the owner hand test

- Harness released, no game running, keep-awake helper stopped. Games ran only in `Simcity_stock_pausetrips`.
- Part 1 (animation while scrolling): done earlier, `verify/carscroll/RESULTS.md` top half.
- Part 2 (route cars keep their count during camera moves, owner decision): staged sc3simrun 0b903bb6 (CARMARGIN 5)
  + sc3cartrips 3f9a2c82 (scroll_fill: margin capture 4, route history, strip quotas, top-up, roaming cut routes).
  Holds for the held button, gentle drags, after overscroll, arrows on the 1024 city; not for very fast sweeps
  (arrows in Berlin's centre during the scroll ~0.5, swinging drag 0.3-0.65). 0 faults; pop-ins <= 79 / min.
- Hand test: `MAIN\re\harness\handtest_carscroll\` (both DLLs + README); pictures `MAIN\verify\carscroll\owner_shots\`.
- Docs: SIM_WHILE_SCROLLING.md, STRTSIM.md 8, CAR_TRIPS.md 8. Not merged (orchestrator integrates).
- Disk: C: was 99% full during the runs (R1b, R2b, L6, V5 lost); frame dumps were deleted after the GIFs.
