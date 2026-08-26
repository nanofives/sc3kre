# PRE-REGISTRATION — U-068 rect-push fix attempt (committed BEFORE any run)

Owner: resizefix session. Committed to git before the lease is taken, so git supplies the
tamper-evident timestamp (BOARD standing rule). Date 2026-08-26.

## The claim under test
The post-resize black iso viewport is caused by the iso view's per-frame present having an **empty
persistent rect list** at `iso+0x4d0`, which Init `FUN_10005b42` erases and nothing repopulates. The
proposed fix: after Init, replay the ctor's single push_back of `{0,0,new_w,new_h}` into `iso+0x4d0` via
`FUN_10010586` (using Init's new dims at `iso+0x5c`/`iso+0x60`), which the mechanism analysis says
**persistently** restores per-frame presentation (`STATUS_resize.md`, mechanism section, all `[CONFIRMED]`).

## The instrument (what the harness will do)
Within-process three-shot A/B, same city/camera/window across all three (the §31.12 pattern), gated on
`SC3PROBE_RESIZE_PUSHRECT=1`:

- **Shot A** — pre-resize, in-city, the instrument control (must render Europolis, as always).
- **Shot B** — post-resize control. `rz_iso_resize` runs normally (Init, tile refill, **redraw kept** so
  `iso+0x74` is rasterised) **but the harness `FUN_1000e206` full present is suppressed.** Redraw's own
  `flush → FUN_1000e058` presents the **empty** (Init-erased) `iso+0x4d0`, i.e. a no-op — so the render
  target holds the city yet nothing blits it. Expected **black**: the defect reproduced through the exact
  list path being fixed.
- **Shot C** — post-resize, phase C **pushes** `{0,0,w,h}` into `iso+0x4d0` (`FUN_10010586`, advancing
  `end`), then drives **`FUN_1000e058`** directly (the game's own incremental present) which blits
  `composite.vt[0x120](iso+0x74, rect, rect)` for that rect. Expected **city**, if the empty list was the
  whole defect.

**Why keep redraw but suppress only the full present.** Redraw `FUN_1000b4b3` **rasterises the display
list into `iso+0x74`** — suppressing it would leave the render target empty and `FUN_1000e058` would blit
black, a false negative. The list-independent full present `FUN_1000e206` is the only paint that would
show the city *without* the rect list, so it alone must be gated off for B to be a valid black control and
for C's city to be attributable to the push. The ONLY presenter that reaches the screen with the city is
then `iso+0x4d0` → `FUN_1000e058` → composite. The blit-source census (`SC3PROBE_U068SRC`) watches whether
`iso+0x74` (or its `+0x44` sub) becomes a blit source in the C window.

Logged every phase: `iso+0x4d0`/`+0x4d4` (vector begin/end → count), `iso+0x7c`, `iso+0x524`, and the
census match/no-match with the source-pointer inventory.

## Outcomes, committed in advance

| Shot C (rect pushed, list path only) | conclusion |
|---|---|
| `iso+0x4d0` count 0→1 after push, census shows `iso+0x74`/sub as a live blit source, **screen shows the city** | **FIX CONFIRMED.** The empty rect list was the defect; restoring it restores presentation. The mechanism is not merely a confirmed path — the field I changed is the one that was preventing the blit. |
| count 0→1, **but census shows 0 iso blits and screen still black** | the rect-push is **insufficient**: the game frame loop is not reaching `FUN_1000e058` post-resize (residual (c)), or a further gate exists. Report as a refutation of the single-push fix; the defect is upstream of the list. NOT a fix. |
| count 0→1, census shows the blit, **but screen still black** | the blit reaches the composite yet not the screen — a composite→primary (flip/Present) problem downstream of the fixed blit. Distinct defect; report, do not claim the fix. |
| push_back faults / `end` not advanced / count stays 0 | instrument error (wrong call shape — must be `FUN_10010586`, not an in-place `*begin` write). VOID; fix the call, do not interpret. |

| Shot B (no push, engine-paint) | required for the run to be valid |
|---|---|
| black, census 0 iso blits | the control reproduces the defect through the path under test → C is interpretable. |
| **not black** (city renders with no push) | the engine-paint path presents without the rect — the premise is wrong or paint-hack suppression failed. VOID C; report B as the finding. |

| Shot A (pre-resize control) | |
|---|---|
| Europolis renders in full | instrument sound. |
| black/empty | capture path broken; ABORT, nothing about the fix concluded (same rule as every prior run). |

## What makes the run VOID rather than a result
- No shot A city frame → capture path unproven → nothing interpretable.
- Shot B not black → the one-variable delta is broken (paint hacks not actually suppressed, or the
  engine paints without the list). Report B, do not interpret C.
- Any `FUN_10010586` fault or `end` not advancing → VOID, instrument bug.

## Reported whatever happens
`iso+0x4d0` count and `iso+0x7c`/`iso+0x524` at each phase; the census source inventory for B and C;
the three BMPs' verdict (city vs black) by direct view; whether the UI also reflows (it will not —
that is item 2, `FUN_100270e5`, a separate defect).

## Provenance / config
Fix-off baseline except the rect-push under test. **Stock SIMSPR restored before the run** (it carries
the iso view; a modified copy is not neutral for a render measurement) and **re-staged to the owner's
two-recipe build after** (BOARD standing rule; `--diff` gate 7 runs / 12 bytes). Own game lease and own
harness claim (hunk-merge into `sc3probe.c`, `re/harness/` is gitignored). **`-AtSec` under 800** until
the `capture.ps1` `-Minutes 15` lease-duration bug (BOARD `9e8d4d4`) is fixed; treat a `STALE` lease as
"check for a live process", never as free. Europolis via bare absolute path, 1024x768 → 1280x1024.
`SC3PROBE_U068SURF`/`U068SRC`/`U068SHOT` armed; new gates `SC3PROBE_RESIZE_PUSHRECT` and the
paint-hack-off switch. Probe sha256 recorded in the run log.

## STATUS
Design complete, pre-registered, committed. **Not built, no lease.** Build pending the harness claim
(held by a sibling at write time) and the orchestrator's go / any redirect on the run shape.
