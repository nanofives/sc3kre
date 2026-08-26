# PRE-REGISTRATION — #3 tile-cache preservation A/B (committed BEFORE the run)

Owner: resizeship session. Committed to git before the lease (BOARD standing rule). Date 2026-08-26.
Owner-approved witness (chose "tile-cache preservation A/B" over the fa36 grid-B route after the census
evidence below).

## Why this and not the fa36 route
The reachable/tested resize renders through the **tile cache `iso+0x24`** (zoom < 3, `FUN_1000be25`), NOT
grid B / fa36 (zoom ≥ 3, `FUN_1000d0f5`). Evidence, from existing logs, no lease spent:
`capture.log:1082` — the shot-C frame that rendered the full city had grid-B **type1=0** (type2=1537);
since both display-list builders gate on type 1 (owner's rule), grid B contributed nothing drawable, so
the city came from the tile cache. `sc3probe.c:5555-5557` documents the zoom split. `u068fix3.log` shows
fa36 refills grid B (type1 0→213) but that is the zoom ≥ 3 path (reachability unestablished, D-003).

The tile cache `iso+0x24` is sized by **map tiles (256×256), resolution-independent** — it does not change
on a pixel resize. Yet Init reallocs+zeroes it every call (`FUN_10005b42:203-235`, no free — it LEAKS the
old grid), discarding live content for no dimensional reason. **That realloc is the stale-state defect for
the reachable path.** A minimal Init-free routine would simply not realloc it. This run isolates exactly
that.

## The instrument (probe `869ef7fe…`, new verb SC3PROBE_RESIZE_TILECACHE)
Single variable = the `iso+0x24` pointer. Same harness Init resize (proven; it does the render-target
recreate, e2c0, ee29 correctly), only the tile cache differs:
- rz_iso_resize **saves** `iso+0x24` before Init; Init reallocs it empty (old one leaked, still valid).
- The `FUN_10018cdf` tile refill is **SUPPRESSED**; sprite caches untouched. So shot B renders the EMPTY
  cache. `FUN_1000e206` full present RUNS (NOT suppressed — unlike pushrect), so the render target reaches
  the screen.
- Phase C **restores** `iso+0x24 = saved`, then redraw + `FUN_1000e206` present. Shot C.
- Primary witness is the direct render-target census (`U068SURF` raw `sub+0xf0` on `iso+0x74`) at B and at
  C; the shots are confirmation.

## Outcomes, committed in advance

| Shot B / census B_post_resize (empty cache, refill suppressed) | conclusion |
|---|---|
| **BLACK / render target uniform-low** | the empty cache renders nothing → the stale-state defect reproduced through the exact structure Init discards. Required for a valid A/B. |
| city / render target 99% image | the empty cache still rendered → the game auto-refilled `iso+0x24`, or rasterisation does not use it → premise wrong. Report; do NOT interpret C as preservation. |

| Shot C / census C_tilecache_restored (cache restored, redraw) | conclusion |
|---|---|
| **full CITY / 99% image at 1280x1024** | the resolution-independent tile cache SURVIVES a resize untouched; Init's realloc is the whole defect. **A minimal routine that preserves `iso+0x24` renders correctly with no refill** — validates the #3 iso-side for the reachable zoom. |
| BLACK / uniform | restoring the old cache did NOT render → the preserved cache is insufficient (stale coordinate mapping, or content invalid at new size). Report; preservation NOT sufficient alone. |
| stale (old-resolution framing) or partial (only newly-exposed region) | the interesting failure the owner flagged — report which, with the census pitch vs w*bpp. |

| Shot A (pre-resize control) | Europolis in full → instrument sound; black → capture path broken, ABORT. |

## VOID conditions
- Shot A not a city frame → capture path unproven → VOID.
- No `TILECACHE A/B: SAVED iso+0x24` line, or restore SKIPPED → the verb did not arm → VOID.
- B not black (auto-refill) → the A/B has no contrast → report B as the finding, do not claim C.

## Reported whatever happens
`iso+0x24` before/after Init and after restore; the B and C render-target censuses (nonzero %, uniform);
the three shot verdicts by direct view; grid-B type-split census at each stage (to confirm grid B stays
type1=0, i.e. the render is the tile-cache path). HUD will not reflow (item 2); upward-only (U-069).

## Provenance / config
**STOCK SIMSPR** for the measurement (it carries the iso view; the resize renders via `FUN_1000e206`, so the
resize_rectfix cave is NOT involved and is NOT staged here). Owner's three-recipe gentle build re-staged +
verified as the LAST action (BOARD standing rule, `--diff` 8/9). Env `SC3PROBE_RESIZE=1 RESIZETO=1280x1024
RESIZEAT=22 U068SURF=1 U068SHOT=1 SC3PROBE_RESIZE_TILECACHE=1` (NOT pushrect). `-AtSec` under 800. Own lease
(`resizeship`); own harness claim (probe rebuilt, sha `869ef7fe…`). Probe/DLL shas in the run log.

## STATUS
Pre-registered. Probe BUILT (`869ef7fe7d2fb24b6a43f49b06bbfd21fa7a1c3b480d355735ed3699f4c1079a`, 278528 b).
**Not yet run — no lease until this PRE.md is committed.**
