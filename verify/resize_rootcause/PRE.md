# PRE-REGISTRATION — root-cause the dangling grid-B AV (before the lease)

**Build.** SEH filter now captures fault-time registers (eax=faulting node, edi≈bucket slot) and the
handler dumps grid state: grid base/dims/stride, whether **edi is inside the 64-bucket array**
(OOB-index vs in-range), whether **eax is readable**, and a scan of all 64 buckets counting dangling
head/next pointers.

**Method.** Europolis, load zoom, gate on, **churn 8 large resizes** (2048x1152 ⇄ 1600/1920/1440/1728)
to maximise the chance of catching the intermittent fault during a grid tear-down/refill.

| the fault dump distinguishes | verdict |
|---|---|
| `edi in-grid=0` (edi outside base..base+0x100) | **OOB BUCKET INDEX** — the extent/scale produced a row/col past the 8x8 grid. Fix: clamp the index / the scale is wrong for the new extent |
| `edi in-grid=1` + a dangling head/next found in the scan | **FREED NODE** — a bucket points at reclaimed memory. Fix: ordering (repaint walks the grid mid-refill) |
| eax readable at dump time but was not at fault | a transient tear-down race — report the timing |
| no fault across all 8 resizes | intermittent + not caught this run; report and retry or accept the located-but-unrooted state |

**Deliverable:** which of OOB-index vs freed-node, with the register/grid evidence. That names the fix.
