# RESULTS — builder fill-array headroom census (2026-08-28). PRE git `1c0681c`.
# ⛔ The measurement CONTRADICTS the 16384-overflow root cause at the tested zoom. Read carefully.

Europolis (dense), `-windowed -fix16`, census at two validated-safe sizes. **No crash.** Both readings
were at **zoom = 3** (the city loaded at zoom 3 and I did not change it — this matters, see below).

| view | px | grid nodes (zoom>=3 builder) | sector recs (zoom<3 builder) | grid headroom |
|---|---|---|---|---|
| 800x600 | 480,000 | 1114 | 144 | 14.7x |
| 1280x1024 | 1,310,720 | 1692 | 144 | 9.7x |

Linear fit: `grid nodes = 780 + 6.96e-4 * area`. Extrapolated **at zoom 3**:
| view | predicted grid nodes | headroom to 16384 |
|---|---|---|
| 1600x1200 | 2116 | 7.7x |
| 1920x1080 | 2223 | 7.4x |
| **2048x1081** | **2320** | **7.1x** |
| 2560x1440 | 3345 | 4.9x |

## ⛔ This means the v3 crash was NOT a 16384 grid overflow at zoom 3
**At zoom 3, 2048x1081 predicts ~2320 grid nodes — nowhere near 16384 (7x margin).** The sector-record
proxy is flat at 144. So neither structure I can read comes close to overflowing at 2048x1081 at zoom 3.
**The earlier "root cause = fixed int[16384] overflow" (`609e97a`) is not confirmed and is contradicted
at the zoom this census ran.** I reported that root cause on the worker's static reading of the arrays
plus a plausible area-scaling story, without measuring the actual fill. The measurement disagrees.

Two live possibilities, neither settled:
1. **The v3 crash happened at a DIFFERENT zoom.** The auto-maximize hit right after load; if the view
   was at **min zoom (zoom<3)**, the active builder is `FUN_1000be25`, whose fill is the **sum of
   sector-list inner-loop iterations** — which my sector-RECORD count (144) does NOT measure. Min zoom
   shows the whole map, so its fill can be far larger. **This is the worst case and it is UNMEASURED.**
2. **`0xC000041D` = STATUS_FATAL_USER_CALLBACK_EXCEPTION is not specifically a /GS stack overrun**
   (`0xC0000409` is). It is any unhandled exception inside a Win32 callback. The v3 crash could be a
   plain access violation somewhere in the repaint chain, surfacing as a callback exception because the
   poll runs in the paint hook — **not the array overflow at all.**

## What IS established
- **At zoom 3, there is enormous headroom** — even 2560x1440 keeps the grid proxy at ~4.9x margin. **At
  this zoom a clamp is not the binding constraint** up to at least 2560x1440 on a dense city.
- The proxies are stable and scale cleanly with area (outcome 1 held for the two points), so the
  instrument works; it is the *zoom* that was not varied.

## Honest status of the clamp question
**Unresolved, and my prior answer was over-confident.** The safe clamp cannot be set from this run
because the worst case (min zoom) was never measured, and the v3 crash mechanism is now back open. What
this run DID buy: it falsified "grid-array overflow at zoom 3" as the explanation, and showed zoom-3
headroom is large.

## Next (one lease, if pursued) — force MIN ZOOM
Re-run the census with the view forced to **zoom 0** (the probe has `-resizezoom`/`g_rz_zoom`), on
dense Europolis, at 800x600 and 1280x1024. That measures the worst-case builder (`FUN_1000be25`) and
its sector-list fill. If it also shows large headroom, the 16384 story is fully refuted and the v3
crash is a plain repaint AV to be traced separately. If it climbs toward 16384, the overflow story is
rehabilitated and the clamp is a min-zoom + area limit. ⚠️ Also fix the census to count the sector-list
**inner-loop fill**, not just record count — the record count (144) is clearly not the fill.

## State
No lease held at close (released; the status showed "no lease to release" after `capture.ps1` already
freed it). Owner build verified `f5b9f1d9` / `acefadf0`. No on-disk patch. Census is `-spritecount` in
the probe (gitignored harness; this file is the record).
