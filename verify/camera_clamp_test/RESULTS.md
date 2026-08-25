# camera_clamp_test — RESULTS

Camera-specific results, split out of `verify/citysize_mod_test/RESULTS.md` because `U-081` and
`U-082` are camera questions and the 512 angle is closed. Pre-registration for everything here:
`re/sessions/PREREG_512_gameplay.md`, addendum 5.

---

# U-082, 2026-08-25. ROW V, with a caveat that matters more than the row: the premise was untestable.

**Verdict: row V — the origin is outside the valid range and the view keeps rendering. But rows T and
U could never have fired, because the origin was ALREADY out of range before the first tap.** The test
was designed to watch the origin cross a bound. It started on the wrong side of it.

**No patch. SIMDIRT `f1708fc1…b070`, install `stock` before and after.** Lease and claim released.
Fixture `Cities\Farmsville.sc3` via the new `-GamePath`, 25 filetrace lines, `MAP 192x192`,
`zoom=2 rot=0 tilepx=32`, bound `0..48896`.

**The harness fix works.** The launcher echoed `-- "C:\…\Farmsville.sc3"` — quoted, one argument.

## The tap-by-tap trajectory

15 taps dispatched, 15 `GZKEY: +0x177=1 (after)` lines, `flags 0/0/1/0` each time. Origin
(`iso+0x54/+0x58`) after each:

| reading | after | origin x | Δx | origin y |
|---|---|---|---|---|
| 1 | *load, no input* | **-722** | — | 1817 |
| 2 | tap 1 | -512 | **+210** | 1817 |
| 3 | tap 2 | -800 | -288 | 1817 |
| 4 | tap 3 | -1024 | -224 | 1817 |
| 5 | tap 4 | -1024 | **0** | 1817 |
| 6 | tap 5 | -1056 | -32 | 1817 |
| 7–13 | taps 6–12 | -1056 | **0 x7** | 1817 |
| 14 | tap 13 | -1088 | -32 | 1817 |
| 15 | tap 14 | -1088 | **0** | 1817 |
| 16 | tap 15 | -976 | **+112** | **1876** |

## ⭐ The finding that voids the design: the origin is negative AT LOAD

**Reading 1 is `-722`, before any input at all.** The valid range is `0..48896`. So on this map the
camera is **already outside it the moment the city finishes loading**.

> **"Unclamped scroll walks the origin off the map" cannot be what happens here, because the origin
> starts off the map.** Scrolling is not what put it there.

Rows T and U are therefore **unreachable** — there was no bound crossing to observe. Reported rather
than reshaped into a row that looked answerable.

## ⭐ And the load-time camera is NON-DETERMINISTIC

Same save, same `zoom=2`, same path-load, two runs on 2026-08-25:

| run | load-time origin |
|---|---|
| the N=192 control | `1356, 266` |
| this run | **`-722, 1817`** |

**Not the same starting point, not even the same sign.** This is a problem for the whole
investigation, not just this run:

> **Every before/after camera measurement made here assumed a stable load-time origin. That
> assumption is false on Farmsville.** The three-arm Craterville control is unaffected — its A and B
> readings are inside one process — but any comparison across processes, including the earlier
> `1356,266 -> -913,-483` "unclamped scroll" reading, is now suspect. That reading may have been the
> load position differing, not scrolling.

The three-arm within-process design was the right instinct for exactly this reason, and this is the
second time per-process variation has bitten a cross-run camera number.

## Motion is erratic, and there IS a dead stretch — but it recovers

Per-tap Δx: `+210, -288, -224, 0, -32, 0, 0, 0, 0, 0, 0, 0, -32, 0, +112`.

- **Two taps moved the origin the WRONG WAY** (`+210`, `+112`) for a left-arrow.
- **Seven consecutive taps (6–12) moved it not at all** — which is the shape of "stops responding".
- **Then it moved again** (tap 13, `-32`), so the stop was **not permanent**.
- `y` was frozen at `1817` for fourteen readings and then moved `+59` on the last tap.

So the symptom "works, then stops" has a partial match — a run of unresponsive taps — but it is
**intermittent, not terminal**, and it coexists with movement in the wrong direction, which no clamp
explains.

## The view did NOT stop rendering

The final frame (`u082_walk_115454.png`) shows the **map edge**: terrain and water across the
upper-left, the brown terrain cross-section forming a cliff, and flat off-map void to the lower right.
Trees, water, the shoreline, the toolbar, the status bar (`Farmsville, Pob: 36,172, §45,724,
5/16/1904`, `Simulación en pausa`) and the minimap with its camera rectangle at the diamond's corner
are all drawn correctly.

**That is a coherent picture of a camera parked off the map corner, not a frozen or black view.** So
with the origin at `-1088` — the entire 1024-wide viewport left of world x = -64 — **rendering
continues.** Row V.

### But "the view kept rendering" is weaker than it sounds, and here is why

`[UNCERTAIN]` **I could not observe the view per tap.** `capture.ps1` writes one shot at the end, and
the blit-rate proxy was unavailable in the window that mattered:

`raster_blit_hw` heartbeats came at t=5.66 s (1,008), t=11.11 s (15,495) and t=16.55 s (47,329) — and
**all 15 taps landed between t≈16.6 s and t≈20.2 s.** `key:` does not wait for its own hold, so the
whole tap phase compressed into ~3.7 s, **shorter than the ~5.45 s heartbeat interval.** No heartbeat
fell inside it.

**My design error, and the fix is obvious:** interleave `wait:` between taps so the tap phase spans
several heartbeats, at the cost of taps against the 32-step budget. Row W applies to the per-tap
question even though row V applies to the endpoint.

## Which rows fired

| row | status |
|---|---|
| T — stops as the origin crosses the bound | **unreachable**; the origin began out of range |
| U — stops before leaving the range | **unreachable**, same reason |
| **V — out of range and the view keeps working** | **FIRED**, on the endpoint frame |
| W — cannot tell whether the view stopped | **also applies**, per tap |
| X — uniform step, never approaches a bound | no — the steps were erratic, not uniform |

## What this means for U-082

**The clamp hypothesis is not confirmed and not cleanly dead — it is bypassed.** The origin is out of
range at load and the view renders anyway, so "origin leaves the map ⇒ view dies" is contradicted at
the endpoint. The owner's progressive symptom is most likely a third thing.

**What would settle it,** in priority order:

1. **A stationary-load fixture.** Nothing about the camera is measurable across runs until the
   load-time origin is reproducible. Establish which maps load deterministically, or read and log the
   saved camera from the `.sc3` so the expected origin is known before launch.
2. **Per-tap view evidence.** Taps spread across heartbeats so the blit rate is sampled inside the tap
   phase, or a shot requested per tap.
3. **The `FUN_10006226` counter** (spec in addendum 4). "Seven taps moved nothing" has two readings —
   never called, or called and the delta discarded — and the counter separates them. It would also
   explain the two wrong-direction taps, which no clamp accounts for.

## By-product

`MAP 192x192` and extent `48896` reproduced exactly, a fourth confirmation of `(N-1) * 0x100` across
192 / 256 / 512.
