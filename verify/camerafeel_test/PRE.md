# PRE-REGISTRATION — camera-feel dead zone + SendInput feel test

Written and committed BEFORE the lease. Owner: `camerafeel`. Fixture: `Cities/Europolis.sc3`
(non-Farmsville, known-good in-city render; every U-082 churn observation on record is Farmsville).
SIMSPR restored to **shipped** (`Apps/SIMSPR.DLL.shipped`, sha `eec71500…`) for the run: divisor
`-2` (`fe fe`), dead zone `12.0f` `@0x100676a4`, clamp `80.0f`, scroll `32.0`×5. Probe
`sc3probe.dll` sha `871c03c9…`.

Two legs in one launch. gzseq:
`cam;dragtest:16,0;setdead:4;dragtest:16,0;setdead:12;dragtest:16,0;dragtest:100,40;rinput:600,400,480,400;cam`

## Leg 1 — dead-zone geometry A/B/A (transport-independent, `dragtest` direct call)

`dragtest:mx,my` calls `FUN_10042cfe`(anchor 0,0, active) then `FUN_10043a38`(mx,my) directly and
reads velX `+0x1f4` / velY `+0x1f8`, computing the expected from the LIVE divisor + dead zone +
clamp `[CONFIRMED @ 0x10043a38]`. `setdead:N` hot-patches the dead-zone f32 live. On shipped
divisor `-2`:

| step | dead zone | raw velX = (0-16)/-2 | gate | EXPECT velX |
|---|---|---|---|---|
| `dragtest:16,0` | 12.0 | 8 | `8 <= 12` -> dead | **0.000** |
| `setdead:4` then `dragtest:16,0` | 4.0 | 8 | `4 < 8 <= 80` -> band | **8.000** |
| `setdead:12` then `dragtest:16,0` | 12.0 | 8 | dead again | **0.000** |
| `dragtest:100,40` control | 12.0 | 50 (velY 20) | band | **50.000 / 20.000** |

- **CONFIRMS:** velX at (16,0) reads **0 -> 8 -> 0** as the dead zone flips `12 -> 4 -> 12`, and the
  (100,40) control stays **50/20** (the knob only changes the near-threshold engage, not general
  motion). Every `dragtest` VERDICT prints "matches the live gate (PASS)". `setdead` reports the
  f32 `12.000 -> 4.000 -> 12.000`. This is the dead-zone C3, mirroring how `drag_divisor` and
  `edge_margin` were confirmed.
- **FALSIFIES:** velX != 0 at dz 12, or != 8 at dz 4, or any `dragtest` MISMATCH, or the control
  not 50/20. Any of these => the dead-zone byte does not behave as the decompilation predicts =>
  do NOT stage `drag_deadzone=4`.

## Leg 2 — SendInput faithful feel test (closes the open leg of D-002)

`rinput:600,400,480,400` runs the rdrag A/B/A state machine with the SendInput transport: idle
drift control, gesture A (divisor `-2`, real OS right-drag 600,400 -> 480,400 = 120 px left over
6 moves), read ΔA, hot-patch divisor to `-4` live, identical gesture B, read ΔB, restore `-2`.

- **VALIDITY GATE (the D-002 closer):** gesture A via SendInput MUST move the camera (ΔA != 0). The
  SendMessage transport gave **ΔA = (0,0)** on 2026-08-25 (STATUS_camera.md run 1), because
  GZWinD/winmgr's pan recognition polls `GetAsyncKeyState`, which a posted WM message does not set.
  If SendInput gives **ΔA != 0** => the OS-level transport arms the pan where WM-post did not =>
  the faithful feel instrument works and D-002's open leg is REACHABLE.
- **CONFIRMS:** ΔA != 0 (gate passes) AND idle drift ~0 (no U-082 churn) AND single `cam` candidate
  AND ratio ΔB/ΔA in **[0.40, 0.60]** (drag4 halves the real OS-driven pan).
- **FALSIFIES / null:** ΔA = (0,0) => SendInput also did not arm the pan => instrument still gapped,
  NO verdict on halving (an instrument gap, never dressed as a negative). Idle drift ~ ΔA => churn
  active => void. >1 `cam` candidate => ambiguous. Ratio ~1.0 => patch inert.

## Post-run staging (gated on Leg 1)

If Leg 1 CONFIRMS (dead-zone geometry as predicted), adopt the owner's chosen `drag_deadzone=4`:
stage the **three-recipe** standing build `scroll_speed=16 + drag_divisor=4 + drag_deadzone=4`
against `SIMSPR.DLL.shipped` in ONE invocation, gate `--diff` = **8 runs / 14 bytes**
(pre-measured, sha `58aabcb1…`), verify live (scroll `16.0`×5, div `fc`, dz `4.0`), and update the
BOARD standing rule. If Leg 1 FALSIFIES, restore the two-recipe build and stage nothing new.

Leg 2's outcome informs D-002 only; it does not gate the dead-zone adoption (the owner chose 4.0
independently; Leg 1 confirms the mechanism).

---

# PRE-REGISTRATION 2 — gentler retune (scroll8 + drag4 + deadzone2), 2026-08-26

Committed BEFORE running `--out`/`--diff`. Owner ruling: three-recipe build kept (diagonal confirmed
better by feel), `rinput` kept disarmed. Retune for a gentler onset and gentler keys:
`scroll_speed=8` (¼ of shipped 32), `drag_divisor=4` (unchanged), `drag_deadzone=2` (halves the onset
step again).

**This differs from the owner's stated count (8 runs / 16 bytes), because `8.0f`/`2.0f` have
different bit patterns than `16.0f`/`4.0f` — the run WIDTHS change, the run COUNT does not:**

| edit | shipped | new | bytes that differ | run |
|---|---|---|---|---|
| scroll ×5 | `32.0` = `00 00 00 42` | `8.0` = `00 00 00 41` | top byte only (`42→41`) | 5 × **1-byte** |
| divisor ×2 | `fe` | `fc` | 1 byte, non-adjacent | 2 × 1-byte |
| dead zone | `12.0` = `00 00 40 41` | `2.0` = `00 00 00 40` | top two (`40 41→00 40`) | 1 × **2-byte** |

**Pre-registered expectation: 8 runs / 9 bytes** at `0x10067690/94/98/9c/a0` (top byte),
`0x10043a5e`/`0x10043a68`, `0x100676a4` (top two bytes), and nothing else. **Stop and do not stage if
the actual `--diff` is anything other than exactly those 8 runs at those addresses.**

Live verify after staging: `0x10067690` `8.0` ×5, `0x10043a5e`/`0x10043a68` `fc`, `0x100676a4` `2.0`.

Coupling to record: engage distance = `deadzone × divisor` = `2×4 = 8` px (down from `4×4 = 16`). The
owner did not complain about engagement and praised the diagonal, and a smaller dead zone widens the
diagonal band, so this is expected welcome. **If it feels twitchy or catches on an unintended
click-drag, raise the divisor and lower the dead zone together to hold `deadzone × divisor` constant
while shrinking the onset** — one step, not trial and error.
