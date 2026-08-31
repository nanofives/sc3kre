# PRE-REGISTRATION — HUD lab: surface census + sampling profiler (2026-08-31)

**One lease, one build, two read-only instruments, one within-run control.**

## Why this run exists

Two claims closed the HUD workstream. Neither was measured.

1. **"The full-width HUD bar's FPS cost is intrinsic to per-frame compositing."**
   `verify/resize_hud/RESULTS.md` reaches this by elimination: three hypotheses falsified (device
   batch, iso overlap, per-tick invalidate) plus a read of `FUN_10026144` showing it is not an
   invalidator. **No one has ever measured where frame time goes.** This is the board's own recurring
   failure mode — asserting a cause from structure instead of building the instrument
   (see the crash-arc scorecard: three asserted causes, three refutations, settled only by the SEH
   catcher). This run builds the instrument.

2. **"The HUD children are a class our model does not cover."**
   The 2026-08-31 diagnostic found all 6 children `g_hud_top[0x2a..0x2f]` carry vtable
   `GZGraphicD+0x1E894` and read that as the model being wrong at a new layer. **`+0x1E894` is the
   raster surface base class this project already mapped** — `LAUNCH_CONTROL.md:4048` logs a device
   with that exact vtable, `RESIZE_DELIVERY_COST.md:47` names it "raster (`+0x1E894`)", and
   `rz_census_one()` in `sc3resize.c:338` already reads that family: dims `+0x24/+0x28`, bpp `+0x10`,
   sub `+0x44`, raw bits `sub+0xf0`, pitch `sub+0xf4`.

   Under that reading the two blockers are one fact: **the bar is composited from fixed-extent raster
   surfaces.** `vt+0xcc` being a flag getter (`FUN_10009ea2`) and `+0xe0` being garbage are then
   expected, not anomalies — a surface has no set-position.

## Hypothesis under test

**H:** the HUD bottom bar's children are raster surfaces of the `GZGraphicD+0x1E894` family whose
extent is fixed at construction, and the full-width FPS cost is the per-frame blit of a widened bar
region — attributable to a nameable function, not diffuse "compositing".

## Instruments (both READ-ONLY except the one SetRect already proven safe)

### I1 — HUD surface census
For each child `g_hud_top[0x2a..0x2f]`: vtable identity (is it `gz+0x1E894` / `gz+0x1F328`?), dims
`+0x24/+0x28`, bpp `+0x10`, sub `+0x44`, raw `sub+0xf0` bits and `sub+0xf4` pitch, plus a non-zero
pixel census. Reuses the validated raw-read discipline: **never call `vf1c` out of band** (standing
rule — the out-of-band lock tears the backing down).

Logged **twice**: before the SetRect widen and after it.

### I2 — EIP sampling profiler
A dedicated sampler thread suspends the game render thread, reads `Eip` via `GetThreadContext`,
resumes, and buckets by `eip >> 6` (64-byte granularity) in a lock-free open-addressed table.
Nothing is logged while the thread is suspended. Game thread id is captured in the existing
heartbeat hook (`fnlog_enter` idx 1), which already runs on the render thread. At dump time each
bucket resolves through `rz_modstr` to `MODULE+0xRVA`; top 30 by count.

## The within-run control — this is what makes the run decidable

Both phases run in **the same process, same city, same window size, same zoom**. The only variable
is the bar's width. The fixture supplies its own control, the pattern that made the `+0x140`
suspend-depth result clean.

| phase | bar state | duration | what is collected |
|---|---|---|---|
| A | **native 800-wide** (SetRect NOT yet applied) | 10 s | profile A + surface census (native) |
| B | **docked full-width** (SetRect applied) | 10 s | profile B + surface census (post-widen) |

Driven by a phase machine ticking in the per-frame poll (game thread), so the SetRect stays on the
thread that already performed it safely. Step 12 arms the machine; it does not widen inline.

## Pre-registered outcomes — scored as written, before the log is read

**On the FPS question (I2), diffing profile B against profile A:**

- **PASS / cause named:** the delta is concentrated — a small number of buckets (<= 5) account for
  the majority of the increase, resolving to nameable `MODULE+RVA` sites. The "intrinsic
  compositing" conclusion is then **refuted**: there is a specific hot site, and it is a fix target.
- **FAIL / conclusion upheld:** the increase is diffuse across many unrelated buckets with no
  concentration. "Intrinsic per-frame composite cost" then stands as **measured**, not merely
  inferred, and the HUD-scaling goal is correctly closed as engine-level work.
- **VOID:** total sample count in either phase < 200, or the sampler fails to attach, or the phases
  are not comparable (a resize/zoom/city change between them). **Do not interpret a VOID profile.**

**On the class question (I1):**

- **H supported:** children read as `+0x1E894`-family rasters with coherent dims/pitch (pitch
  consistent with `width * 2`, fix16), and their dims **do not change** across the SetRect. That
  identifies the fixed-extent surface as the thing a real reflow must resize, and points the fix at
  machinery steps 1-11 already own (`FUN_10009efb` create-replay).
- **H refuted:** children are not that family, or reads are incoherent (pitch/dims inconsistent, no
  readable backing). Then the raster reading is wrong and the "unknown class" write-up stands.
- **Partial:** family confirmed but dims **do** track the SetRect — the bar already re-extents itself,
  and the cost is elsewhere.

## Falsifiers, stated in advance

- If profile A and profile B are statistically indistinguishable **while the owner reports the FPS
  drop in phase B**, the sampler is not seeing the cost (wrong thread, or the cost is off-thread /
  in the driver). That is an **instrument failure, VOID** — not evidence of "no cost". The owner's
  perception is the ground truth the instrument must match.
- If the owner reports **no FPS drop at all** this run, the whole comparison is VOID (nothing to
  localize) and that itself is a finding worth recording.

## Safety

- Gated behind `SC3RESIZE_HUDLAB=1`. Unset, the mod is byte-for-byte the shipped viewport build
  with the HUD native. The default ship path is untouched.
- The only write is the HUD `vt+0xc8` SetRect, already run without crash or VEH fault (attempt 3).
- No teardown, no rebuild (that approach is falsified and stays disabled), no disk patching.
- VEH crash logger stays installed throughout.
- `SuspendThread` on the render thread is the one new risk. Mitigated: no logging or allocation
  while suspended, resume is unconditional on the same iteration, sampler exits on `g_prof_on == 0`.

## What this run does NOT claim

It does not attempt a reflow, does not resize any HUD surface, and does not produce a shippable HUD
change. It produces the two measurements that decide whether a reflow is reachable at all.
