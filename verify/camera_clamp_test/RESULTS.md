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

---

# Follow/track gate run — PRE-REGISTRATION, written before the launch, 2026-08-25

The enumeration run above closed the object-identity question (`N == 1`, row AE) and its `span`
result reframed the churn as a **rigid translation**, so the question became *who calls the
translate*. A parallel call-site hunt answered that: `FUN_10006226` has **zero `E8`/`E9` call sites**
and exactly one dword pointer (`.rdata 0x10062538` = iso vtable `+0x2c`), and one of its two
dispatch paths carries **no input at all** — the flush/paint tick `vt+0x148` (`FUN_1000dc17`) ->
`FUN_1000ec0b`, a follow/track re-centre -> `vt+0x30` ScrollTo. The keys/edge/drag branch takes 0
hits in 16 s of idle city, so it cannot be the input-free mover and this can.

Gate, as corrected: armed iff **`+0x354 != 0` AND `+0x524 == 0`**
`[CONFIRMED @ 0x1000ec0b: param_1[0xd5] and param_1[0x149]]`. `+0x358` (`param_1[0xd6]`) is a
**re-entrancy guard, not a gate** — `FUN_10006226:58-59` clears `+0x354` only when `+0x358 == 0`.
`+0x524` is the `U-068` field. `cam` now prints all three plus, when `+0x354` is non-zero, the
**tracked rect and its centre**. Probe rebuilt to 245,248 b.

Fixture: `Cities\Farmsville.sc3` again, **and this run must go past t+16.6 s** — the whole point.
The enumeration run has every stable read at t < 13.5 s and the earlier churn series has every
churning read at t > 16.6 s, and no run has ever sampled across that boundary. Sixteen `cam` reads,
no input: eight ~1.4 s apart to cover t+6.6 s to t+17.6 s densely, then seven ~2.9 s apart out to
t+37 s. No `dump`, so no frame this run — the reads are the measurement and the step budget
(`GZMAXSEQ` = 32) buys reach instead.

> **PRIMARY PREDICTION: `+0x354` becomes non-zero (or `+0x524` drops to 0) at t ~ 14-17 s, and the
> churn begins when the follow arms.** Arming time coinciding with churn onset is the mechanism,
> timed.

**Strongest single check, and it is free:** the log prints the tracked rect's centre. If the origin
moves **toward** that centre, the follow is demonstrably driving it. Compared on every read.

| row | prediction | what it would mean |
|---|---|---|
| **AH** | follow arms at ~ the churn onset | **mechanism CONFIRMED and timed** |
| **AI** | `+0x354` non-zero from read 1 yet no drift before t+16.6 s | `+0x524` is the discriminator; its trajectory is the report |
| **AJ** | `+0x354` **zero throughout** while churn happens | **mechanism DEAD**, said plainly |
| **AK** | no churn at all this run | churn not reproduced; and two runs would then have failed to reproduce it on demand |
| **AL** | origin moves **away** from the tracked centre | the follow is not the driver even if armed |

Install `stock (matches original/)` at claim time. No patch, one run.

---

# RESULT — **ROW AJ FIRED. `+0x354` is ZERO on all 16 reads. The follow/track mechanism is DEAD.**

The churn reproduced, hard — 13 of 15 transitions moved, mean |dx| 1,317 px — and
**`followTarget(+0x354)` was `0x00000000` on every single read, from t+4.3 s to t+32.0 s.** The gate
never armed once. `FOLLOW disarmed (predicts none)` printed 16/16 times.

**Said plainly: `FUN_1000ec0b`'s follow/track re-centre did not move this camera.** It cannot have —
its own gate requires `+0x354 != 0` `[CONFIRMED @ 0x1000ec0b]` and `+0x354` never left zero while
the origin travelled thousands of pixels. That was the leading mechanism after the call-site hunt and
it is now falsified on its own gate, by the field the hunt itself identified. Second hypothesis
killed by measurement in two runs.

## Every read verbatim, 16 reads, no input (`grep -c GZKEY` = 0), all on game thread `tid 9578`

```
[ 4295.947 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-508,-73,516,695 span=1024x768  zoom=0 tilepx=8   <== USED
[ 4296.027 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=35253  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[ 5610.604 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[ 5610.670 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[ 6803.315 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-160,1604,864,2372 span=1024x768  zoom=2 tilepx=32   <== USED
[ 6803.392 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[ 8000.551 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-160,1721,864,2489 span=1024x768  zoom=2 tilepx=32   <== USED
[ 8000.626 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[ 9130.179 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=257,862,1281,1630 span=1024x768  zoom=2 tilepx=32   <== USED
[ 9130.243 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=102  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[10251.308 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-1845,123,-821,891 span=1024x768  zoom=2 tilepx=32   <== USED
[10251.380 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[11375.598 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-1881,80,-857,848 span=1024x768  zoom=2 tilepx=32   <== USED
[11375.670 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[12501.485 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=762,-18,1786,750 span=1024x768  zoom=2 tilepx=32   <== USED
[12501.611 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=147  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[13625.930 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-1237,1898,-213,2666 span=1024x768  zoom=2 tilepx=32   <== USED
[13626.018 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[16251.024 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-331,1557,693,2325 span=1024x768  zoom=2 tilepx=32   <== USED
[16251.090 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[18875.411 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=361,1176,1385,1944 span=1024x768  zoom=2 tilepx=32   <== USED
[18875.481 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[21500.957 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-951,2172,73,2940 span=1024x768  zoom=2 tilepx=32   <== USED
[21501.058 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[24125.470 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=1993,1212,3017,1980 span=1024x768  zoom=2 tilepx=32   <== USED
[24125.535 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[26752.118 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-279,924,745,1692 span=1024x768  zoom=2 tilepx=32   <== USED
[26752.204 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[29375.358 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=-247,508,777,1276 span=1024x768  zoom=2 tilepx=32   <== USED
[29375.419 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
[32000.314 ms] ### CAM: candidate 1/1 at cityViewIso+0x158 -> 0x0EEEC620  rectA=1417,1500,2441,2268 span=1024x768  zoom=2 tilepx=32   <== USED
[32000.378 ms] ### CAM: followTarget(+0x354)=0x00000000  gate(+0x524)=0  guard(+0x358)=0  => FOLLOW disarmed (predicts none)
```

`rectB == rectA` on all 16. `rot=0`, `presentGate(+0x7c)=0` on reads 2-16 (`=1` on read 1).
`guard(+0x358)=0` on 16/16 — the re-entrancy guard was never up at sample time either.
`N == 1` candidate on 16/16, same address `0x0EEEC620`, same `cityViewIso+0x158` — row AE reconfirmed.

## I could not measure the tracked-rect check at all

The "strongest single check" was origin-versus-tracked-centre. **The tracked rect never printed,
because `+0x354` was zero on every read and the print is conditional on it being non-zero.** There
was no target to compare against. That is a null, not a negative: row AL is **not evaluable**, and I
am not substituting a proxy for it.

## The trajectory, and it kills the time-boundary theory too

| # | t (ms) | x | y | dx | x32? | dy | y32? | zoom |
|---|---|---|---|---|---|---|---|---|
| 1 | 4296 | -508 | -73 | — | | — | | **0** |
| 2 | 5611 | -160 | 1604 | +348 | no | +1677 | no | 2 |
| 3 | 6803 | -160 | 1604 | **0** | — | **0** | — | 2 |
| 4 | 8001 | -160 | 1721 | 0 | — | +117 | no | 2 |
| 5 | 9130 | 257 | 862 | +417 | no | -859 | no | 2 |
| 6 | 10251 | -1845 | 123 | -2102 | no | -739 | no | 2 |
| 7 | 11376 | -1881 | 80 | -36 | no | -43 | no | 2 |
| 8 | 12501 | 762 | -18 | +2643 | no | -98 | no | 2 |
| 9 | 13626 | -1237 | 1898 | -1999 | no | +1916 | no | 2 |
| 10 | 16251 | -331 | 1557 | +906 | no | -341 | no | 2 |
| 11 | 18875 | 361 | 1176 | +692 | no | -381 | no | 2 |
| 12 | 21501 | -951 | 2172 | **-1312** | **yes** | +996 | no | 2 |
| 13 | 24125 | 1993 | 1212 | **+2944** | **yes** | **-960** | **yes** | 2 |
| 14 | 26752 | -279 | 924 | **-2272** | **yes** | **-288** | **yes** | 2 |
| 15 | 29375 | -247 | 508 | **+32** | **yes** | **-416** | **yes** | 2 |
| 16 | 32000 | 1417 | 1500 | **+1664** | **yes** | **+992** | **yes** | 2 |

**Churn onset is between t+6.80 s and t+8.00 s** — reads 2 and 3 are byte-identical at the same
`-160,1604` load-time origin (now reproduced a **third** time, so that value is deterministic), and
read 4 has moved. **That is 6-9 seconds earlier than the predicted t ~ 14-17 s, and earlier than the
enumeration run's stability window, which held to t+13.46 s.** So the "stable before 13.5 s, churning
after 16.6 s" boundary that motivated the timing of this run **does not hold**: same fixture, same
switches, same probe path, and this run was churning at t+8.0 s while the previous one was frozen at
t+13.5 s. Whatever selects between the two regimes is not elapsed time.

## A structure nobody predicted, and it is the one new lead

**The mover becomes exactly tile-quantised partway through the run and stays that way.**
Transitions 2-11 (t+5.6 s to t+18.9 s): **0 of 10 are multiples of 32 in x.** Transitions 12-16
(t+21.5 s to t+32.0 s): **5 of 5 are multiples of 32 in x, and 4 of 5 in y.** From read 12 onward
`x mod 32 == 9` and `y mod 32 == 28` on every read — the origin is locked to one sub-tile phase and
only ever moves whole tiles.

That is the **same quantisation split** flagged in addendum 5 (key-driven deltas exact multiples,
others not), except here both regimes appear in one process with **zero input**, so it cannot be
input that distinguishes them. Two movers, or one mover with two modes; unresolved either way.
`[UNCERTAIN]` what changes at t ~ 20 s — nothing else in this log changes there.

## `span` still never varies

**`1024x768` on 32/32 rect prints this run.** Cumulative across the three Farmsville series:
**76/76.** The rigid-translation reading holds and is now the most robust fact about this field.

## Validity

25 filetrace hits on `Farmsville.sc3` out of 329 filetrace lines; 0 keys dispatched; 16/16 reads on
one thread, so no read is torn across a game-thread write; `MAP dimensions UNAVAILABLE` 16/16 (the
occupant bridge was again not captured, so **N is not confirmed from memory** — fixture rests on the
filetrace). Read 1 at t+4.3 s is a distinct pre-city regime: `zoom=0 tilepx=8`, `presentGate=1`,
`gate(+0x524)=35253`, origin centre `4,311` at the world origin. Frame written but not analysed:
`.happy-share/cmsysyj1a0rivn51c47lbyf3l/camfollow_123801.png`.

`gate(+0x524)` was non-zero on 3 of 16 reads (35253, 102, 147) and zero on 13. It is moot for the
prediction — with `+0x354 == 0` the gate is never reached — but recorded because it is the `U-068`
field and this is the first per-read trajectory of it on a live idle city.

## Which rows fired

| row | status |
|---|---|
| AH — follow arms at ~ the churn onset | **no** — it never armed |
| AI — `+0x354` non-zero from read 1, no drift before t+16.6 s | **no** — `+0x354` never non-zero |
| **AJ — `+0x354` zero throughout while churn happens** | **FIRED** |
| AK — no churn this run | **no** — churn reproduced, 13 of 15 transitions moved |
| AL — origin moves away from the tracked centre | **not evaluable** — no tracked rect was ever printed |

## Where this leaves the investigation

**Dead, by measurement, in order:** origin off-map ⇒ view dies; soft-clamp toward the map;
first-match / minimap cell map; and now the `FUN_1000ec0b` follow/track re-centre.

**Standing facts.** One cell map, uniquely identified. Both rects translate rigidly, span invariant
76/76. The load-time origin `-160,1604` is deterministic across three runs. The churn is real,
input-free, and its onset varies between runs on the identical fixture (t+8.0 s here, not yet begun
at t+13.5 s in the previous run).

**The two questions I would put next, in this order.** (1) The `vt+0x148` path was reached through
`FUN_1000ec0b`; with that branch's own gate proven closed, is there a *third* writer of
`+0x54..+0x70` that is not `FUN_10006226` at all? The call-site hunt established `FUN_10006226` has
zero direct call sites and one vtable pointer — it did not establish that `FUN_10006226` is the only
code that writes those eight dwords. A write watchpoint on `iso+0x54` answers it directly and stops
this from being another gate-by-gate elimination. (2) What changes at t ~ 20 s to make the motion
tile-quantised, given no input and no other logged transition there.

Install `stock (matches original/)` before and after; no patch, one run, both locks released.

---

# Write-watchpoint run — PRE-REGISTRATION, written before the launch, 2026-08-25

Four mechanisms have now been eliminated one gate at a time. This run stops eliminating and asks the
direct question: **who writes `iso+0x54`?**

Instrument: `SC3PROBE_CAMWATCH=1` arms a **hardware 4-byte write watchpoint** on the origin-x dword —
`DR0` = `iso+0x54`, `DR7` L0 set, `RW0=01` (break on write), `LEN0=11` (4 bytes). A vectored handler
records faulting EIPs into a bounded 16-entry table with per-EIP counts, resolved to `MODULE +
offset` via `log_modaddr`. `cam` arms on its first successful read and reports the accumulated census
on **every** read, so the output is a running total, not one snapshot. Off unless the env var is set.
Probe rebuilt to 246,272 b.

**Two limits, and the probe prints them itself in the arm line.** Data breakpoints are **per thread**,
and it arms the thread `cam` runs on (the game thread, `tid` recorded in the arm line), so
**zero hits is AMBIGUOUS, not a negative**. And x86 reports data breakpoints as traps, so the EIP is
the instruction **after** the store — the writer is immediately before it.

Fixture: `Cities\Farmsville.sc3`, 16 reads out to t+32 s so the run spans both regimes (churn onset
was t+8.0 s and the phase lock t+18.9 s in the previous run). No keys, no patch, install stock.

| row | prediction | what it would mean |
|---|---|---|
| **AM** | hits, **one** unique EIP | **the writer is named.** Resolve it and say what function it lands in. |
| **AN** | hits, **several** EIPs | several writers; all reported with counts, and which one correlates with the churn |
| **AO** | **zero hits while the origin moves** | **the writer is on another thread.** That is a finding in itself and would explain why every same-thread theory failed. It is NOT "nothing wrote it". |
| **AP** | watchpoint never arms (`GetThreadContext` / `SetThreadContext` / VEH failure) | an **instrument** result, not a camera one. Error code reported. |
| **AQ** | the game crashes | when and where, and **the instrument is the first suspect** — withdraw it rather than let it corrupt a reading |

Follow-up question if an EIP lands: is it inside `FUN_10006226` (the translate, reached only through
`.rdata 0x10062538` = iso vt `+0x2c`), or somewhere nobody has looked? The second is the more
interesting answer.

---

# RESULT — **NO ROW FIRED. The origin did not move at all, so this run measured the instrument, not the camera.**

The watchpoint armed cleanly, the game ran 38 s without a crash or a single foreign exception, and
recorded **0 hits**. But the origin was **byte-identical on all 15 reads across 27.7 seconds**. So
zero hits is neither row AM/AN (no EIP to name) nor row AO (nothing moved for a cross-thread writer
to explain) — it is the trivially consistent case, and **the pre-registered rows all presupposed a
churn that did not happen.**

Reported honestly: **I could not measure who writes `iso+0x54`, because on this run nobody did.**

## The arm line, verbatim

```
[ 4965.546 ms][tid 73f4] ### CAMW: ARMED 4-byte WRITE watch on iso+0x54 = 0x0EEC597C, thread 29684. Data breakpoints are PER THREAD, so ZERO HITS IS AMBIGUOUS (writer may be on another thread). Reported EIP is the instruction AFTER the store.
```

`tid 73f4` = 29684 decimal, so it armed exactly the thread `cam` runs on — the game thread. The
instrument did what it said.

## The census from the last read, verbatim

```
[32665.972 ms][tid 73f4] ### CAMW: 0 hit(s), 0 unique writer(s) of iso+0x54 (0x0EEC597C)  <-- zero: either nothing wrote it, or the writer is on another thread
```

Identical at all 15 reads (t+4.97 s, 6.17, 7.41, 8.65, 9.88, 11.11, 12.34, 13.58, 16.27, 19.00,
21.74, 24.48, 27.20, 29.91, 32.67 s). **Zero EIPs were recorded, so there is nothing to resolve to
module+offset and no EIP to test against `FUN_10006226`.**

## The camera was frozen — 15 reads, 27.7 s, not one pixel

Every read: `rectA = -160,1604,864,2372`, `rectB` identical, `span=1024x768`, `zoom=2 rot=0
tilepx=32`, `followTarget(+0x354)=0x00000000`, `N == 1` at `cityViewIso+0x158`. **0 of 14 transitions
moved.** `grep -c GZKEY` = 0.

That is the same `-160,1604` load-time origin, now reproduced a **fourth** time, and this run simply
never left it.

## The game was alive, so "frozen camera" is not "frozen game"

This is the check that decides whether the null means anything, and it passes:

| witness | value |
|---|---|
| `raster_blit_hw` census | 3,063 (t+10.9 s) -> 5,086 -> 7,181 -> 9,309 -> 11,371 -> **13,395** (t+38.1 s) — monotonic, ~2,050 blits per 5.4 s interval throughout |
| `WFLAG` heartbeats | 7, last one "checked 350 times" at t+38.2 s |
| exceptions / crash / minidump | **none** in the log |
| sequence | ran to `COMPLETE` at 33.3 s, `SHOT #3` written at t+40.2 s |
| filetrace | 25 hits on `Farmsville.sc3` |

The engine drew ~13,400 hardware blits while the camera sat still. Frame:
`.happy-share/cmsysyj1a0rivn51c47lbyf3l/camwatch_125558.png` — a normal, dense in-map farmland view,
status bar `Farmsville  Pob: 36,172  45,724  5/16/1904`, minimap camera rectangle at the south of the
diamond. Nothing is wrong with this process.

**And the sim clock is not advancing.** `5/16/1904` in this frame at t+40 s, and `5/16/1904` in the
enumeration run's frame — the save's own date, unchanged. The enumeration run's frame also carried
the ticker `Simulación en pausa  Sí`. So on the runs where a frame exists **the simulation is paused**,
which rules out sim-driven camera motion as the mover on those runs.

## What this run actually establishes

**One positive fact, hardware-verified:** across 27.7 s of a live, rendering, paused city with a
static camera, there were **zero writes to `iso+0x54` from the game thread**. There is no continuous
writer re-writing the same value — when the origin is still, nothing is touching it at all. That
closes off "the field is constantly being rewritten and `cam` catches it mid-write", which was one of
the two live explanations for the churn after the `U-082` null.

**One instrument fact:** `SC3PROBE_CAMWATCH` arms, survives 38 s in the game thread, costs nothing
observable, and does not crash the process. Row AP and row AQ are both ruled out. The instrument is
fit to use — it has simply not yet been pointed at a moving camera.

## ⭐ The churn is not reproducible on demand, and that is now the blocking problem

Four runs, **identical fixture, identical switches, identical probe path, no input in any of them**:

| run | reads | window | behaviour |
|---|---|---|---|
| A (earlier session) | 15 | t+16.6 -> 32.4 s | churn throughout, mean \|dx\| 1,080 px |
| B (enumeration) | 7 | t+6.6 -> 14.6 s | **stable** 6 reads, then one jump at t+14.6 s |
| C (follow gate) | 16 | t+4.3 -> 32.0 s | churn from **t+8.0 s**, 13 of 15 transitions moved |
| **D (this run)** | 15 | t+5.0 -> 32.7 s | **frozen. 0 of 14 transitions moved.** |

Churn onset has been t+16.6 s, t+14.6 s, t+8.0 s, and never. **It is not elapsed time** (killed last
run), **not the fixture** (all four are Farmsville, and B and D were quiet on the fixture called
unstable), **not input** (zero keys in all four), and **not the sim** (paused where measured). No
variable identified so far sorts these four runs.

**The confound I have to flag, because it is the one difference.** Run D is the only run with
`SC3PROBE_CAMWATCH=1`, and run D is the only completely frozen run. Against that: the VEH recorded 0
hits, so it never executed, and an armed-but-never-hit debug register has no runtime cost — there is
no mechanism by which it would suppress a write. But **I cannot rule it out from one run**, and it
would be careless to leave a coincidence between "new instrument" and "phenomenon vanished"
unexamined. `[UNCERTAIN]`, and the test is cheap: one run identical to D with the env var **unset**.
If that one churns, the watchpoint is the suppressor and must be withdrawn; if it is also frozen, the
non-reproducibility is real and D is just the fourth sample of a coin-flip.

## Which rows fired

| row | status |
|---|---|
| AM — hits, one unique EIP | **no** — 0 hits, no EIP |
| AN — hits, several EIPs | **no** — 0 hits |
| AO — zero hits while the origin moves | **no**, and this is the point: the origin **did not move**, so the cross-thread inference is not licensed |
| AP — watchpoint never arms | **no** — it armed, on the right thread |
| AQ — the game crashes | **no** — 38 s, no exception, no dump, sequence completed |
| **none of the above** | **the phenomenon did not occur.** No row was written for that, and one should have been. |

## What I would do next, in priority order

1. **A control run: identical to this one with `SC3PROBE_CAMWATCH` unset.** Until that exists, every
   reading from D carries the confound above. This is the cheapest run on the list and it gates the
   others.
2. **Stop treating the churn as on-demand.** Three of four runs disagree about when it starts and one
   says never. Any future writer-hunt run needs a *live* churn-detection gate — arm the watchpoint,
   then only trust the census from a run where consecutive reads actually differ — otherwise a null
   like this one is indistinguishable from a real negative.
3. **If a churning run is caught with the watchpoint armed and still reports 0 hits**, that is row AO
   for real and names the answer: another thread.

Install `stock (matches original/)` before and after; no patch, one run, claim and lease both
released.

---

# Watchpoint-suppression control — PRE-REGISTRATION, written before the launches, 2026-08-25

Run D (the write-watchpoint run) was the only run with `SC3PROBE_CAMWATCH=1` and the only completely
frozen run. That coincidence is mine to clear before anything built on D is trusted.

**The design rests on an asymmetry, and it is the reason this run is worth a session.** Three runs
without the watchpoint already exist (A churned, B stable-then-jumped at t+14.6 s, C churned). So:

> **If freezing EVER happens without `SC3PROBE_CAMWATCH`, the suppression hypothesis is dead.**

**One frozen no-var run is decisive. A churning no-var run is worth nothing** — at the observed
3-in-4 base rate, churn is simply the expected outcome, and three churns in a row would occur about
42% of the time by luck alone. This is stated here, before the launches, so a churn cannot later be
read as evidence for suppression.

**Design: three launches, `SC3PROBE_CAMWATCH` unset, otherwise byte-identical to D** — Farmsville via
`-GamePath`, the same switch string, the **same `-GzSeq` step-for-step** (16 `cam` reads, eight
~1.24 s apart then seven ~2.7 s apart, out to ~t+32 s), no input. A shortened sequence was considered
and rejected: for a control, "identical" is the point, and a shorter window would make "frozen" mean
something weaker than it did in D.

**Deciding criterion, fixed in advance:** *any* pair of consecutive `cam` reads whose `rectA`
differs => **churn**. Zero such pairs across the whole window => **frozen**.

| row | prediction | what it would mean |
|---|---|---|
| **AR** | **any one of the three is frozen** | suppression hypothesis **DEAD**; the watchpoint is exonerated; non-reproducibility is a property of the game, not the instrument |
| **AS** | all three churn | **not** proof of suppression. Consistent with it, does not establish it (~42% by chance). What would settle it: a matched set with the var **set**. |
| **AT** | any run crashes or fails to load | instrument or fixture problem — report and stop |

**Free addition, registered now:** for each run that churns, the **elapsed time to first motion**.
Four onsets are known (t+16.6 s, t+14.6 s, t+8.0 s, never); three more begin to show whether the
onset distribution has any shape.

**One protocol deviation, disclosed.** `capture.ps1` acquires the game lease itself and releases it in
its own `finally`, so a lease taken by hand around all three launches would be dropped by the first
one. What is actually held continuously across the three is the **harness claim** (`cam-enum`); the
lease is re-taken and released per launch by the same owner via `SC3_SESSION`, which preserves the
single-instance guarantee and the attribution. Install verified stock before and after.

---

# RESULT — **ROW AR FIRED. Run E2 froze with `SC3PROBE_CAMWATCH` unset. The suppression hypothesis is DEAD and the watchpoint is exonerated.**

Three launches, var unset, byte-identical sequence to D, no input in any of them, all three ran to
`COMPLETE` with zero exceptions. **E2 sat at `-160,1604` for 15 consecutive reads spanning 27.9 s.**
That is the decisive single freeze the design was bought for: freezing happens without the
instrument, so the instrument does not cause it. My confound on run D is cleared.

## First, the criterion I pre-registered was defective, and I am not going to quietly fix it

I wrote: *any pair of consecutive `cam` reads whose `rectA` differs => churn*. Applied literally,
**all three controls churn** — and that answer is wrong, because the pair it fires on in E2 and E3 is
`read 1 -> read 2`, the **city-load transition**: `zoom=0 tilepx=8` at `-508,-73` (the pre-city
default) becoming `zoom=2 tilepx=32` at `-160,1604`. That is loading, not churn.

Worse, it is not comparable across runs. Whether a run's first read lands before or after the city
loads is load-timing jitter: **D and E1 never sampled the pre-city state; E2 and E3 did.** So the
criterion as written classifies runs by when their first sample happened to fall.

**Corrected criterion, applied uniformly to every run in this file:** consider only reads from the
first `zoom=2` post-load read onward. Churn = any consecutive pair differing within that window.

| run | literal criterion | **corrected criterion** |
|---|---|---|
| E1 | churn | **CHURN** |
| E2 | churn | **FROZEN** |
| E3 | churn | **CHURN** |

## The three controls, with the deciding read pair for each

**E1 — CHURN, then it STOPPED.** `CAMW` lines: 0 (var confirmed unset). 15 reads.

| # | t (ms) | x | y | dx | dy |
|---|---|---|---|---|---|
| 1 | 4994 | -160 | 1604 | — | — |
| 2 | 6257 | -160 | 1604 | 0 | 0 |
| **3** | **7421** | **-362** | **1346** | **-202** | **-258** |
| 4 | 8545 | -82 | -450 | +280 | -1796 |
| 5 | 9672 | -82 | 1355 | 0 | +1805 |
| 6 | 10796 | -1362 | 1974 | -1280 | +619 |
| 7 | 11921 | -1362 | 895 | 0 | -1079 |
| 8 | 13046 | 794 | -9 | +2156 | -904 |
| 9 | 15671 | -1466 | 114 | -2260 | +123 |
| 10-15 | 18296 - 31421 | -1466 | 114 | **0** | **0** |

Deciding pair: **read 2 -> 3, t+6257 -> t+7421 ms, `-160,1604` -> `-362,1346`.** Onset bracket
**t+6.26 s to t+7.42 s**. Then, unprompted, **it froze at `-1466,114` for reads 9 through 15 — six
consecutive zero transitions over 15.8 s.**

**E2 — FROZEN. This is the run that settles it.** `CAMW` lines: 0. 16 reads.

| # | t (ms) | x | y | zoom |
|---|---|---|---|---|
| 1 | 4113 | -508 | -73 | 0 (pre-city) |
| 2 | 5335 | -160 | 1604 | 2 |
| 3-16 | 6623 - 33221 | **-160** | **1604** | 2 |

**Zero differing pairs across the entire post-load window: 15 reads, t+5.34 s to t+33.22 s, 27.9
seconds, not one pixel.** Materially identical to D — and with the watchpoint absent.

**E3 — CHURN, and the zoom moved on its own.** `CAMW` lines: 0. 16 reads.

| # | t (ms) | rectA | zoom | tilepx |
|---|---|---|---|---|
| 1 | 3697 | -508,-73,516,695 | 0 | 8 |
| 2-9 | 4979 - 13512 | **-160,1604,864,2372** (identical) | 2 | 32 |
| **10** | **16154** | **-465,861,559,1629** | 2 | 32 |
| 11 | 18779 | -1154,2077,-130,2845 | 2 | 32 |
| 12 | 21404 | 1533,570,2557,1338 | 2 | 32 |
| 13 | 24029 | -600,1347,424,2115 | 2 | 32 |
| **14** | **26653** | **868,7426,1892,8194** | **4** | **128** |
| 15 | 29279 | -1516,6838,-492,7606 | 4 | 128 |
| 16 | 31903 | -2512,7120,-1488,7888 | 4 | 128 |

Deciding pair: **read 9 -> 10, t+13512 -> t+16154 ms, `-160,1604` -> `-465,861`.** Onset bracket
**t+13.51 s to t+16.15 s**.

## Two findings the control run was not designed to get

**1. Churn stops by itself. E1 churned for 7 transitions then froze for 15.8 s.** So "churning" and
"frozen" are not properties of a run — they are properties of a *window* within a run. Every
run-level classification in this file, including my own D verdict, is therefore a statement about
when it sampled. A run that begins sampling at t+18 s would have called E1 frozen.

**2. The zoom changes with no input.** E3 went `zoom=2 tilepx=32` -> `zoom=4 tilepx=128` between
t+24.03 s and t+26.65 s, zero keys dispatched. A second field on this object moves unprompted, and
`SetZoom` is a different vtable slot (`+0x38` -> `0x10006752`) from the translate (`+0x2c` ->
`0x10006226`), so whatever is driving this reaches more than one entry point.

That also **settles the yardstick question I flagged two runs ago**. E3 read 14 has `y = 7426`, which
is outside `0..3072` (the diamond at `tilepx=32`) but inside `0..12288` (the diamond at
`tilepx=128 = 192 x 128 / 2`). The bound is **zoom-dependent**, `N x tilepx` by `N x tilepx / 2`, and
`0..48896` was never the right comparison. **Any out-of-bounds claim in this file must be re-checked
against the zoom recorded on the same read.**

## Reconfirmed across the controls

- **`followTarget(+0x354) = 0x00000000` on all 47 control reads.** With C and D that is **63
  consecutive reads** with the follow gate closed. Row AJ stands, three runs deep.
- **`N == 1` candidate on 47/47.** Row AE stands.
- **`span = 1024x768` on 47/47 reads, `rectA` and `rectB` both** = 94 prints, **cumulative 170/170**
  across six series. Rigid translation remains the most robust fact in the thread.
- Validity: 0 keys in all three; 25 `Farmsville.sc3` filetrace hits each; 0 exceptions, 0 minidumps,
  all three sequences `COMPLETE`, all three shots written.

## Running tally, corrected criterion, all seven runs

| run | `CAMWATCH` | post-load window | verdict | first motion (bracket) |
|---|---|---|---|---|
| A | unset | t+16.6 -> 32.4 s | churn | not bracketed (already moving at first read) |
| B | unset | t+6.6 -> 14.6 s | churn | t+13.46 -> 14.59 s |
| C | unset | t+5.6 -> 32.0 s | churn | t+6.80 -> 8.00 s |
| **D** | **SET** | t+4.97 -> 32.67 s | **frozen** | never |
| E1 | unset | t+4.99 -> 31.42 s | churn, **then froze from t+15.7 s** | t+6.26 -> 7.42 s |
| **E2** | **unset** | t+5.34 -> 33.22 s | **frozen** | **never** |
| E3 | unset | t+4.98 -> 31.90 s | churn | t+13.51 -> 16.15 s |

**Base rate without the watchpoint: 5 churn, 1 frozen out of 6.** D's freeze is no longer
exceptional. Suppression is dead by row AR, not by a base-rate argument — one freeze without the var
was the pre-registered killer and E2 delivered it.

**Onset brackets, four of them now:** t+6.26-7.42, t+6.80-8.00, t+13.46-14.59, t+13.51-16.15. Two
near t+7 s and two near t+14 s, with nothing in between. **n = 4, so this is an observation and not a
distribution** — but if it survives more samples, a bimodal onset would mean two triggers rather than
one noisy one, and that is a cheap thing to keep counting.

## Which rows fired

| row | status |
|---|---|
| **AR — any one of the three frozen** | **FIRED** — E2, 15 reads, 27.9 s, zero motion |
| AS — all three churn | **no** under the corrected criterion (yes under the literal one, which I have shown is not comparable across runs) |
| AT — a run crashes or fails to load | **no** — 3/3 loaded, 3/3 completed, 0 exceptions |

## What this changes for the next step

**The write-watchpoint instrument is cleared for use.** Nothing built on D needs withdrawing, and D's
one positive fact stands: no continuous same-value writer of `iso+0x54` on the game thread.

**But the live churn-detection gate is now mandatory, not merely advisable, and E1 shows why it must
be a *window* gate rather than a run gate.** A watchpoint census is only interpretable if the origin
demonstrably moved *while the census was accumulating*. The cheap version: have `cam` report the
watchpoint census **per interval** alongside that interval's `dx,dy`, so each interval is its own
experiment — the intervals that moved are the ones whose EIPs matter, and a run like E1 yields both a
moving sample and a frozen control inside one launch.

Install `stock (matches original/)` before and after; no patch; claim held across all three launches,
lease per launch by the same owner, both released.
