# RESULTS — #3 bridge stash-and-validate WITNESS (2026-08-26). FALSIFIER PASSES. Single view.
# Plus a base finding that CORRECTS my inference and flags a latent X-cave fragility.

**Verdict: the top-row pre-registered outcome landed.** The bridge pointer survives + validates across a
resize, there is exactly one iso view, and it equals the harness's independent `g_iso`. The pure-DLL stash
is viable; build the (position-independent) cave next.

## Provenance
Probe `a1d0c7c70037b95c…d55d` (280064 b), verb `SC3PROBE_STASH_WITNESS`. Europolis, `RESIZE=1
RESIZETO=1280x1024 RESIZEAT=22`. Live install (four-recipe SIMSPR + patched GZGraphicD; the witnessed
pointers are recipe-independent). `capture.log`. **The capture.ps1 fix also verified in-flight:** lease = 7
min (from `-AtSec 100`), dirty detected at acquire, `released (DIRTY handoff recorded)` — no leak.

## The measurement (`STASHW>` @ capture.log:916-988)
| | PRE-resize | POST-resize |
|---|---|---|
| bridge ptr | `0x0D4602B0` ok=1 | **`0x0D4602B0` (SAME) ok=1** |
| iso (bridge+0x18) | `0x0ED5A3D8` ok=1 | **`0x0ED5A3D8` (SAME) ok=1** |
| iso vtable | `0x033A250C` == want ✓ | `0x033A250C` == want ✓ |
| iso == g_iso | **1** | **1** |
| iso-vtable objects reachable | **1 (single view)** | **1 (single view)** |

- **Survives:** identical bridge and iso pointers before and after the resize (which re-runs Init + refill —
  a stronger test than a real WM_SIZE, which never touches the SIMSPR bridge).
- **Validates:** readable, `bridge+0x18` iso vtable == `SIMSPR+0x6250c` (runtime base), == `g_iso`.
- **Single view:** `rd_find_iso` count = 1 both phases — no `cam`-verb ambiguity. The minimap is not a
  second iso-vtable object reachable from the view. One stash yields both pointers, unambiguously.

## The base finding — CORRECTS my inference, and confirms position-independence is mandatory
Measured runtime bases: **SIMSPR = `0x03340000` (relocated)**, **GZGraphicD = `0x03030000` (relocated)**.
- SIMSPR relocated: as inferred.
- **GZGraphicD ALSO relocated this run** — which REFUTES my inference that GZGraphicD sits at `0x10000000`.
  Base assignment is plain load-order collision (no ASLR), and it **differs by run/DLL-set**: GZGraphicD won
  `0x10000000` in the owner's no-probe X-test (its absolute refs worked), but lost it here (the injected
  `sc3probe.dll` took `0x10000000` first, forcing GZGraphicD to relocate). Exactly the load-order variance
  the owner warned about. The probe's validation was correct because it uses `GetModuleHandleA + RVA`
  (base-safe) — that is why `vt` read `0x033A250C` and matched.

## ⚠️ Latent fragility this surfaced in the shipped X-cave (close_button_quit)
The X-cave uses ABSOLUTE refs (`call [0x1001e05c]`, `push 0x1001d832`) that are correct **only when
GZGraphicD loads at `0x10000000`**. In the owner's no-probe launch it does, so the X quit cleanly. But under
any relocation of GZGraphicD (this witness run; a different OS/DLL set), `call [0x1001e05c]` reads a foreign/
unmapped address and would **CRASH on WM_CLOSE** (the fault is on the pointer READ, BEFORE the fail-closed
`test/je`, so it is not caught). This violates the "no crash on close" bar in principle — it is safe for the
owner's current use only by base-luck. **Fix: make the X-cave position-independent (call/pop EIP → resolve
the IAT slots and strings relative to the cave), the same technique the bridge cave will use.** The
resize_rectfix cave is unaffected (all-relative by construction, as the owner verified).

## Verdict + next
Falsifier PASSES: pure-DLL stash viable, single view, pointer survives+validates. Two builds follow, both
position-independent (call/pop EIP), no absolute refs: (1) harden the X-cave; (2) the bridge stash cave at
`FUN_10016eba` writing to a `.data` slot. State left: witness verb in the probe; live install unchanged
(owner's four-recipe SIMSPR + patched GZGraphicD); lease released (DirtyOk), no leak.
