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

## The correction I owe — my redirection was premature
I steered off the owner's fa36 plan toward tile-cache preservation on the inference "the #1 city rendered
with grid-B type1=0, so it came from the tile cache." That inference was unsafe:
- The #1 city rendered because that run's `FUN_10018cdf` refill **ran** (it was not suppressed) and
  **populates grid B** (1537 type-2 nodes) as well as the tile cache. This run suppressed the refill and the
  render went black — so **the refill, not the tile-cache pointer, is the lever**.
- `[UNCERTAIN]` whether the #1 frame rendered from grid-B type-2 nodes or the tile cache — this run cannot
  say, because #1's zoom was not recorded and its log is overwritten. What IS certain: with the refill
  suppressed and grid B empty at zoom 3, nothing renders, and preserving `iso+0x24` does not change that.
- Consequence: the "builders gate only on type 1" simplification is **not safely load-bearing** here — the
  refill's type-2 population is implicated in what renders at zoom 3. Left as `[UNCERTAIN]`, needs a
  type-attribution run (census the builder's actual source), not asserted.

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
