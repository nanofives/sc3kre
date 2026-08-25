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

---

# Per-interval writer census — PRE-REGISTRATION, written before the launches, 2026-08-25

`cam` now scores **intervals, not runs**, which is the fix E1 forced: churn stops by itself, so a
run-level label is really a statement about when the run sampled. Each read prints
`### CAMW: interval N dx=+X dy=+Y MOVED|still writes=K`, writer lines are **differenced per
interval** so a moving interval names its own writers, and a moving interval with zero writes prints
`<== MOVED WITH ZERO WRITES ON THIS THREAD: the writer is on ANOTHER THREAD`. The `dx,dy` labelling
runs even with the watchpoint off. Probe rebuilt to 246,784 b.

**Every interval is now an independent experiment, so a frozen launch is no longer a wasted one** —
its intervals are `still` controls.

## A constraint I hit, and the deviation it forces — disclosed before the run

`GZMAXSEQ` is **32**, so one launch buys at most 16 `cam` reads (16 reads + 15 waits = 31 steps).
That makes "~1 s cadence" and "30 s or more" **mutually exclusive in a single launch**: at 1 s
spacing 16 reads span ~15 s, and to reach 30 s the spacing must be ~1.8 s.

Rather than silently pick one, **two launches inside one claim**:

- **F1 — tight cadence.** `wait:750` x 15, giving ~1.0 s intervals across roughly t+5 s to t+20 s.
  Covers both known onset modes (t+6-8 s and t+13-16 s) at maximum interval resolution.
- **F2 — long window.** `wait:1500` x 15, giving ~1.8 s intervals across roughly t+5 s to t+31 s.
  Reaches past t+16.6 s, where run A churned.

Two launches double the independent intervals (30 rather than 15) and hedge the 5-in-6 churn base
rate, at the cost of one extra load. Same lease-per-launch / claim-held-across pattern as the
control set. `SC3PROBE_CAMWATCH=1` on both, Farmsville via `-GamePath`, no input, install stock.

| row | prediction | what it would mean |
|---|---|---|
| **AU** | any **MOVED** interval **with writes** | **the writer is named.** Every EIP resolved, and stated whether it lands in `FUN_10006226` (translate, iso vt `+0x2c`) or somewhere unmapped. Unmapped is the more interesting answer. |
| **AV** | any **MOVED** interval with **zero writes** | **the writer is on another thread.** Decisive and new; it retires every same-thread mechanism at once, five of which are already dead. |
| **AW** | MOVED-with-writes **and** still-with-writes both present | compare them: writers firing in both are background, writers unique to moving intervals are the cause |
| **AX** | no MOVED intervals in either launch | both launches sat in frozen windows. Reported as such; the intervals still functioned as `still` controls; **not** a negative about the writer |

Secondary, carried forward at no cost: `zoom`/`tilepx` per read (E3 changed zoom with no input), and
the running `span` count.

---

# RESULT — **ROW AU FIRED. The writer is named: `SIMSPR + 0x62AF` = `FUN_10006226 + 0x89`, the translate.**

Twelve MOVED intervals, **every one of them with writes**. Seventeen `still` intervals, **every one of
them with zero writes**. **29 of 29 intervals separate perfectly**, and the EIP is the same on all but
one hit.

**`0x100062AF` is inside `FUN_10006226`.** The next function in the SIMSPR export is `0x10006736`, so
`FUN_10006226` spans `0x10006226`-`0x10006735` and the faulting EIP sits at **`+0x89`, 137 bytes in**
[CONFIRMED @ 0x100062af]. The EIP is the instruction *after* the store, so the store to `iso+0x54`
lives at or immediately before `FUN_10006226+0x89`. **It is the translate**, reached only through
`.rdata 0x10062538` = iso vt `+0x2c`, exactly the function the call-site hunt pointed at.

**Row AV did not fire, and that is a second answer.** No MOVED interval had zero writes. **The writer
is on the game thread** — the cross-thread hypothesis is retired, and D's ambiguous null was ambiguity
only, not a hidden thread.

## The second writer, and it is `SetZoom`

`SIMSPR + 0x68C9` = **`FUN_10006752 + 0x177`**. Next function in the export is `0x1000699f`, so
`FUN_10006752` spans `0x10006752`-`0x1000699e` and `0x100068C9` is 375 bytes in
[CONFIRMED @ 0x100068c9]. `FUN_10006752` is **`SetZoom`**, iso vt `+0x38` — a *different* slot from
the translate.

It fired **once**, in F2 interval 1, the city-load transition where `zoom` went `0 -> 2` and
`tilepx` `8 -> 32`. So `SetZoom` also writes the origin rect, which is the mechanism behind E3's
unprompted zoom change, and it confirms the point I raised last run: **a translate-only hunt would
have missed this entry point.**

## F1 — tight cadence (~0.9 s), CHURN. The interval table

`ARMED 4-byte WRITE watch on iso+0x54 = 0x0EEA0D94, thread 6160.`

| iv | t (ms) | dx | dy | class | writes | writer |
|---|---|---|---|---|---|---|
| 0 | 4828 | baseline `-160,1604` | | | | |
| 1 | 5840 | +0 | +0 | still | **0** | — |
| 2 | 6875 | +0 | +0 | still | **0** | — |
| 3 | 7822 | +0 | +0 | still | **0** | — |
| **4** | **8727** | **-1512** | **+207** | **MOVED** | **104** | `SIMSPR+0x62AF` |
| 5 | 9602 | +3371 | -1275 | MOVED | 138 | `SIMSPR+0x62AF` |
| 6 | 10477 | -2785 | -705 | MOVED | 79 | `SIMSPR+0x62AF` |
| 7 | 11352 | +501 | -148 | MOVED | 150 | `SIMSPR+0x62AF` |
| 8 | 12226 | +770 | +178 | MOVED | 91 | `SIMSPR+0x62AF` |
| 9 | 13102 | -519 | +1223 | MOVED | 66 | `SIMSPR+0x62AF` |
| 10 | 13977 | -928 | +64 | MOVED | 72 | `SIMSPR+0x62AF` |
| **11** | **14851** | **+0** | **-32** | **MOVED** | **1** | `SIMSPR+0x62AF` |
| 12 | 15727 | -672 | +576 | MOVED | 21 | `SIMSPR+0x62AF` |
| 13 | 16602 | +2208 | -1952 | MOVED | 72 | `SIMSPR+0x62AF` |
| 14 | 17477 | +320 | +1824 | MOVED | 66 | `SIMSPR+0x62AF` |

Onset bracket **t+7.82 s to t+8.73 s**. `zoom=2 tilepx=32` on all 15 reads.

**Interval 11 is the cleanest single data point in this whole investigation:** `writes=1`, `dx=0`,
`dy=-32`. One call, one tile of movement, and `dx=0` **with a write recorded** — which proves the
counter registers a store even when the stored value is unchanged. That matters, because it means
the 17 `still` intervals with `writes=0` had **no store at all**, not merely no net displacement.
The separation is real, not an artefact of differencing.

**What I will not claim:** that each write equals one 32 px step. It holds for interval 11
(1 write, 32 px) and interval 12 (`dx = -672 = -21 x 32` with 21 writes), but not for interval 4
(104 writes, `dx = -1512`, not a multiple of 32). Call frequency is 66-150 stores per ~0.9 s
interval, i.e. **roughly 75-165 calls per second** into the translate with no input whatsoever;
the net displacement is much smaller than the path length, so it oscillates. `[UNCERTAIN]` what the
per-call delta is.

## F2 — long window (~1.6 s), FROZEN. Fifteen `still` controls

`ARMED 4-byte WRITE watch on iso+0x54 = 0x0EEB339C, thread 37124.`

| iv | t (ms) | dx | dy | class | writes | writer |
|---|---|---|---|---|---|---|
| 0 | 3838 | baseline `-508,-73` (`zoom=0 tilepx=8`, pre-city) | | | | |
| **1** | **5589** | **+348** | **+1677** | **MOVED** (city load) | **2** | `SIMSPR+0x62AF` x1, **`SIMSPR+0x68C9` x1** |
| 2-15 | 7262 - 28386 | +0 | +0 | **still** | **0** | — |

Fifteen consecutive `still` intervals, t+5.59 s to t+28.39 s, **22.8 s frozen at `-160,1604`**. Under
the old design this launch would have been a wasted run; under the interval design it contributed
**15 clean controls**, which is exactly what makes the 29/29 separation meaningful.

## The whole result in one line

| | writes > 0 | writes = 0 |
|---|---|---|
| **MOVED** | **12** | **0** |
| **still** | **0** | **17** |

**Stores to `iso+0x54` occur if and only if the origin moved**, across 29 intervals in two processes.
No background writer, nothing to disambiguate — row AW had nothing to compare because there were no
still-interval writes at all.

## Validity

0 keys in both launches; 25 `Farmsville.sc3` filetrace hits each; 0 exceptions, 0 minidumps, both
sequences `COMPLETE`, both shots written. `span = 1024x768` on 31/31 reads across both launches
(`rectA` and `rectB`) = 62 prints, **cumulative 232/232**. `N == 1` on 31/31. `followTarget(+0x354)`
zero throughout, as in every run since C.

## Running tally, corrected criterion, nine runs

| run | `CAMWATCH` | window | verdict | onset bracket |
|---|---|---|---|---|
| A | unset | t+16.6 - 32.4 s | churn | not bracketed |
| B | unset | t+6.6 - 14.6 s | churn | t+13.46 - 14.59 s |
| C | unset | t+5.6 - 32.0 s | churn | t+6.80 - 8.00 s |
| D | SET | t+4.97 - 32.67 s | frozen | never |
| E1 | unset | t+4.99 - 31.42 s | churn, then froze from t+15.7 s | t+6.26 - 7.42 s |
| E2 | unset | t+5.34 - 33.22 s | frozen | never |
| E3 | unset | t+4.98 - 31.90 s | churn | t+13.51 - 16.15 s |
| **F1** | **SET** | t+4.83 - 17.48 s | **churn** | **t+7.82 - 8.73 s** |
| **F2** | **SET** | t+5.59 - 28.39 s | **frozen** | never |

Six churn, three frozen. **F1 churning with the watchpoint armed is the independent confirmation of
E2's verdict** — the instrument neither suppresses churn nor is required for it.

**Onset brackets, five now:** 6.26-7.42, 6.80-8.00, **7.82-8.73**, 13.46-14.59, 13.51-16.15. Three in
a t+6.3-8.7 s cluster and two in a t+13.5-16.2 s cluster, still nothing between. n = 5; the gap has
survived every sample so far, which is worth continuing to count but is not yet a distribution.

## Which rows fired

| row | status |
|---|---|
| **AU — MOVED interval with writes** | **FIRED** — 12 of 12, writer resolved to `FUN_10006226 + 0x89`, **inside the translate** |
| AV — MOVED interval with zero writes | **no** — 0 of 12. **The writer is on the game thread**; the cross-thread hypothesis is retired |
| AW — MOVED-with-writes and still-with-writes both present | **no** — 0 still intervals had writes, so there is no background set to subtract |
| AX — no MOVED intervals at all | **no** — F1 supplied 12; F2 supplied 15 controls |

## Where this leaves it

**Answered, for the first time in this thread:** *what* writes the camera origin, *where*, and *on
which thread*. `FUN_10006226+0x89` on the game thread, plus `FUN_10006752+0x177` (`SetZoom`) on a
zoom change. Both on the same object `cam` has been reading all along.

**Still open, and it is now a different question.** `FUN_10006226` has **zero direct call sites** and
one vtable pointer (iso vt `+0x2c`), and the one dispatch path with no input on it — `vt+0x148` ->
`FUN_1000ec0b` -> `vt+0x30` — is **gated closed** (`+0x354 == 0` on 63+ consecutive reads). So the
translate is being entered 75-165 times a second through a vtable slot whose known input-free caller
cannot be firing. **The next question is not what writes the field but who calls vt+0x2c**, and the
same interval technique answers it: a breakpoint or hook on `FUN_10006226` entry recording its
**return address**, differenced per interval, names the caller the way this run named the writer.

Install `stock (matches original/)` before and after; no patch; claim held across both launches, lease
per launch by the same owner, both released.

---

# Caller census on iso vt+0x2c — PRE-REGISTRATION, written before the launches, 2026-08-25

The writer is settled: `FUN_10006226+0x89` on the game thread, 29/29 interval separation. The open
question changed shape as a result — the translate is entered **75-165 times a second with no input**,
through a vtable slot whose only known input-free caller (`FUN_1000ec0b`) is gated closed
(`+0x354 == 0` on every read since run C). So: **who calls `vt+0x2c`?**

Instrument: `SC3PROBE_CAMCALLER=1` swaps the single vtable dword at `.rdata SIMSPR+0x62538`. Checked
before the run: it is **expect-or-refuse** (reads the slot and refuses unless it holds exactly
`SIMSPR+0x6226`, logging what it found), the thunk is the house `MAKE_STUB` shape with the return
address at `[esp+36]` = 32 (`pushad`) + 4 (`pushfd`) which I verified by inspection, and the swap is
**memory-only** — no file on disk is touched, so the install remains stock by hash throughout.
A vtable swap rather than an entry detour is the right call on a function this hot. Probe rebuilt to
248,832 b.

**Both instruments on**, so each interval reports **calls in and stores out**. That is a mutual
self-check: if `calls=` and `writes=` disagree in shape, one of the two is lying and the disagreement
is itself the finding.

**Same `GZMAXSEQ` = 32 constraint as last time**, so "~1 s cadence" and "30 s+" remain mutually
exclusive in one launch, and the same disclosed deviation applies: **two launches inside one claim** —
**G1** at `wait:750` (~1.0 s intervals, ~t+5 to t+20 s, covering both onset clusters at maximum
resolution) and **G2** at `wait:1500` (~1.8 s intervals, ~t+5 to t+31 s, reaching past t+16.6 s).
This also hedges the 6-in-9 churn base rate, and F2 proved a frozen launch is not wasted.

| row | prediction | what it would mean |
|---|---|---|
| **AY** | callers named on MOVING intervals | resolve every return address. Is it `FUN_1000ec0b` (the follow — which would **contradict** `+0x354 == 0`), `FUN_1001d503` / `FUN_10006736` (the two mapped dispatch sites), or **something unmapped**? The third is the interesting one and is what the call rate suggests. |
| **AZ** | the same caller on MOVING **and** still intervals | that caller is not the driver; the driver is whatever differs between the two sets |
| **BA** | **`MOVED WITH ZERO CALLS`** | the origin moves **without** entering `vt+0x2c` => a **second writer path**, and a direct contradiction of the 29/29 separation. **Bigger than the caller question**; report loudly. |
| **BB** | refuses to arm | report the slot contents **verbatim** — that is a fact about the binary, not a failure |
| **BC** | crash | **the new thunk is the first suspect**, it is new code in a hot path; withdraw it rather than let it colour a reading |

Carried forward free: writer census per interval, `zoom`/`tilepx` per read, `span` tally, onset
bracket for any launch that churns.

---

# RESULT — **NO ROW FIRED. Both launches sat in frozen windows, so the caller was never called.**

28 intervals across two launches, **every one `still`, every one `calls=0`, every one `writes=0`**.
No MOVED interval, so **no return address was ever recorded and the caller is not named.** The
instrument armed correctly and the game was alive throughout; the phenomenon simply did not occur.

## First, an omission that is mine, and I made it after writing down that I had made it before

**I did not pre-register a "no MOVED intervals" row this time.** Two runs ago, when the watchpoint
run produced exactly this outcome, I wrote in this file: *"none of the above — the phenomenon did not
occur. No row was written for that, and one should have been."* I then wrote row AX for the F-run
pre-registration, and dropped it again for this one. So the same gap caught me twice. Recording it
here rather than quietly scoring against row AX from a different pre-registration.

## The arm lines, verbatim — and expect-or-refuse PASSED in both

```
[ 5034.462 ms] ### CAMW: ARMED 4-byte WRITE watch on iso+0x54 = 0x0EED8BCC, thread 36852. Data breakpoints are PER THREAD, so ZERO HITS IS AMBIGUOUS (writer may be on another thread). Reported EIP is the instruction AFTER the store.
[ 5034.498 ms] ### CAMC: ARMED caller census - iso vt+0x2c at 0x034F2538 swapped 0x03496226 -> thunk 0x6F361EB0. One vtable pointer, so this catches 100% of calls; no code was patched.
```
```
[ 5760.066 ms] ### CAMW: ARMED 4-byte WRITE watch on iso+0x54 = 0x0EED630C, thread 10212. Data breakpoints are PER THREAD, so ZERO HITS IS AMBIGUOUS (writer may be on another thread). Reported EIP is the instruction AFTER the store.
[ 5760.112 ms] ### CAMC: ARMED caller census - iso vt+0x2c at 0x034D2538 swapped 0x03476226 -> thunk 0x6F361EB0. One vtable pointer, so this catches 100% of calls; no code was patched.
```

**This is the run's one unambiguous positive.** The slot held `0x03496226` in G1 and `0x03476226` in
G2 — in each process exactly `SIMSPR + 0x6226`, so the swap proceeded rather than refusing. Until now
"iso vt `+0x2c` holds `FUN_10006226`" was a **static** claim from the call-site hunt over `.rdata`.
It is now **confirmed at runtime in two independent processes** by an instrument that would have
refused and printed the contents had it been anything else. Row BB did not fire, and the reason it
did not fire is itself the evidence.

## The interval table — 28 intervals, all still, all silent

**G1** (tight, ~0.97 s intervals), armed t+5.03 s, baseline `-160,1604`:

| iv | t (ms) | dx | dy | class | writes | calls |
|---|---|---|---|---|---|---|
| 1-14 | 6003 - 18647 | **+0** | **+0** | **still** | **0** | **0** |

**G2** (long, ~1.75 s intervals), armed t+5.76 s, baseline `-160,1604`:

| iv | t (ms) | dx | dy | class | writes | calls |
|---|---|---|---|---|---|---|
| 1-14 | 7455 - 30142 | **+0** | **+0** | **still** | **0** | **0** |

Origin `-160,1604` on **30 of 30 reads** in both launches, `zoom=2 tilepx=32` throughout, no
transition of any kind. G1 covered t+5.03-18.65 s, G2 covered t+5.76-30.14 s.

## ⭐ What the null does establish, and it is not nothing

**In a frozen window, `vt+0x2c` is called ZERO times.** Not "called with a zero delta" — **not called
at all**, across 28 intervals and 44 seconds of live city in two processes.

Set that beside F1, where every moving interval carried **66-150 stores** in ~0.9 s. The contrast is
sharp and it narrows the caller hunt:

> **The driver is not a continuously-running loop whose delta is sometimes zero. It starts and stops.**
> Something begins calling `vt+0x2c` at ~100 Hz and later ceases, which is exactly the shape E1 showed
> from the outside when it churned for 7 transitions and then froze for 6 in one launch.

So the caller is gated by something that toggles, and the frozen windows are the gate closed rather
than the driver idling. A caller census will name it the moment a launch churns; nothing about the
method needs changing.

## The two instruments agree, which is the self-check passing

`calls=0`, `writes=0`, `dx=dy=0` in **28 of 28 intervals**. Running both was meant to catch one of
them lying, and in this regime they corroborate each other exactly. Row BA (`MOVED WITH ZERO CALLS`)
had no opportunity to fire, so the 29/29 separation from the F runs is neither confirmed nor
challenged here.

## The confound, stated because it is the instrument's first outing

CAMCALLER is new, and **both of its launches froze.** Against reading anything into that:

- The thunk **never executed** (`calls=0`), so it had no runtime cost or timing effect. The only
  action taken was a single dword write at arm time.
- `writes=0` as well, so this is not "the swap broke dispatch and the writes stopped" — the entire
  path was quiet, including the store the watchpoint sees independently of the vtable.
- The game was demonstrably alive: `raster_blit_hw` 897 -> 7,323 (G1) and 897 -> 12,720 (G2),
  monotonic; 4 and 7 `WFLAG` heartbeats; both sequences `COMPLETE`; shots written; **0 exceptions,
  0 minidumps**. Row BC did not fire.
- And the base rate no longer makes two freezes surprising — see below.

`[UNCERTAIN]` all the same, on one pair of launches. The clean test is the same shape that cleared
the watchpoint: a churning launch **with** CAMCALLER armed, which would exonerate it the way F1
exonerated CAMWATCH.

## Running tally, corrected criterion, eleven runs

| run | instruments | window | verdict |
|---|---|---|---|
| A | none | t+16.6 - 32.4 s | churn |
| B | none | t+6.6 - 14.6 s | churn |
| C | none | t+5.6 - 32.0 s | churn |
| D | CAMWATCH | t+4.97 - 32.67 s | frozen |
| E1 | none | t+4.99 - 31.42 s | churn, then froze from t+15.7 s |
| E2 | none | t+5.34 - 33.22 s | frozen |
| E3 | none | t+4.98 - 31.90 s | churn |
| F1 | CAMWATCH | t+4.83 - 17.48 s | churn |
| F2 | CAMWATCH | t+5.59 - 28.39 s | frozen |
| **G1** | **CAMWATCH + CAMCALLER** | t+5.03 - 18.65 s | **frozen** |
| **G2** | **CAMWATCH + CAMCALLER** | t+5.76 - 30.14 s | **frozen** |

**6 churn, 5 frozen.** I previously called this 6-and-3 out of 9; with two more samples the frozen
rate is close to a coin flip, and **two consecutive freezes now carry probability ~0.21** — ordinary.
That revision matters more than it looks: at ~45% frozen, **a fixed two-launch design fails to
observe the phenomenon about one time in five**, which is what happened here.

## The method fix, and why I am NOT running a third launch now

The obvious move is one more launch to catch a churn. **I am not taking it**, because the
pre-registration committed to two and adding a third after seeing the result is exactly the
undisclosed flexibility pre-registration exists to prevent — the same discipline that made E2 worth
something.

Instead, the next caller run should pre-register an **adaptive stopping rule, declared in advance**:

> *Launch repeatedly until one launch yields at least one MOVED interval, to a maximum of four
> launches; report every launch including the frozen ones.*

At a 45% freeze rate that reaches a churning launch with ~94% probability inside four loads, it is
honest because it is declared before the run, and the frozen launches are not waste — they are
`still` controls, which is the property F2 first demonstrated. **And it should also pre-register the
all-frozen row that I have now omitted twice.**

## Validity

0 keys both launches; 25 `Farmsville.sc3` filetrace hits each; 0 exceptions, 0 minidumps; both
sequences `COMPLETE`; shots written. `followTarget(+0x354) = 0` on **30/30** reads (the follow gate
has now been closed on every read since run C). `N == 1` candidate on 30/30. `span = 1024x768` on
30/30 reads for both rects = 60 prints, **cumulative 292/292**.

## Which rows fired

| row | status |
|---|---|
| AY — callers named on MOVING intervals | **no** — there were no MOVING intervals |
| AZ — same caller on moving and still | **no** — no callers recorded at all |
| BA — `MOVED WITH ZERO CALLS` | **no** — no opportunity |
| BB — refuses to arm | **no**, and its not firing is the run's positive: the slot held `SIMSPR+0x6226` in both processes, confirming iso vt `+0x2c` at runtime |
| BC — crash | **no** — 2/2 loaded, 2/2 completed, 0 exceptions |
| **(unwritten row) — no MOVED intervals at all** | **this is what happened**, and I failed to pre-register it for the second time |

Install `stock (matches original/)` before and after — the vtable swap is memory-only and touches no
file on disk. No patch; claim held across both launches, lease per launch by the same owner, both
released.

---

# Caller census, adaptive design — PRE-REGISTRATION, written before any launch, 2026-08-25

**Stopping rule, declared in advance:**

> **Launch until one launch yields at least one MOVED interval. Maximum four launches. Report every
> launch, including frozen ones. Stop as soon as a launch churns — the maximum is a ceiling, not a
> quota.**

Farmsville via `-GamePath`, both `SC3PROBE_CAMWATCH=1` and `SC3PROBE_CAMCALLER=1`, no input, install
stock, one claim held across all launches with the lease taken per launch by the same owner.

## Cadence, and the disclosed trade

`GZMAXSEQ` is 32, so ~1 s cadence and a 30 s window remain mutually exclusive in one launch. This
time I am choosing **cadence over reach**, and the reason is in the data rather than in preference:
**all five onset brackets ever measured fall inside t+6.26 s to t+16.15 s** (6.26-7.42, 6.80-8.00,
7.82-8.73, 13.46-14.59, 13.51-16.15). A `wait:750` sequence covers roughly **t+5 s to t+20 s**, which
spans the entire observed onset range, at ~1.0 s intervals — the maximum interval resolution
available. Naming a caller needs resolution on the transition, not reach past t+20 s where no onset
has ever been seen. If all four launches freeze, that choice is a candidate explanation and I will
say so rather than defend it.

## Rows

| row | prediction | what it would mean |
|---|---|---|
| **BD** | callers named on a MOVING interval | resolve every return address. `FUN_1000ec0b` (the follow — would **contradict** `+0x354 == 0` on 30/30), `FUN_1001d503` or `FUN_10006736` (the two mapped dispatch sites), or **something unmapped**. The third is what a ~100 Hz call rate implies and is the interesting answer. |
| **BE** | the same caller on MOVING and still intervals | that caller is not the driver; the driver is whatever differs between the sets |
| **BF** | **MOVED with `calls=0`** | a second writer path, contradicting the 29/29 separation. **Bigger than the caller question**; report loudly. |
| **BG** | **ALL FOUR LAUNCHES FROZEN** | the phenomenon did not occur. Its **own outcome**, not a negative about the caller; frozen intervals still served as `still` controls. At `P(frozen) = 5/11` this has **p = 0.0427**, so if it happens it is worth stating that it was unlikely rather than shrugging. |
| **BH** | crash | the thunk is the first suspect — new code in a hot path |

## The extra measurement, registered now

The driver **starts and stops**, so **the transition is the interesting moment.** If a launch churns:
record which interval is the **first** to move, and whether the caller set on that interval **differs
from the later moving intervals**. What *starts* the motion may not be what *sustains* it, and that
distinction is only visible on the first moving interval.

---

# RESULT — **ROW BG FIRED: all four launches frozen post-load (p = 0.043).** But a caller WAS named, on the load transition — and a suppression signal has appeared that must be cleared first.

Four launches, the full pre-registered ceiling, **none of them churned after the city loaded**. Row BG
is the outcome. At `P(frozen) = 5/11` that is `p = 0.0427`, so this was unlikely rather than routine
and I am saying so rather than shrugging.

**But the run is not empty.** Three of the four captured the **city-load transition**, and on that
interval the caller census fired and named its caller identically in three independent processes.

## My stopping rule was defective, and it is the same defect a third time

I wrote the rule as *"until one launch yields at least one MOVED interval."* **H2 tripped it on
interval 1 — the city-load transition** (`zoom 0 -> 2`, `-508,-73 -> -160,1604`), which under the
**corrected churn criterion I myself published in this file after the E runs** is not churn at all.

So the rule I wrote to operationalise "churn" inherited the exact defect I had already found and
fixed for the churn criterion, and it stopped the sequence at two launches for the wrong reason.
This is the third instance of the same class of error from me (the twice-omitted all-frozen row, now
this): **fixing a definition in one place and not carrying it to the place that consumes it.**

**What I did about it, disclosed:** I corrected the detector to *a MOVED interval whose preceding read
was already post-load (`zoom == 2`)* and continued to the **pre-registered ceiling of four**. I did
not raise the ceiling, change a row, or alter the fixture. The correction applies a criterion that was
already published in this document before this run began — it is not a new rule invented after seeing
data. H3 and H4 were run under the corrected detector and both came back frozen.

## The caller, named — `SIMSPR + 0x674F` = `FUN_10006736 + 0x19`

```
[ 4740.496 ms] ### CAMC: interval 1  calls=1
[ 4740.531 ms] ### WIDGET: CAMC iv1 caller x1 [MOVING interval] (return address) 0x0348674F = SIMSPR.DLL + 0x674F  (export VA 0x1000674F)
```

Identical in **H2, H3 and H4** — three independent processes, same interval, same single call, same
return address.

`FUN_10006736` spans `0x10006736`-`0x10006751`, **28 bytes**, so `0x1000674F` is `+0x19`, the
instruction after its one `call` [CONFIRMED @ 0x1000674f]. Its entire body:

```c
void __thiscall FUN_10006736(int *param_1,int param_2,int param_3,undefined4 param_4)
{
  (**(code **)(*param_1 + 0x2c))(param_2 - param_1[0x15],param_3 - param_1[0x16],param_4);
  return;
}
```

**`param_1[0x15]` is `+0x54` and `param_1[0x16]` is `+0x58` — exactly the origin x/y the watchpoint
watches.** So `FUN_10006736` takes an **absolute** target, subtracts the current origin to make a
**relative delta**, and dispatches to `vt+0x2c` [CONFIRMED @ 0x10006736]. That is
**`ScrollTo(absolute)` implemented on top of `Scroll(relative)`**, and it is one of the two **mapped**
dispatch sites — **not** the unmapped answer the ~100 Hz rate suggested, and **not** `FUN_1000ec0b`.

`FUN_10006736` has **zero code xrefs** in the SIMSPR export (only its `symbols.csv` row), so like
`FUN_10006226` it is reached solely through a vtable slot.

**`[UNCERTAIN]` which slot.** The recorded follow path is `vt+0x148` -> `FUN_1000ec0b` -> `vt+0x30`
**ScrollTo**, and `FUN_10006736` has exactly the ScrollTo shape — so **`vt+0x30 == FUN_10006736` is a
hypothesis consistent with both facts, not a measurement.** The export contains no data dump of
`PTR_FUN_1006250c` and I did not read the slot at runtime. **If it is confirmed, it matters a lot:**
the load-time motion would be going through *the same final dispatch the follow path uses*, while
`+0x354 == 0` rules out `FUN_1000ec0b` as the caller — meaning something else calls ScrollTo. One more
expect-or-refuse swap, on `.rdata SIMSPR+0x6253c`, both confirms the slot and names ScrollTo's caller.

## The two instruments corroborate at single-event resolution

On every load-transition interval: `calls=1`, and **exactly one** store at `SIMSPR+0x62AF` (the
translate) plus one at `SIMSPR+0x68C9` (`SetZoom`, which does not route through `vt+0x2c`).

**One call in, one translate-store out — three times, in three processes.** The F-run separation was
statistical over 29 intervals; this is exact at n=1 per event. Row BF had no opportunity to fire and
nothing contradicts the 29/29 separation.

## The interval tables

**H1** — armed t+4.97 s, baseline already post-load `-160,1604`: intervals 1-14, t+5.91 s to
t+18.65 s, **all `still`, all `writes=0`, all `calls=0`**. No load transition captured.

**H2 / H3 / H4** — baseline `-508,-73` (`zoom=0 tilepx=8`, pre-city):

| iv | class | dx | dy | writes | calls | caller |
|---|---|---|---|---|---|---|
| 1 | MOVED (**city load**) | +348 | +1677 | 2 (`+0x62AF`, `+0x68C9`) | **1** | **`SIMSPR+0x674F`** |
| 2-15 | **still** | +0 | +0 | **0** | **0** | — |

H2 t+4.74-18.53 s, H3 t+5.03-18.89 s, H4 t+5.26-18.82 s. Post-load origin `-160,1604` on every
subsequent read in all three.

## ⭐ A suppression signal on CAMCALLER, and this one does not look like noise

| | launches | churn | frozen |
|---|---|---|---|
| before CAMCALLER existed | 11 | 6 | 5 |
| **with CAMCALLER armed** | **6** (G1, G2, H1-H4) | **0** | **6** |

Six consecutive frozen launches with the caller census armed. Under the pre-CAMCALLER rate
`P(churn) = 6/11 = 0.545`, six frozen in a row is **p = 0.45^6 = 0.0083**. I raised the mirror-image
concern about CAMWATCH on one sample and it was cleared by E2 and F1; **this is six samples and it is
an order of magnitude stronger than the signal I flagged then.** It has to be cleared before any
caller result is built on.

**Against a mechanism:** I inspected the thunk before the run and it is correct — `pushad`/`pushfd`
save all GP registers and flags, `[esp+36]` = 32+4 is the right return-address slot, `camc_record` is
`__cdecl` with a matching `add esp,4`, `__thiscall`'s `ecx` survives `pushad`/`popad`, and the `jmp`
leaves the caller's return address in place. And it demonstrably works: it recorded the load-time call
correctly in three processes.

**A competing explanation that needs excluding, and it is not the instrument.** Load times have drifted
**shorter** across the day as the file cache warmed: baselines were t+5.0-5.8 s in the F and G runs and
t+3.79-4.27 s in H2-H4. If the churn is a load-related transient, faster loads plausibly mean less of
it inside the sampling window. **CAMCALLER's arrival and the warm cache are confounded with each
other**, because every CAMCALLER launch came later in the day than every non-CAMCALLER launch.

**So the clean test is not a batch of unset launches — that would repeat the confound with time.**
It is **interleaved**: alternate CAMCALLER-set and CAMCALLER-unset launches within one session,
pre-registering the alternation and the count, so instrument and elapsed-session-time are crossed
rather than confounded. That design answers both explanations at once, and nothing else I can think of
does.

## Validity

0 keys in all four; 25 `Farmsville.sc3` filetrace hits each; **0 exceptions, 0 minidumps** in any
launch (row BH did not fire); all four sequences `COMPLETE`, all four shots written; expect-or-refuse
passed in all four (slot held `SIMSPR + 0x6226` each time — now runtime-confirmed in **six** processes).
`followTarget(+0x354) = 0` on **63/63** reads across these four launches, and on every read since run C.
`N == 1` on 63/63. `span = 1024x768` on 63/63 reads for both rects = 126 prints, **cumulative 418/418**.

## Which rows fired

| row | status |
|---|---|
| BD — callers named on a MOVING interval | **partially** — named on the **load transition** (`FUN_10006736+0x19`, a **mapped** dispatch site, `ScrollTo`), reproduced 3/3. **The churn caller remains unnamed** — no post-load MOVED interval occurred. |
| BE — same caller on moving and still | **no** — no still interval had any calls |
| BF — MOVED with `calls=0` | **no** — no opportunity; the 29/29 separation is untouched |
| **BG — all four launches frozen** | **FIRED**, `p = 0.0427`. Frozen intervals served as `still` controls throughout. **Not** a negative about the caller. |
| BH — crash | **no** — 4/4 loaded, 4/4 completed, 0 exceptions |

## Where this leaves it

**Gained:** `ScrollTo` (`FUN_10006736`) is a confirmed caller of the translate, its exact arithmetic
is known (`target - origin`), single-event instrument corroboration, and a concrete next target
(`.rdata SIMSPR+0x6253c`).

**Blocked:** the churn has not been observed in **seven** consecutive launches, six of them with
CAMCALLER armed. **The next run should be the interleaved control, not another caller attempt** — at
`p = 0.0083` the suppression signal is now the largest uncontrolled variable in this thread, and
naming a churn caller while it stands would produce a result nobody could trust.

Install `stock (matches original/)` before and after — the vtable swap is memory-only. No patch; one
claim held across all four launches, lease per launch by the same owner, both released.

---

# Interleaved CAMCALLER control — PRE-REGISTRATION, written before any launch, 2026-08-25

Six launches with CAMCALLER armed have now all frozen (`p = 0.0083` under the prior rate), but every
one of them came later in the session than every unarmed launch, so **instrument and warm file cache
are perfectly confounded**. A batch of unset launches now would repeat that confound with time. This
design crosses them instead.

> **Design, declared in advance: SIX launches, strictly alternating, STARTING UNSET —
> unset, set, unset, set, unset, set. All six run regardless of outcome. No early stopping.**

Starting unset puts an unset launch in the **coldest** slot and an armed launch in the **warmest**, so
if warm cache is the real cause its effect runs **against** the instrument rather than with it. That
is deliberately the harder test for the warm-cache story, which is currently the more comfortable
explanation and therefore the one worth stressing.

**`SC3PROBE_CAMWATCH=1` on all six**, so the writer census is constant and **only `CAMCALLER` varies** —
one variable at a time. Farmsville via `-GamePath`, no input, install stock, one claim across all six
with the lease per launch.

**Churn detector, correct from the start this time:** a MOVED interval whose **preceding read was
already post-load (`zoom == 2`)**. Three criteria in this thread have now been defined correctly in
one place and consumed defectively in another; this one is wired in before the first launch rather
than patched mid-run.

**Cadence:** `wait:750` (~1.0 s intervals, ~t+5 s to t+20 s), the same sequence as G1, G2 and H1-H4.
The `GZMAXSEQ` = 32 ceiling still forbids ~1 s cadence and a 30 s window together, and here
**consistency with the launches being compared outranks reach** — a control that changed the cadence
would confound a third variable. All five onset brackets ever measured (t+6.26 to t+16.15 s) fall
inside this window.

**Load baseline recorded for every launch** — the timestamp of the first `cam` read, plus the
pre-city -> post-load transition where captured.

| row | outcome | what it would mean |
|---|---|---|
| **BI** | **any ARMED launch churns** | **suppression is dead outright.** One suffices; no statistics needed. |
| **BJ** | any **UNSET** launch **late** in the session freezes | warm cache weakened — freezing would then occur without the instrument at a warm cache |
| **BK** | all three armed frozen **AND** all three unset churn | suppression strongly supported. If the instrument were inert this pattern has **p = 0.015**; stated in advance so it cannot be quoted loosely afterwards. |
| **BL** | mixed, no clean split | **neither hypothesis is carried.** A real outcome at n = 6; the table gets reported and nothing gets squeezed into a story. |
| **BM** | **load baselines do NOT shorten across the session** | the warm-cache hypothesis **loses its factual basis entirely**, independent of any churn data. It rests on an observed drift from ~5.0-5.8 s to ~3.8-4.3 s; if that does not continue or reverses, the explanation weakens on its own terms. |
| BN | crash | thunk first suspect on armed launches; on unset launches it cannot be the thunk |

---

# RESULT — **ROWS BL AND BM FIRED. All six frozen, armed and unset alike. Neither hypothesis survives, and my warm-cache evidence was selection.**

Six launches, strict alternation, no early stopping. **Every one frozen post-load.**

| # | run | CAMCALLER | first-read baseline | load transition | verdict | first motion |
|---|---|---|---|---|---|---|
| 1 | I1 | **unset** | 4998 ms | (not captured) | **FROZEN** | — |
| 2 | I2 | **SET** | 3825 ms | 4776 ms | **FROZEN** | — |
| 3 | I3 | **unset** | 4822 ms | (not captured) | **FROZEN** | — |
| 4 | I4 | **SET** | 4868 ms | (not captured) | **FROZEN** | — |
| 5 | I5 | **unset** | 4315 ms | (not captured) | **FROZEN** | — |
| 6 | I6 | **SET** | 4704 ms | (not captured) | **FROZEN** | — |

**Armed: 0 churn of 3. Unset: 0 churn of 3.** The instrument variable produced no split whatsoever.
Row BI did not fire (no armed launch churned) and row BK did not fire (the p = 0.015 pattern did not
appear). **Row BL is the outcome** — and I am reporting the table rather than squeezing it into a
story, which is what that row exists for. Its wording says "mixed"; the actual result is *uniform*,
which is the same thing for its purpose: **armed and unset are indistinguishable, so suppression is
not supported.**

Under a suppression model the three unset launches should have churned at the historical rate;
three unset freezes has `p = 0.455^3 = 0.094`. Not decisive alone, but it points the same way as E2
did for CAMWATCH: **freezing happens without the instrument.**

## Row BM fired, and it takes my own hypothesis down

**Load baselines did not shorten.** Across all fourteen launches since F1 the first-read baseline
oscillates between **3789 ms and 5760 ms with no trend** — mean of the first three is **4566 ms**,
mean of the last three is **4629 ms**, i.e. slightly *longer*.

On the cleaner measure it is the same. The **load transition** (`zoom 0 -> 2`) is only available for
launches whose first read caught the pre-city state: F2 = 5589, H2 = 4740, H3 = 5025, H4 = 5265,
**I2 = 4776**. Earliest to latest is `-813 ms` of noise, not a drift, and the latest launch is slower
than two earlier ones.

**And I have to correct myself on how I produced the drift in the first place.** I reported it as
"~5.0-5.8 s in the F and G runs, ~3.8-4.3 s in H2-H4". Looking at the full list, **F2 was 3838 ms** —
as short as anything in H — and I compared G1/G2 (the two highest values in the set) against H2-H4
(three of the lowest). **That was selection, and I presented it as a trend.** It is the same failure
mode as the criterion errors: a claim assembled from the subset that fit.

There is also a mechanical reason the first-read baseline was never a good proxy: it fires as soon as
the city view exists, so a launch that catches the **pre-city** state (`zoom=0`) times earlier than one
that catches the loaded state. Every "short" baseline in my list (F2 3838, H2 3789, H3 4076, H4 4266,
I2 3825) is a **pre-city** catch and every "long" one is a post-load catch. **The variable I called
load speed was mostly which state the sampler happened to land on.**

**So the warm-cache hypothesis loses its factual basis entirely**, exactly as row BM anticipated, and
it loses it independently of any churn data.

## I also have to flag the inference attached to row BJ, because it is backwards

Row BJ read: *"any UNSET launch late in the session freezes -> warm-cache weakened, since freezing
would then occur without the instrument at a warm cache."*

Unset launches froze (I1, I3, I5), so the row's **condition** fired. But the conclusion does not
follow. Freezing without the instrument at a warm cache is **what the warm-cache hypothesis
predicts** — it is evidence *for* that story, not against it. What unset-and-frozen actually weakens
is **suppression**, because it shows the freeze does not need the instrument.

So BJ's condition fired with its stated inference inverted. Warm cache is dead here on **row BM's**
evidence (no drift), not BJ's. Recording the correction rather than adopting the row as written.

## What neither hypothesis explains, and it is now the main fact

**Thirteen consecutive frozen launches since F1**: F2, G1, G2, H1, H2, H3, H4, I1, I2, I3, I4, I5,
I6. At the pre-F1 rate `P(churn) = 6/11` that streak has **`p = 3.5e-5`**.

And the two candidate explanations are now both out:

- **Not the instrument** — unset launches froze at the same rate as armed, in an interleaved design
  built to detect exactly that.
- **Not the warm cache** — no baseline drift on either measure, and the proxy I used for it was
  selected.
- **Not the probe build** — F1 (churn) and F2 (frozen) ran on the *same* binary minutes apart.
- **Not the fixture, not input, not the sim, not elapsed time** — all previously eliminated.

Something changed around F1 -> F2 and has held for thirteen launches. I checked the obvious candidate,
persistent state written by the game: the only install file touched today is `Apps/SC3U_stkdmp.txt`,
last written **09:02:50**, hours before this session began, and `Cities\Farmsville.sc3` is untouched.
So no file in the install changed under these runs. `[UNCERTAIN]` what did change; I could not measure
it, and I am not going to name a mechanism I have not tested.

## Free confirmations, four processes deep

I2 caught the load transition and reproduced the caller **exactly**:

```
[ 4775.705 ms] ### CAMW: interval 1  dx=+348 dy=+1677  MOVED  writes=2
[ 4775.732 ms] ### WIDGET: CAMW iv1 writer x1 [MOVING interval] (instr AFTER store) 0x034762AF = SIMSPR.DLL + 0x62AF
[ 4775.753 ms] ### WIDGET: CAMW iv1 writer x1 [MOVING interval] (instr AFTER store) 0x034768C9 = SIMSPR.DLL + 0x68C9
[ 4775.773 ms] ### CAMC: interval 1  calls=1
[ 4775.792 ms] ### WIDGET: CAMC iv1 caller x1 [MOVING interval] (return address) 0x0347674F = SIMSPR.DLL + 0x674F
```

`SIMSPR+0x674F` = `FUN_10006736+0x19` = **`ScrollTo`**, now confirmed as iso vt `+0x30` from the
anchored binary. **Four independent processes** (H2, H3, H4, I2), identical single call, identical
one-call-in / one-translate-store-out correspondence. The load-time path is settled:
**something calls `ScrollTo(vt+0x30)` once at city load, which subtracts the origin and dispatches to
the translate (`vt+0x2c`), while `+0x354 == 0` rules out `FUN_1000ec0b`.**

## Validity

0 keys in all six; 25 `Farmsville.sc3` filetrace hits each; **0 exceptions, 0 minidumps** (row BN did
not fire); 6/6 sequences `COMPLETE`. Expect-or-refuse passed on all three armed launches (slot held
`SIMSPR+0x6226`), now runtime-confirmed in **nine** processes. `followTarget(+0x354) = 0` on 91/91
reads. `N == 1` on 91/91. `span = 1024x768` on 91/91 reads, both rects, **cumulative 600/600**.

## Which rows fired

| row | status |
|---|---|
| BI — any ARMED launch churns | **no** — 0 of 3 |
| BJ — any UNSET launch late in session freezes | **condition fired** (I1, I3, I5) — but **its stated inference is inverted**; it weakens suppression, not warm cache |
| BK — all armed frozen AND all unset churn (`p = 0.015`) | **no** — unset did not churn either |
| **BL — no clean split, neither hypothesis carried** | **FIRED** — 0/3 vs 0/3, the instrument variable had no effect |
| **BM — load baselines do NOT shorten** | **FIRED** — no drift on either measure; the warm-cache hypothesis loses its factual basis, and my evidence for it was selection |
| BN — crash | **no** — 6/6 loaded and completed |

## Where this leaves it

**Cleared:** CAMCALLER is exonerated — the suppression signal I raised was real as a pattern but does
not survive a crossed design. Nothing built on the armed runs needs withdrawing, and the caller
identification stands on four processes.

**Open, and it is now the blocking fact:** the churn has not been observed in thirteen consecutive
launches, and every variable proposed so far has been eliminated, including both of mine. **The next
step should not be another launch on this fixture.** Thirteen launches at `p = 3.5e-5` says the
phenomenon's precondition is gone rather than rare, and the productive question is what the *early*
session had that the last thirteen launches did not. The cheapest thing that would actually move it:
**re-run one of the exact early configurations** — an A/B/C-era switch set and sequence, unchanged —
and see whether churn returns. If it does, the difference is in the harness configuration and is
bisectable. If it does not, the precondition is in machine or session state and no amount of sampling
this fixture will recover it.

Install `stock (matches original/)` before and after; the vtable swap is memory-only. No patch; one
claim across all six launches, lease per launch by the same owner, both released.

---

# Era replay — PRE-REGISTRATION, written before any launch, 2026-08-25

## What is and is not recoverable, established before designing the run

- **Run A cannot be reproduced faithfully.** Its section in this file records read cadence
  (~1.12 s, t+16.6-32.4 s) and validity counts but **no launch line**, and
  `re/sessions/PREREG_512_gameplay.md` records only a *different*, keyed sequence
  (`wait:15000;cam;key:0x25,2500;cam;wait:180000`). The A-era invocation was never written down.
- **Runs B and C are fully recoverable** — both are from this session and their `sc3launch` command
  lines are on the record verbatim.
- **The probe build is unrecoverable** (`re/harness/` is gitignored, no history), so the replay can
  vary **switches and sequence only**, against the current binary.

## The switch diff is EMPTY, and that is a finding before a single launch

The C-era switch string was
`-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace`
and the current standard string is **byte-identical**. `capture.ps1` adds the same
`-shot -gzlog -log` in both eras. **No switch existed in the B/C era and is absent now.** The
cheapest bisection candidate list the coordinator asked for is therefore **empty** — nothing to
bisect on switches.

(For completeness: the *citysize* investigation of the same era used the string without
`-filetrace` and with `-modlog SIMCITY.DLL:0x10003ea6`. That is a different investigation on a
different fixture and is not the camera era's invocation.)

**So the only thing that differs between the churning era and the recent launches is the `-GzSeq`
cadence:** C used `cam` + 8x(`wait:1000`,`cam`) + 7x(`wait:2500`,`cam`); the recent frozen launches
used `wait:750` x15 (F1, G1, H1-H4, I1-I6) or `wait:1500` x15 (F2, G2).

## And the sequence hypothesis is ALREADY falsified by data in hand

This has to be said before spending launches. **C, D, E1, E2 and E3 all ran the identical switch
string AND the identical `-GzSeq`** — and produced **churn, frozen, churn, frozen, churn**. The same
invocation gave both outcomes inside one block. **Switches and sequence therefore cannot be the
discriminator**, and the first branch of the decision procedure ("churn returns => bisect
switches/sequence") is already known to be a dead end even if churn returns.

What the replay can still decide is **temporal**: does the exact C-era invocation churn *now*, after
thirteen consecutive freezes? That is worth measuring, and it is the only thing this run can settle.

## The invocation being replayed, unchanged

```
capture.ps1 -Name <n> -GamePath <Cities\Farmsville.sc3>
  -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace"
  -GzSeq "cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam"
  -AtSec 150
```
**`SC3PROBE_CAMWATCH` and `SC3PROBE_CAMCALLER` both UNSET** — neither existed when C ran, so arming
either would not be a replay.

## Launch count, declared now

**Adaptive, with the corrected post-load detector** (a MOVED interval whose preceding read was
already `zoom == 2`): **launch until one launch churns, maximum four, report every launch.** Same
rule and same ceiling as the H block, with the detector correct from the start this time.

| row | outcome | what it would mean |
|---|---|---|
| **BO** | churn returns | difference is in switches/sequence and is bisectable — **but see above: C/D/E1/E2/E3 already crossed that variable, so I would treat a return as temporal recovery, not as a sequence effect, and the first thing I would bisect is nothing on the switch list (it is empty) but the `wait:1000/2500` versus `wait:750` cadence, purely because it is the only remaining difference** |
| **BP** | all four frozen | difference is **build or machine/session state**, and those are **not separable** because the build is unrecoverable. Stated plainly, attributed to neither. |
| **BQ** | the old invocation cannot be reproduced faithfully | **already fired for run A** before launching (no recorded launch line). Reported as the diff it is. |
| **BR** | crash or failure to load | instrument or fixture; report and stop |
| **BS** | **all four frozen** (the row omitted three times, written here explicitly) | the phenomenon did not occur; frozen intervals still serve as `still` controls; **not** a negative about switches or sequence |

---

# RESULT — **ROW BO fired, in the weakest form the row admits. Motion returned once, at t+32.9 s — beyond the window every recent launch sampled.**

Three launches of the exact C-era invocation, adaptive rule, stopped on the third.

| # | run | baseline | window reached | verdict | first motion |
|---|---|---|---|---|---|
| 1 | J1 | 3721 ms (pre-city) | t+32.38 s | **FROZEN** | — |
| 2 | J2 | 4107 ms (pre-city) | t+33.65 s | **FROZEN** | — |
| 3 | **J3** | 5102 ms (post-load) | t+32.94 s | **CHURN** | **iv14, t+32.94 s, `dx=+0 dy=+566`** |

**J3 is the first post-load motion in sixteen consecutive launches** (F2, G1, G2, H1-H4, I1-I6, J1,
J2 frozen; J3 moved).

## The invocation replayed, and the diff against the current standard

```
capture.ps1 -Name J<n> -GamePath <Cities\Farmsville.sc3>
  -Switches "-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace"
  -GzSeq "cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:1000;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam;wait:2500;cam"
  -AtSec 150
SC3PROBE_CAMWATCH and SC3PROBE_CAMCALLER both UNSET (neither existed when C ran)
```

**Switch diff: EMPTY.** The C-era string and the current standard string are byte-identical, and
`capture.ps1` adds the same `-shot -gzlog -log` in both eras. **No switch existed in the B/C era and
is absent now** — the bisection candidate list from switches is empty, established before launching.

**The only difference is the `-GzSeq`,** and it changes two things at once: cadence (~1.24 s then
~2.7 s, versus a flat ~1.0 s) **and total window** (t+33 s versus t+18-20 s).

**Row BQ fired before any launch: run A cannot be reproduced faithfully.** Its section records read
cadence and validity counts but **no launch line**, and `re/sessions/PREREG_512_gameplay.md` records
only a different, keyed sequence (`wait:15000;cam;key:0x25,2500;cam;wait:180000`). B and C are
recoverable; A is not, and was never written down.

## ⭐ The structural fact, and it is the useful output of this run

**All three replay launches reached ~t+33 s. The twelve `wait:750` launches (G1, H1-H4, I1-I6, F1)
ended at ~t+18-20 s. The single motion observed happened at t+32.94 s — outside the window those
launches could ever have sampled.**

That is a concrete, bisectable candidate and it is **window length, not cadence** — which is what I
pre-registered as the first thing I would bisect, arrived at for a better reason than I had then.

**But I am not going to oversell it, and here is the evidence against:** `F2` and `G2` used
`wait:1500` and reached t+28.4 s and t+30.1 s, both frozen; `J1` reached t+32.4 s and `J2` t+33.6 s,
both frozen. So a long window does **not** by itself produce motion — 1 of 5 long-window launches
moved, once. Window length is now the **only remaining** difference on the table, not a demonstrated
cause.

## And this event is not the churn regime

Reported precisely, because the difference matters:

| | churn regime (A, C, E1, E3, F1) | **J3, iv14** |
|---|---|---|
| motion | both axes, oscillating | **`dx=0`**, y only |
| magnitude | mean \|dx\| ~1,080-1,317 px per interval, peaks 2,700-3,400 | **+566 px, once** |
| duration | 7-13 consecutive moving intervals | **1** |
| translate calls | 66-150 per ~0.9 s interval | **not measured** (see below) |
| quantisation | mixed; tile-locked in late windows | 566 is not a multiple of 32 |

`rectB` moved with `rectA` and `span` held at `1024x768`, so it is a rigid translation like every
other motion in this file. `followTarget(+0x354) = 0` on that read as on all others.

**It satisfies the pre-registered criterion and I am scoring it as row BO. It does not resemble the
phenomenon the criterion was written to catch,** and calling one 566 px y-shift "the churn has
returned" would be exactly the squeezing-into-a-story that row BL exists to prevent.

## The cost of fidelity, stated plainly

The replay ran with **both env vars unset**, because neither existed when C ran. So the probe printed
`writes=0  (watchpoint disabled)` on every interval, including J3's moving one. **`writes=0` here is
not a measurement** — it is the instrument reporting itself off. **I have no writer or caller
information for the one motion this run produced.** That is the direct price of fidelity, and it was
the right trade for the question asked, but it means J3 tells us *when* and *how much*, not *who*.

## Which rows fired

| row | status |
|---|---|
| **BO — churn returns** | **FIRED**, weakly: 1 launch of 3, 1 interval, `dx=0 dy=+566`, at t+32.94 s. Bisection candidate is **window length** (t+33 vs t+18-20), the only remaining difference; the switch list is empty. |
| BP — all four frozen => build or machine/session state, not separable | **no** — J3 moved |
| **BQ — old invocation not faithfully reproducible** | **FIRED for run A**, before launching: no launch line was ever recorded. B and C were reproduced exactly. |
| BR — crash or failure to load | **no** — 3/3 loaded, 3/3 `COMPLETE`, 0 exceptions |
| BS — all four frozen (the row omitted three times) | **no** — did not arise, but it was written this time |

## Validity

0 keys in all three; 25 `Farmsville.sc3` filetrace hits each; 0 exceptions, 0 minidumps; 3/3
sequences `COMPLETE` (31 steps each); 3 shots per launch. `followTarget(+0x354) = 0` on 47/47 reads.
`N == 1` on 47/47. `span = 1024x768` on 47/47 reads, both rects = 94 prints, **cumulative 694/694**.
The load-time origin `-160,1604` reproduced again in all three.

## Where this leaves it

**Settled by this run:** the switch set is not the difference — the diff is empty and that is now a
closed question rather than a suspicion. Run A's invocation is unrecoverable and should stop being
treated as a reference point.

**The single remaining difference between the churning era and the frozen streak is the sampling
window**, and the one motion recovered sits outside the short window. **The next run is therefore a
clean two-arm test and needs no new instrument:** the same launch repeated at `wait:750` (t+20) and at
the C-era sequence (t+33), interleaved as in the I block, with `SC3PROBE_CAMWATCH=1` so a motion
carries writer data — **arming CAMWATCH is safe here because F1 already churned with it on**, so it
is not a fidelity violation the way arming it during this replay would have been.

If the long-window arm moves and the short arm does not, the freeze streak was substantially a
sampling artefact and thirteen of those "frozen" verdicts need re-reading as "not sampled long
enough". If neither moves, the J3 event was a rare tail and the difference remains **build or
machine/session state — which are not separable, because `re/harness/` is gitignored and the A/B/C-era
binary cannot be rebuilt.**

Install `stock (matches original/)` before and after. No patch; one claim across all three launches,
lease per launch by the same owner, both released.

---

# Window-length two-arm test — PRE-REGISTRATION, written before any launch, 2026-08-25

**A correction to my own last report, accepted before designing this run.** I offered window length as
"the only remaining difference", and it **does not survive the data already in hand**: three of the
five recorded onsets sit well inside a short window — E1 at t+6.26-7.42 s, C at t+6.80-8.00 s, F1 at
t+7.82-8.73 s. A `wait:750` arm reaching ~t+20 s **would have sampled all three**, and thirteen
short-window launches saw nothing there. From the other side, only **1 of 5** long-window launches
moved. So window length is already weak as an explanation.

**That makes the short arm a direct re-test of those three onsets rather than a mere control**, which
is what makes this run worth six loads.

> **Design: SIX launches, strictly alternating, STARTING SHORT — short, long, short, long, short,
> long. All six run. No early stopping.**

- **Short arm** = `cam` + 15x(`wait:750`,`cam`), reaching ~t+20 s.
- **Long arm** = the C-era sequence, `cam` + 8x(`wait:1000`,`cam`) + 7x(`wait:2500`,`cam`), reaching
  ~t+33 s.
- **Only the sequence varies.** Switches identical
  (`-nocom -windowed -origin -fix16 -fitclient -nointro -quiet -filetrace`), Farmsville via
  `-GamePath`, `-AtSec 150`, no input, install stock.
- **`SC3PROBE_CAMWATCH=1` on all six.** Legitimate rather than a fidelity violation, because **F1
  churned with it armed** — it is not a suppressor. `SC3PROBE_CAMCALLER` stays **unset** on all six so
  exactly one variable moves.
- Churn detector: the corrected one — a MOVED interval whose preceding read was already `zoom == 2`.

| row | outcome | what it would mean |
|---|---|---|
| **BT** | long arm moves, short does not | freeze streak substantially a **sampling artefact**; the thirteen frozen verdicts get re-read as *"not sampled long enough"*, and I will name **which** specifically |
| **BU** | **short arm moves at t+6-9 s** | **window length is dead outright**, the early onsets are reproducible, and the streak had another cause. The outcome that most changes the picture. |
| **BV** | both arms move | window length irrelevant; onsets reported per arm |
| **BW** | neither moves | `p = 0.0088` if window length is irrelevant. J3 was a tail, and the difference remains **build or machine/session state — not separable**, since `re/harness/` is gitignored and the era binary cannot be rebuilt. |
| **BX** | motion of **J3's shape** (single axis, one interval) rather than the regime's (7-13 consecutive both-axes intervals at >1,000 px) | **scored as its own row in either arm.** A 566 px blip is not the churn returning. |

**If anything moves, `CAMWATCH` is armed, so the moving interval carries writer data — the EIPs get
reported.** J3's motion was uninstrumented and this run should not repeat that.

---

# RESULT — **ROW BW FIRED. Neither arm moved. Window length is dead, and so is the reproducibility of the early onsets.**

Six launches, strict alternation, no early stopping. **Zero post-load motion in either arm.**

| # | run | arm | window reached | verdict | first motion | writer EIPs |
|---|---|---|---|---|---|---|
| 1 | K1 | **short** | t+18.8 s | **FROZEN** | — (load transition only, iv1) | `SIMSPR+0x62AF` x1, `SIMSPR+0x68C9` x1 |
| 2 | K2 | **long** | t+33.1 s | **FROZEN** | — (no load transition captured) | — |
| 3 | K3 | **short** | t+18.7 s | **FROZEN** | — (load transition only, iv1) | `SIMSPR+0x62AF` x1, `SIMSPR+0x68C9` x1 |
| 4 | K4 | **long** | t+32.6 s | **FROZEN** | — (load transition only, iv1) | `SIMSPR+0x62AF` x1, `SIMSPR+0x68C9` x1 |
| 5 | K5 | **short** | t+18.9 s | **FROZEN** | — (load transition only, iv1) | `SIMSPR+0x62AF` x1, `SIMSPR+0x68C9` x1 |
| 6 | K6 | **long** | t+32.7 s | **FROZEN** | — (no load transition captured) | — |

**Short arm: 0 of 3. Long arm: 0 of 3.** Row BT did not fire (long did not move), row BU did not fire
(short did not move), row BV did not fire, and **row BX had nothing to score** — no motion of any
shape, J3's or the regime's, in six launches.

## The short arm was a direct re-test of three recorded onsets, and it failed three times

This is the part that matters more than the window question. E1 (t+6.26-7.42 s), C (t+6.80-8.00 s)
and F1 (t+7.82-8.73 s) all began churning inside a band the short arm samples at ~1.0 s resolution.
K1, K3 and K5 each covered t+5 s to t+18.8 s and saw **nothing**.

Counting every short-window launch since F1 — G1, H1-H4, I1-I6, K1, K3, K5 — that is **fifteen
launches covering the t+6-9 s onset band with zero onsets.** If the early onsets were still
reproducible at the rate they were observed (3 of 5 recorded onsets fall in that band), fifteen
consecutive misses has `p = 1.1e-06`.

**So the early onsets are not merely unsampled. They are not reproducible.** That closes the
last version of the sampling-artefact story, including the one I proposed last run.

## The overall streak, stated once and precisely

Twenty-two launches since F1: **21 frozen post-load, 0 showing the churn regime, 1 (J3) showing a
single-interval 566 px y-only blip.** At the pre-F1 rate `P(churn) = 6/11`, twenty-one frozen has
`p = 6.4e-08`.

Every variable proposed by either of us has now been eliminated by measurement:

| candidate | how it died |
|---|---|
| the fixture, input, the sim, elapsed time | eliminated earlier in this file |
| `CAMWATCH` suppression | E2 froze without it; F1 churned with it |
| `CAMCALLER` suppression | interleaved I block, 0/3 armed vs 0/3 unset |
| warm file cache | no baseline drift on either measure; my evidence for it was selection |
| switch set | diff is **empty** — byte-identical between eras |
| sequence / cadence | C, D, E1, E2, E3 ran the *same* sequence and gave churn, frozen, churn, frozen, churn |
| **window length** | **this run** — long arm 0/3, and the short arm re-tested three early onsets and missed all three |

## "Not separable" is now confirmed by search, not just by argument

I said the probe build could not be replayed because `re/harness/` is gitignored. I went looking
anyway. The only other `sc3probe.dll` on disk is
`.happy-share/.../SC3000-portable/sc3probe.dll` — **159,744 bytes, dated 08-17**, SHA-256 prefix
`32f03e5b59b4c511`. The B/C-era binary was **244,736 bytes** and dated 08-25. The archived copy
predates the `cam` candidate enumeration entirely and is eight days older than the era in question,
so it is **not** an era replay and running it would substitute a third unknown rather than resolve
one.

**The era binary is genuinely gone.** So the residual difference is **build or machine/session state,
and those two cannot be separated with the artefacts that exist.** That is the honest terminal state
of this line of inquiry, and it is row BW as written.

## Free confirmation, now eight processes deep

Four of the six launches caught the city-load transition, and all four reproduced the load-time
writer pair exactly: **`SIMSPR+0x62AF` (`FUN_10006226+0x89`, the translate) x1 and `SIMSPR+0x68C9`
(`FUN_10006752+0x177`, `SetZoom`) x1**, one store each. With H2, H3, H4 and I2 that is **eight
independent processes** with an identical load-time signature.

The load-time path is the one part of this investigation that is fully nailed down:
**something calls `ScrollTo` (`FUN_10006736`, iso vt `+0x30`) once at city load; it subtracts the
current origin and dispatches to the translate at `vt+0x2c`; `SetZoom` writes the rect in the same
interval; and `+0x354 == 0` rules out `FUN_1000ec0b` throughout.**

## Which rows fired

| row | status |
|---|---|
| BT — long moves, short does not | **no** — long 0/3 |
| BU — short moves at t+6-9 s | **no** — short 0/3, and this was a direct re-test of three recorded onsets |
| BV — both arms move | **no** |
| **BW — neither moves** | **FIRED** (`p = 0.0088` under the row's model). J3 was a tail; the residual difference is **build or machine/session state, not separable** — now confirmed by search, not just by the gitignore argument. |
| BX — J3-shaped motion rather than the regime's | **nothing to score** — no motion of either shape |

## Validity

0 keys in all six; 25 `Farmsville.sc3` filetrace hits each; **0 exceptions, 0 minidumps**; 6/6
sequences `COMPLETE`. `followTarget(+0x354) = 0` on 94/94 reads. `N == 1` on 94/94.
`span = 1024x768` on 94/94 reads, both rects = 188 prints, **cumulative 882/882**. The load-time
origin `-160,1604` reproduced in all six.

## My recommendation: stop sampling this fixture

Twenty-two launches, seven eliminated variables, and `p = 6.4e-08` against the phenomenon still being
present at its old rate. **The precondition for the churn is gone, not rare, and the one artefact that
could distinguish "gone because the build changed" from "gone because the machine/session changed" no
longer exists.** More launches on Farmsville will produce more frozen verdicts at a cost of one lease
each and will not decide anything.

What is still worth doing, in order:

1. **Bank what is solid.** The load-time path is measured to instruction level across eight
   processes. The writer, the caller, the arithmetic (`target - origin`), the vtable slots and the
   rigid-translation invariant (882/882) are all confirmed and do not depend on the churn.
2. **If the churn matters, change the fixture rather than resample this one.** Every churn observation
   in this file is Farmsville. Craterville was reported stable early on. A fixture that churns *today*
   would restore the phenomenon and make the instruments useful again; a sweep of the other
   `Cities\*.sc3` at one launch each is the cheapest way to find one.
3. **Prevent the recurrence of the unrecoverable-build problem.** The reason this ended in an
   unanswerable question is that `re/harness/` has no history. Archiving `sc3probe.dll` with its
   SHA-256 alongside each RESULTS entry would have made today's final question a two-minute check.

Install `stock (matches original/)` before and after. No patch; one claim across all six launches,
lease per launch by the same owner, both released.
