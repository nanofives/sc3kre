# RESULTS — #3 tile-cache preservation A/B (2026-08-26). PRESERVATION REFUTED; the refill is the lever.
# And it corrects my own earlier redirection.

**Verdict: the pre-registered "C black" branch landed — restoring the `iso+0x24` pointer did NOT render.**
Tile-cache-pointer preservation is **insufficient**. The run also pinned the reachable zoom at **3**, which
is the **grid-B** render path, not the tile cache — so my earlier "type1=0 → tile cache" redirection was
premature. The lever that actually renders a resize is the bridge's whole-map refill `FUN_10018cdf`.

## Provenance
- Probe `sc3probe.dll` sha256 `869ef7fe7d2fb24b6a43f49b06bbfd21fa7a1c3b480d355735ed3699f4c1079a`
  (278528 b), new verb `SC3PROBE_RESIZE_TILECACHE`. **STOCK SIMSPR** (scroll 32.0 verified). Europolis,
  `-nocom -windowed -fix16 -fitclient -nointro -quiet`, `RESIZETO=1280x1024 RESIZEAT=22 U068SURF=1
  U068SHOT=1 RESIZE_TILECACHE=1`, `-AtSec 100`. Own lease + own harness claim. Log `capture.log`.
- Owner's three-recipe gentle build re-staged + verified LAST (sha `e63ec800`, 8/9). Lease + claim released.

## The measurements — render-target census (iso+0x74, raw sub+0xf0, the direct read)
| phase | iso+0x24 | grid B | render target iso+0x74 |
|---|---|---|---|
| A pre-resize control | populated | (loaded) | **99% non-zero, image** (`capture.log:634`) |
| B post-resize, refill SUPPRESSED | empty (Init realloc 0x0F1D3288) | **empty, nodes=0** | **0%, ENTIRELY UNIFORM** = black (`:1004`) |
| C `iso+0x24` restored (0x0F1D7308) + redraw | restored (old, populated) | **still empty, nodes=0** | **0%, ENTIRELY UNIFORM** = black (`:1034`) |

The `TILECACHE` lifecycle fired correctly: SAVED `iso+0x24=0x0F1D7308` before Init (`:949`), refill
SUPPRESSED (`:974`), restored to `0x0F1D7308` in phase C (`:1027`). Shot C viewed: iso viewport black, only
the HUD + loading box visible (`.happy-share/…/tilecache_shot_C_restored.png`).

## Why C stayed black — the zoom-3 diagnosis
`iso+0x28 = 3` (`:940`), and the documented split (`sc3probe.c:5555`) is: zoom < 3 renders via the tile
cache `iso+0x24` (`FUN_1000be25`), **zoom ≥ 3 via grid B `iso+0x380` (`FUN_1000d0f5`)**. At zoom 3 the
render enumerates **grid B**, which was **empty** (nodes=0) because the `FUN_10018cdf` refill was suppressed
and nothing else fills it. So the render target is black **regardless of the tile-cache pointer** — restoring
`iso+0x24` cannot help a path that reads grid B. Grid B stayed `nodes=0` through phase C (`:1045`).

## The correction — BOTH specific mechanisms were wrong; only the shared premise survived
Two wrong specific calls, stated so no future reader trusts either instinct over a measurement:
- **My redirection (tile cache) was wrong** — restoring `iso+0x24` rendered black.
- **The earlier fa36 call (`FUN_1000fa36`, grid-B type-1) was ALSO wrong** — the lever is `FUN_10018cdf`,
  a distinct 6,959-byte routine. Init `FUN_10005b42` contains **zero references to `FUN_10018cdf`**
  (verified), consistent with Init zeroing grid B and something else entirely refilling it.
- **What survived is only the shared premise: grid B matters at this zoom.** The specific refill is
  `FUN_10018cdf` (the bridge whole-map fill), not fa36 and not the tile cache. The #1 city rendered because
  that run's `FUN_10018cdf` refill **ran** (it populates grid B); suppress it and the render goes black.
- `[UNCERTAIN]` whether the zoom-3 frame sources grid-B type-2 or the tile cache — needs a builder-source
  type-attribution run; the "builders gate only on type 1" simplification is not safely load-bearing here.
- `[UNCERTAIN]` #1's actual zoom. ⚠️ **Recoverability gap:** #1's `capture.log` was overwritten by this run,
  so its zoom is unrecoverable. The probe-SHA-in-log fix exists precisely because unrecoverable run identity
  has burned this project before; per-run logs should be archived (not just the probe SHA) when a later run
  will overwrite them, or the comparison cannot be re-derived.

## What this DOES establish for #3
- The reachable/default Europolis zoom is **3** → the **grid-B** render path.
- A resize renders correctly only when the bridge whole-map fill **`FUN_10018cdf`** is re-driven (it
  repopulates grid B). The harness does this (#1 → city); the game's real `WM_SIZE`→vt+0x30 does not.
- **Neither tile-cache-pointer preservation NOR fa36 type-1 re-register alone is the answer at zoom 3.**
  The corrected minimal iso routine is: render-target resize + **`FUN_10018cdf` refill** + present.
- Init's `iso+0x24` realloc is still a needless discard of a resolution-independent structure, but
  preserving it does not by itself make a resize render — so it is a cleanliness point, not the fix.

## STATUS
Preservation refuted (pre-registered branch). Zoom-3 / grid-B / refill-is-the-lever established. The
minimal-routine target is corrected to the `FUN_10018cdf` refill. No new build; lease + claim released;
gentle build live. Two `[UNCERTAIN]`s named (builder source type at zoom 3; #1's zoom).
