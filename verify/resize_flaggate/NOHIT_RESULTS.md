# NOHIT_RESULTS.md

# ⭐⭐ ANSWERED WITHOUT A SINGLE CLICK — the `+0x80/+0x84` write NEVER HAPPENS

**2026-09-01, attempt 2, two no-human smoke runs. Hypothesis REFUTED.**

After fixing the instrument (below), the two arms were run purely to validate that the flags
arrive. They answered the whole question instead.

**Arm B — the shipping build, `nohit=0`:**

```
### FLAGS> cluster=1 input=1 nohit=0 ...
HIT> bottom bar:      rect +0x80..0x8c = [1248 1025 1847 1081] (599x56)  want origin (1248,1025)
HIT> side panel:      rect +0x80..0x8c = [1952 481 2048 923]  (96x442)  want origin (1952,481)
HIT> painter window:  rect +0x80..0x8c = [1888 917 2048 1081] (160x164) want origin (1888,917)
```

**Count of lines showing an actual write (`hit rect ->`): 0.**

In every case the rect **already holds the exact value the mod was about to write**, and the
extents are positive, so `rz_win_move_hit` takes its `/* already correct */` early return and
**writes nothing**. This is the normal, shipping path — not a special mode.

**Therefore arm A and arm B are identical in effect, and the experiment is decided by construction:
a write that never executes cannot be the blocker.** No owner click was needed, and running one
would have compared a build against itself.

| pre-registered outcome | |
|---|---|
| A-PASS / A-FAIL / A-REGRESS | none apply — the arms are not distinct |
| **hypothesis** | **REFUTED: there is no write to refute the effects of** |

## ⛔ And a false comment in our own source, falsified by this run

`sc3resize.c:901` says, at the `rz_win_move_hit` call site:

```c
rz_win_move_hit(w, name, ox, oy, x1, y1);   /* SetRect does not touch +0x80/+0x84 */
```

**It does.** For the bottom bar and the side panel, the `vt+0xc8` SetRect call is the *only* thing
that runs between reading the old rect and this log line, and by that point `+0x80..0x8c` already
holds the new position. The engine maintains that rect itself.

So `rz_win_move_hit` has been dead code for its entire existence. It was added as the fix for
clickability, was committed as "THE FIX" (`3621894`, `5a5a45c`), and **has never once written a
byte.** Two of the three "confident fixes that failed" in `HANDOFF.md`'s scorecard were this
function.

## Where that leaves the blocker

Every geometric explanation is now exhausted:

- `+0x14..0x20` (window rect) — moved by SetRect, and it is what `FUN_1006de62`, the hit test
  `FUN_1001e748` actually calls, compares `[CONFIRMED @ SIMUI 0x1006de62; GZWIND 0x1001e748]`.
- `+0x80..0x8c` — maintained by the engine, correct, and read only as extents by `FUN_1006ddbd`.
- `+0x90` (paint dest) — moved, and demonstrably honoured: the HUD *renders* in the corner.
- `vt+0xf0(0x80000)` — refuted statically in `PRE.md`; not a gate.

**Surviving suspects, in order:**

1. **Reachability** — does the find-at-point walk from `sink+0x38` ever reach these windows?
   `[UNCERTAIN]`, never tested. `FUN_1001e748` only recurses into children of `this+0x34`.
2. **`vt+0xf0(1)`, the shown bit** — gates every child before recursion
   `[CONFIRMED @ GZWIND 0x1001e748]`. Set by default (`0x903`), so this is only the answer if
   relocation hides something.

**Both are answerable with NO human in the loop**, which attempt 1 wrongly assumed was impossible:
call the engine's own find-window-at-point from the mod with a coordinate inside the relocated bar,
and log which window it returns. That is a direct read of the thing in question rather than a proxy
for it — and this project has now been burned three times by proxies.

---

# History — attempt 1: **VOID**. My error, not the mod's.

Scored against `NOHIT_PRE.md` (committed `5c61566`, before the build).

## Verdict: VOID

`NOHIT_PRE.md` pre-registered VOID as *"no click verified inside a logged rect, or the HUD does not
relocate, or a fault fires"*. **Two of the three fired.** Nothing about the hypothesis was tested and
nothing may be inferred from this run.

## The measurements

| line | count | meaning |
|---|---|---|
| `INPUT> click` | **0** | no click was ever logged |
| `NOHIT>` | **0** | `rz_win_move_hit` never took the arm-A branch |
| `CLUSTER>` | **0** | cluster mode never engaged |
| `WINSTATE>` | **0** | the new per-click dump never ran |
| `FAULT CAUGHT` | 0 | (the SEH catcher was clean) |
| log lines | 73 | the run itself completed normally |

**None of the three environment flags reached the DLL.** A grep for `cluster|nohit|input` across the
whole log returns nothing. What ran instead was the default bar dock+span path (`HUDFIT>` refitting
the bar to 2048x56), which is what the mod does when `SC3RESIZE_CLUSTER` is unset.

## Root cause — a trap that was already written down, in the file I read

`verify/resize_hudlab/HANDOFF.md`, "Tooling left behind":

> `auto.ps1` … **Env vars must be set in the parent shell** (`-EnvVars` with `pwsh -File` embeds
> quotes).

I invoked it as `pwsh -NoProfile -File auto.ps1 -EnvVars "SC3RESIZE_CLUSTER=1","SC3RESIZE_INPUT=1",…`
— **precisely the form the handoff warns against.** I had read that line earlier in the session and
quoted the `auto.ps1` tooling note back before using it. Reading a warning is not the same as
applying it.

This is the same shape as the three "wired behind the wrong flag" errors the handoff records against
the previous session: **a feature silently not running, in a log that looks internally consistent.**
The log here is entirely healthy — city loads, resize fires, HUD refits, zero faults — and reports
nothing wrong. Only the absence of lines I was specifically looking for revealed it.

## Second reason this attempt could not have worked

**No human was at the keyboard.** Zero clicks were logged because zero clicks were made. Even with
the flags correct, arm A requires an owner clicking the relocated HUD, and I launched a 120-second
hold without first confirming the owner was present and ready. The lease and the launch were spent
on a window nobody could use.

## Corrections for attempt 2

1. **Set the env vars in the parent shell**, then call `auto.ps1` with no `-EnvVars`:
   ```powershell
   $env:SC3RESIZE_CLUSTER=1; $env:SC3RESIZE_INPUT=1; $env:SC3RESIZE_NOHIT=1
   ```
2. **Add a startup flag echo to the DLL.** The mod logs no line stating which flags it parsed, which
   is the only reason this failure was silent. A single `FLAGS> cluster=%d input=%d nohit=%d …` line
   at init makes this class of error impossible to miss again, and costs nothing.
3. **Confirm the owner is at the keyboard before acquiring the lease**, not after launching.
4. Gate the run: if the flag echo does not show `nohit=1`, abort before the owner spends attention on
   clicking.

## Incidental, unrelated to this experiment

A VEH fault fires at t+3.3 ms on every launch, before any mod work:
`code=0xC0000096 at SC3U.exe+0x84122` (privileged instruction). The run continues normally and this
predates this build. **Not investigated, not claimed to be benign** — logged here so it is not
mistaken for a new defect later.

## What this cost

One build, one lease acquisition, one 120 s launch. No evidence about the hypothesis was produced.
The hypothesis in `NOHIT_PRE.md` stands exactly where it stood before the run: untested.
