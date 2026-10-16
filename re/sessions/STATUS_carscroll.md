# STATUS_carscroll (child of the orchestrator, branch child/carscroll from child/cartrips2)

Task: street agents keep animating while the camera moves (owner request 2026-10-16).

## State 2026-10-16 11:40

- Harness claimed by `carscroll` (300 min). Games only in `Simcity_stock_pausetrips`, own PIDs only.
- Decode (PRE.md + addenda): the scroll step SIMSPR `FUN_10043daf` passes rate 0.0 to the render view's `+0x7c`
  (three copies of the write, one per branch) before its own frame; the frame `FUN_1001cab9` calls the heartbeat only
  while `+0x2b = rate >= 0.1`. Zoom/rotate need nothing.
- sc3simrun `animate_while_scrolling=1`: ANIMATE (3 x 5-byte call in SIMSPR), STRIPS (view refill only on revealed
  strips), TICKSTRIP (producer tick places on the revealed strip while moving). Final build ede5732a.
- S1 (stock cars, f3d94920) passed the animation and FREEZE predictions; drag pop-ins from the producer tick led to
  TICKSTRIP (addendum 2).
- Running: `cs_queue.sh` (S2, S3, N0, C1, F2, F1, C2, L1, L2), then `cs_queue2.sh` (S1b, S3b, L3, V1o, V1r).
  Log `Simcity_stock_pausetrips\re\harness\cs_queue.log`.
- If resumed after a limit: check `harness_claim.ps1`, `tasklist | grep SC3U`, the queue log; the queues kill only
  their own PIDs (pt_run).
