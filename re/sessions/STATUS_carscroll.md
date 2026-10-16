# STATUS_carscroll (child of the orchestrator, branch child/carscroll from child/cartrips2)

Task: street agents keep animating while the camera moves (owner request 2026-10-16).

## State 2026-10-16

- Decode done (PRE.md "Known"): the scroll step SIMSPR `FUN_10043daf` passes rate 0.0 to the render view's `+0x7c`
  before its own frame; the frame `FUN_1001cab9` calls the heartbeat only while `+0x2b = rate >= 0.1`. Zoom/rotate
  need nothing (0 then 60 inside one call, no frame between).
- Code: sc3simrun `animate_while_scrolling=1` (5-byte call at SIMSPR 0x10044003), build 291dcec9. Not yet run.
- Tools: `re/tools/cs_probe.py`, `cs_run.py`, `cs_summary.py`.
- Next: commit PRE, wait for the owner's harness claim to clear, smoke K0, arms.
