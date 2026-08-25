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

---

# U-082 pure null, 2026-08-25. ROW AB: pull-back is DEAD. And the field itself is not trustworthy.

Pre-registration: `re/sessions/PREREG_512_gameplay.md`, addendum 6.

**Verdict: row AB. With ZERO input the origin moves non-monotonically by thousands of pixels. A
restoring force does not oscillate, so the soft-clamp / pull-back hypothesis is dead.**

**And a bigger result underneath it: the frame contradicts the last reading, so `iso+0x54..+0x60` is
not reliably the live camera on this fixture.**

No patch; SIMDIRT `f1708fc1…b070`, install `stock` throughout. Locks released.

## Validity checks first — all four pass, so this is not a garbage read

| check | result |
|---|---|
| keys dispatched | **0** — `grep -c GZKEY` = 0. No input of any kind. |
| object identity | **same address all 15 reads**: `cell map found at cityViewIso+0x158 -> 0x0EEA4A68`, 15/15. Not a realloc, not a different object. |
| structural sanity | `span=1024x768` on **30/30** rect prints (rectA and rectB). The rects are intact, not garbage. |
| fixture | Farmsville confirmed, 25 filetrace lines; `MAP 192x192`, extent `48896`; `zoom=2 rot=0 tilepx=32` |

## The no-input trajectory

Fifteen `cam` reads, ~1.12 s apart, no input:

| # | t (ms) | origin x | Δx | origin y |
|---|---|---|---|---|
| 1 | 16625 | -160 | — | 1604 |
| 2 | 17813 | 100 | +260 | 1604 |
| 3 | 18938 | 505 | +405 | 93 |
| 4 | 20063 | -1020 | -1525 | -128 |
| 5 | 21187 | -1797 | -777 | 228 |
| 6 | 22313 | -1720 | +77 | 1765 |
| 7 | 23439 | 952 | +2672 | 1752 |
| 8 | 24563 | 2030 | +1078 | 616 |
| 9 | 25687 | -690 | -2720 | -566 |
| 10 | 26815 | -1790 | -1100 | 975 |
| 11 | 27939 | 88 | +1878 | 523 |
| 12 | 29062 | -1263 | -1351 | -239 |
| 13 | 30188 | -1297 | -34 | -226 |
| 14 | 31313 | -2469 | -1172 | 871 |
| 15 | 32438 | -2396 | +73 | 282 |

**Derived, per the rate rule fixed in advance:**

- **mean |Δx| = 1,080 px per interval; mean rate 959 px/s; peak 2,720 px in one interval (2,420 px/s)**
- **6 sign changes in 13 transitions** — it oscillates, it does not converge
- **net x: `-160 -> -2396`, i.e. 2,236 px FURTHER out of bounds over 15.8 s** — the opposite of a pull
- **1 of 14 deltas is a multiple of 32** (`-2720`), consistent with chance

Neither a creep, nor a snap, nor a restoring force. **Row AB.**

## What survives of the two-mechanism reading, and what does not

**Survives:** the quantisation split. This no-input mechanism is **not** step-quantised (1/14 multiples
of 32, i.e. chance), which is consistent with the addendum-5 observation that leftward, key-driven
deltas were exact multiples and the others were not. **Two mechanisms is still the right shape.**

**Does not survive:** the *direction*. Mechanism 2 is **not** a pull toward the map. It oscillates and
its net movement is further out of bounds. So "pull-back exceeded the tap" and "pull-back cancelled the
tap" are not the explanation for the reversals and the seven zeros — though an undirected disturbance
of this amplitude would produce both by chance, which is a weaker but sufficient account.

## ⭐ The frame falsifies the reading, and this is the important part

The final sample is `x = -2396`, far outside `0..48896`. **The frame taken moments later shows a normal
in-map view** — dense zoned blocks, roads, rail, pylons, trees, and the status bar
(`Farmsville, Pob: 36,172, §45,724, 5/16/1904`, `Simulación en pausa`). It is coherent and sharp.

Compare the addendum-5 endpoint, where the origin read `-976` and the frame **did** show the map edge
and off-map void. There, field and picture agreed. Here they do not.

> **A camera at x = -2396 cannot render the picture that was rendered.** So on this fixture
> `iso+0x54..+0x60` is being written **transiently** — set and restored inside a rendering pass — and
> `cam` is sampling it mid-flight rather than reading a persistent camera position.

### Consequence, and it reaches backwards

**Two findings collapse into one.** The "load-camera non-determinism" reported in addendum 5
(`1356,266` vs `-722,1817`, and now a third value `-160,1604`) is **not** three different load
positions. It is three samples of a quantity that is being rewritten continuously. Same phenomenon,
one cause.

**And every two-point camera delta taken on Farmsville is void**, not merely suspect: the `-2269,-749`
whose attribution was already withdrawn, and the `-913,-483` out-of-bounds reading that **motivated
`U-082` in the first place.**

**What is NOT void:** the three-arm Craterville control. Its A and B reads were **byte-identical**
(`1984,1344,3008,2112` twice) and its C differed by exactly one step. A field being rewritten at
~1,000 px/s cannot produce two identical reads 3.3 s apart. **So the field is stable on Craterville and
unstable on Farmsville**, and the `-32` single-step result — the basis of the `U-081` answer — stands.

The baseline's `-6848` was also measured on a stable-looking pair with rectB agreeing, so it is not
impugned either.

## The next diagnostic, and it is cheap and specific

**`cam` takes the FIRST object it finds with vtable `SIMSPR+0x6250c`, and stops.** The minimap is also
a city view and would also own a cell map. If more than one such object exists, `cam` may be reading a
**render-scratch or minimap** cell map rather than the main view's — which would explain wandering
values, a coherent frame, and why Farmsville and Craterville differ.

**One-line probe change, no new mechanism:** make `cam` enumerate **all** matches instead of breaking on
the first, and log each with its offset and address. If two objects appear, the whole camera series in
this investigation needs re-reading against the right one.

That check should come **before** the `FUN_10006226` counter. A counter on the scroll function is
uninterpretable while it is unknown which object's rect is being observed.

## Which rows fired

| row | status |
|---|---|
| Y — moves toward the range with zero input | **no** — net movement is away |
| Z — stationary out of bounds | **no** — mean 1,080 px per interval |
| AA — moves away | partly: net is outward, but not monotonically |
| **AB — non-monotonic, not a clamp** | **FIRED** |
| AC — load position in bounds, no OOB start | **no** — `x = -160` was out of bounds at the first read |

## Status of U-082

**Dead hypotheses:** origin off-map ⇒ view dies (falsified by the addendum-5 frame); soft-clamp /
pull-back toward the map (falsified here).

**Live and unresolved:** the owner's progressive symptom. Nothing measured so far reproduces "works,
then stops" in a controlled way, and **the instrument now needs repair before more runs**: identify
which cell-map object `cam` should read, on a fixture whose field is stable (Craterville, not
Farmsville).

---

# Cell-map enumeration run — PRE-REGISTRATION, written before the launch, 2026-08-25

The instrument change under test: `cam` no longer stops at the first object carrying vtable
`SIMSPR+0x6250C` (`cISC3CitySpriteCellMap`). It walks both bases (`cityView`, `cityViewIso`) over
their first `0x280` bytes, de-duplicates objects reachable through two fields, prints **every**
candidate with the base+offset it was found at, its `rectA`, `span`, `zoom`, `tilepx`, marks the one
it uses `<== USED`, and shouts when more than one exists. It still uses the first, so every earlier
reading in this file stays comparable.

Fixture: `Cities\Farmsville.sc3` (N=192) — the fixture whose origin churned at ~1,000 px/s. Several
`cam` reads, **no input of any kind**, plus one frame. Install stock at claim time
(`game_lock.ps1 -Status` = "stock (matches original/)").

| row | prediction | what it would mean |
|---|---|---|
| **AD** | `N > 1` candidates | the first-match ambiguity is **real**. Payoff: decide which candidate's `rectA` is consistent with the rendered frame, and that identifies the correct object — retro-fitting the whole camera investigation. |
| **AE** | `N == 1` candidate | the first-match theory is **DEAD**. Stated plainly: it was a fix for a hypothesis, and falsification is the useful outcome. The churn then has another cause (field genuinely observed mid-write, or a live interpolation). |
| **AF** | `N > 1` but **every** candidate churns | ambiguity real but insufficient to explain the churn. Both reported, neither claim promoted. |
| **AG** | candidate count **varies between reads in one process** | objects being created/destroyed under the observer. Reported as such. |

**Free side-measurement, registered now:** `span` printed `1024x768` on every read of 2026-08-25. If
the origin moves ~1,000 px while the span stays exactly constant, the motion is a **rigid
translation, not corruption** — that is evidence about what writes the field. Whether `span` ever
varies is recorded either way.

---

# RESULT — **ROW AE FIRED. The first-match theory is DEAD.**

`N == 1` on **every** read. There is exactly one object carrying vtable `SIMSPR+0x6250C` reachable
from `cityView` or `cityViewIso` within `0x280` bytes, it is at the same base+offset and the same
address on all seven successful reads, and the `!! N objects` warning never fired.

**Stated plainly: the minimap-cell-map hypothesis is falsified.** The enumeration fix was built to
catch an ambiguity that does not exist in this process. It stays in (it is now the thing that proves
the object is unique instead of assuming it) but it explains nothing about the churn, and the
"`cam` may be reading the minimap's cell map" line in the section above is retracted. Whatever moved
the origin on 2026-08-25 moved **the** cell map, not a second one.

## The candidate blocks, verbatim — all eight reads, no input (`grep -c GZKEY` = 0)

```
[ 5272.617 ms] ### CAM: no object with vt SIMSPR+0x6250C (0x034F250C) reachable from cityView 0x0F4DC950 or cityViewIso within 0x280 bytes - not reading camera state from an object we cannot identify
[ 6641.149 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[ 8032.372 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[ 9399.914 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[10773.465 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[12205.294 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[13459.899 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[14585.137 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEBCD68  rectA=1776,1209,2800,1977 span=1024x768  zoom=2 tilepx=32   <== USED
```

`rectB` equalled `rectA` on all seven reads. `zoom=2 rot=0 tilepx=32`, `presentGate(+0x7c)=0`,
`flag(+0x32c)=0` on all seven.

Validity: `Farmsville.sc3` opened at t+1.81 s and again at t+2.96 s, 329 filetrace lines; 0 keys
dispatched; 152 windows walked by the closing `dump`. `MAP dimensions UNAVAILABLE` on every read —
the occupant bridge was not captured this run, so **N was not confirmed from memory**; the fixture is
established by the filetrace and by the status bar reading `Farmsville  Pob: 36,172  45,724
5/16/1904` in the frame.

## Row AG also fired, in a narrow and benign form

The count is not constant across the run: **0 on the first read (t+5.27 s), then 1 on all seven
later reads.** The object comes into existence between t+5.27 s and t+6.64 s, while the city is
still loading, and never multiplies afterwards. That is object creation during load, not churn, and
the enumeration's refusal to read anything at t+5.27 s is the fix behaving correctly — the old code
would also have found nothing there, but nothing in the log would have said why.

## The churn did NOT reproduce, and that is the finding

Six consecutive reads spanning **t+6.64 s to t+13.46 s — 6.8 seconds — are byte-identical**
(`-160,1604,864,2372`). Then one jump to `1776,1209,2800,1977` at t+14.59 s: `dx = +1936`,
`dy = -395`, neither a multiple of 32.

Set against the earlier Farmsville series (fifteen reads, t+16.6 s to t+32.4 s, mean |dx| 1,080 px
per interval, zero repeats), this run's first six reads are the opposite behaviour **on the same
fixture and the same field**. Two facts about the difference are on the record and neither is
explained:

- **The load-time origin is reproducible.** `-160,1604` here is byte-identical to read #1 of the
  earlier series (`-160`, `1604`). The addendum-5 claim of a non-deterministic load-time camera is
  not supported by this run.
- **The reads that were stable are the early ones.** Every stable read here is at t < 13.5 s; every
  churning read in the earlier series is at t > 16.6 s. This run stopped at t+14.6 s and so did not
  sample the window where churn was previously seen. **I did not measure whether the churn is still
  there after t+16 s** — one game run, and it went to the enumeration question.

A correlation, offered as a correlation only: `SHOT #1` completed at t+14.03 s, between the last
stable read (t+13.46 s) and the jumped read (t+14.59 s).

## `span` never varied — the motion is a rigid translation

**`1024x768` on 14/14 rect prints (7 x `rectA`, 7 x `rectB`).** Combined with the earlier series
(30/30) that is **44 consecutive rect prints at exactly `1024x768`**, across origin excursions of
thousands of pixels. The rects are being *translated*, not corrupted: whatever writes the field
writes all four edges consistently, which is exactly the signature of `FUN_10006226` (it adds
`param_1` to both lefts and rights and `param_2` to both tops and bottoms, `:61-68`, so the span is
invariant by construction) [CONFIRMED @ 0x10006226]. Random memory damage does not preserve a span
44 times running.

## The frame, and what it can and cannot settle

Frame: `.happy-share/cmsysyj1a0rivn51c47lbyf3l/camenum_122429.png` (from `re/harness/shot_02.bmp`,
1024x768, mirror window t+15.09 s to t+15.25 s — so it postdates the last read, `1776,1209`, by
0.67 s and is the frame for that read, not for the six stable ones).

**Which candidate matches the picture: not applicable — there is only one candidate.** The payoff
registered under row AD cannot be collected, because the ambiguity it was meant to resolve is not
there.

What the frame does show, and it is consistent rather than contradictory: land in the lower-left,
off-map grey filling the upper-right, a map boundary running diagonally between them and the map's
edge cliff at screen x = 860. The game's **own** camera indicator agrees — the minimap's red
rectangle sits at the east side of the diamond, overhanging its edge. Both say "parked at a map
edge with off-map space in view", which is what an in-range-but-peripheral origin looks like. This is
a qualitative agreement; I did **not** derive the world-pixel-to-screen projection, so I cannot
convert `1776,1209` into an expected pixel and check it numerically.

**One arithmetic observation that bears on every out-of-bounds judgement in this file.** All 14 rect
values in this run lie inside `0..6144` by `0..3072`, and `6144 = 192 x 32 = N x tilepx`,
`3072 = N x tilepx / 2` — the iso diamond's own pixel extent at `zoom=2`. The `0..48896` range this
investigation has been testing against is SIMGEOM's `(N-1) x 0x100`
[CONFIRMED @ 0x100023e8], which is 8x larger and zoom-independent. `[UNCERTAIN]` which of the two is
the bound this field is actually kept within — not measured. It does not rescue the `-2396` read
(negative is out of bounds under either), but "far outside `0..48896`" was the wrong yardstick and
should not be reused without settling this.

## Which rows fired

| row | status |
|---|---|
| AD — `N > 1`, ambiguity real | **no** |
| **AE — `N == 1`, first-match theory dead** | **FIRED** |
| AF — `N > 1` but all candidates churn | **no** — not reachable, `N == 1` |
| **AG — candidate count varies in one process** | **FIRED**, narrowly: `0 -> 1`, object creation during load, never `> 1` |
| span side-measurement | `span` **never varied**: 14/14 at `1024x768`, 44/44 across both runs |

## Where this leaves U-081 / U-082

**Retracted:** the first-match / minimap-cell-map explanation for the camera anomalies. It was the
leading hypothesis at the top of this section and it is now falsified by measurement.

**Restored, with a caveat:** `cam` reads a uniquely identified object, and says so per read. The
instrument is no longer the suspect for *object identity*. It is still an unverified sampler of a
field that demonstrably changes between reads.

**Open, and now sharper.** The churn is a rigid translation of both rects with an invariant span, so
the writer is a translate, not corruption — and `FUN_10006226` is the translate. The next run should
ask **who calls it with no input**, not what `cam` is pointing at. And it should sample past t+16 s,
because that is the only window where churn has ever been observed and this run never entered it.

Install verified `stock (matches original/)` before launch and after; no patching at any point.
