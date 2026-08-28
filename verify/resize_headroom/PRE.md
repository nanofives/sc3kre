# PRE-REGISTRATION — builder fill-array headroom census (committed BEFORE the lease)

**Question.** How much view-area headroom is there to the builders' fixed `int[16384]` fill arrays,
so a resize clamp can be set on evidence rather than the conservative 1280x1024 proxy?

**Instrument (`-spritecount`, pure read, `SC3PROBE_SPRITECOUNT`).** At the periodic tick, read UPPER
BOUNDS on the fill: the 8x8 bucket-grid node count at `*(iso+0x380)` (zoom>=3 builder `FUN_1000d0f5`)
and the sector-list record count `(iso+0x4c8-iso+0x4c4)/12` (zoom<3 builder `FUN_1000be25`), with the
live extent (`iso+0x5c-0x54` x `iso+0x60-0x58`) and zoom (`iso+0x28`). Track per-run max of each.
No hook into the hot builders.

**Method.** Europolis (a dense, populated city — a genuine load, not a best case), `-windowed -fix16`,
resize 800x600 -> 1280x1024 at t+30 (both validated-safe sizes, no crash). Read counts at each size;
the two points give the area slope; extrapolate each to 16384.

**Pre-registered reads.**
- counts at **800x600** and at **1280x1024**, both builders' proxies.
- the run must NOT crash (both sizes are under the ceiling); if it does, that itself revises the safe
  set and the census is void.

**Outcomes.**
| # | reading | meaning |
|---|---|---|
| 1 | both proxies well under 16384 at 1280x1024, clean area slope | ⭐ headroom quantified; recommend a clamp = the area giving a safe margin (e.g. 70%) to 16384 |
| 2 | either proxy already near 16384 at 1280x1024 | the safe clamp is **at or below** 1280x1024; say so |
| 3 | a proxy does not scale ~linearly with area between the two points | report both points, do NOT extrapolate a single slope; recommend measuring more points |
| 4 | grid reads 0 at both sizes | the zoom is <3 so only the sector list is live; report the sector proxy alone and note the grid is a zoom>=3 structure |

⚠️ **These are UPPER BOUNDS, not the exact fill** (dedup only reduces the count). A clamp derived from
an upper bound is conservative in the safe direction. The exact fill needs a mid-builder counter, which
this run deliberately avoids. **Any pixel maximum published from this is "safe-by-upper-bound", stated
as such.**

## Install
Owner build stays live (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`). Probe drives `-windowed -fix16`; no
on-disk patch. Restore nothing beyond releasing the lease + claim.
